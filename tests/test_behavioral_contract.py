import json
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.behavioral_contract import (
    MAX_CONTRACT_BYTES, canonical_bytes, contract_digest, obligations,
    parse_contract_bytes, validate_contract, validate_initial_binding,
    validate_revision,
)


SCHEMA = json.loads((
    KERNEL_REFERENCES / "behavioral-verification-contract-schema.json"
).read_text())


def contract_one():
    obligation_ids = [
        "BROWSER:browser-primary", "PERSONA:persona-editor", "REG-001",
        "REQ-001", "PROOF:CHK-001:REQ-001",
    ]
    return {
        "schema_version": 1,
        "contract_id": "adaptive-fusion-verification",
        "revision": 1,
        "previous_contract_digest": None,
        "requirements": [{
            "id": "REQ-001", "source_ref": "original-prompt.md#key-requirements",
            "statement": "The result preserves the requested behavior.",
        }],
        "prohibited_regressions": [{
            "id": "REG-001", "source_ref": "assessment.html#current-state",
            "statement": "Existing output remains stable.",
        }],
        "checks": [{
            "id": "CHK-001",
            "argv": ["python3.12", "-m", "unittest", "tests.test_example"],
            "proves_requirement_ids": ["REQ-001"],
            "baseline_expectation": "must_fail",
        }],
        "persona_case_ids": ["persona-editor"],
        "browser_case_ids": ["browser-primary"],
        "manual_requirements": [],
        "revision_justification": {
            "reason_code": "initial_binding",
            "summary": "Initial approved behavioral contract.",
            "added_obligation_ids": obligation_ids,
            "retained_obligation_ids": [],
            "removed_obligation_ids": [],
            "human_approval_evidence_ref": None,
        },
    }


class BehavioralContractTests(unittest.TestCase):
    def test_documented_shape_matches_schema_and_bool_numeric_values_do_not(self):
        contract = contract_one()
        self.assertTrue(schema_matches(contract, SCHEMA))
        self.assertEqual(validate_initial_binding(contract)["revision"], 1)
        for field in ("schema_version", "revision"):
            mutated = json.loads(json.dumps(contract))
            mutated[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_contract(mutated)

    def test_canonical_digest_ignores_author_order_but_not_behavior(self):
        contract = contract_one()
        contract["requirements"].append({
            "id": "REQ-002", "source_ref": "original-prompt.md#second",
            "statement": "A second behavior is explicit.",
        })
        contract["checks"].append({
            "id": "CHK-002", "argv": ["python3.12", "-m", "unittest", "tests.test_second"],
            "proves_requirement_ids": ["REQ-002", "REQ-001"],
            "baseline_expectation": "may_pass",
        })
        contract["revision_justification"]["added_obligation_ids"].extend([
            "REQ-002", "PROOF:CHK-002:REQ-001", "PROOF:CHK-002:REQ-002",
        ])
        reordered = json.loads(json.dumps(contract))
        for name in ("requirements", "checks", "persona_case_ids", "browser_case_ids"):
            reordered[name].reverse()
        reordered["checks"][0]["proves_requirement_ids"].reverse()
        reordered["revision_justification"]["added_obligation_ids"].reverse()
        self.assertEqual(contract_digest(contract), contract_digest(reordered))
        self.assertEqual(canonical_bytes(contract), canonical_bytes(reordered))
        changed = json.loads(json.dumps(contract))
        changed["requirements"][0]["statement"] += " Changed."
        self.assertNotEqual(contract_digest(contract), contract_digest(changed))

    def test_strict_closed_validation_and_safe_argv_links(self):
        mutations = []
        extra = contract_one(); extra["unknown"] = True; mutations.append(extra)
        record_extra = contract_one(); record_extra["requirements"][0]["unknown"] = True; mutations.append(record_extra)
        argv_string = contract_one(); argv_string["checks"][0]["argv"] = "python test.py"; mutations.append(argv_string)
        empty_argv = contract_one(); empty_argv["checks"][0]["argv"] = []; mutations.append(empty_argv)
        nul_argv = contract_one(); nul_argv["checks"][0]["argv"] = ["python3.12", "bad\x00arg"]; mutations.append(nul_argv)
        shell = contract_one(); shell["checks"][0]["argv"] = ["sh", "-c", "touch should-not-run"]; mutations.append(shell)
        unknown_proof = contract_one(); unknown_proof["checks"][0]["proves_requirement_ids"] = ["REQ-999"]; mutations.append(unknown_proof)
        duplicate = contract_one(); duplicate["requirements"].append(duplicate["requirements"][0].copy()); mutations.append(duplicate)
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_contract(mutation)

    def test_manual_and_not_runnable_requirements_remain_explicit(self):
        contract = contract_one()
        contract["checks"] = []
        contract["manual_requirements"] = [{
            "requirement_id": "REQ-001", "reason_code": "human_judgment_required",
            "evidence_ref": None,
        }]
        contract["revision_justification"]["added_obligation_ids"].remove(
            "PROOF:CHK-001:REQ-001",
        )
        canonical = validate_initial_binding(contract)
        self.assertIsNone(canonical["manual_requirements"][0]["evidence_ref"])
        self.assertNotIn("PROOF:CHK-001:REQ-001", obligations(canonical))

    def test_revision_recomputes_deltas_and_requires_approval_for_weakening(self):
        previous = validate_initial_binding(contract_one())
        previous_digest = contract_digest(previous)
        revision = json.loads(json.dumps(previous))
        revision.update({"revision": 2, "previous_contract_digest": previous_digest})
        revision["prohibited_regressions"] = []
        revision["checks"][0]["baseline_expectation"] = "may_pass"
        revision["revision_justification"] = {
            "reason_code": "approved_scope_change", "summary": "Approved narrower baseline.",
            "added_obligation_ids": [],
            "retained_obligation_ids": [
                "BROWSER:browser-primary", "PERSONA:persona-editor", "REQ-001",
                "PROOF:CHK-001:REQ-001",
            ],
            "removed_obligation_ids": ["REG-001"],
            "human_approval_evidence_ref": None,
        }
        with self.assertRaises(ValueError):
            validate_revision(previous, revision, previous_digest)
        revision["revision_justification"]["human_approval_evidence_ref"] = (
            "plans/adaptive/plan.html#approval"
        )
        self.assertEqual(validate_revision(previous, revision, previous_digest)["revision"], 2)
        revision["previous_contract_digest"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            validate_revision(previous, revision, previous_digest)

    def test_parser_rejects_malformed_invalid_utf8_duplicate_depth_and_size(self):
        valid = canonical_bytes(contract_one())
        bad = {
            "malformed": b"{",
            "utf8": b"\xff",
            "duplicate": valid.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1', 1),
            "depth": b'{"nested":' + b"[" * 17 + b"0" + b"]" * 17 + b"}",
            "oversize": b" " * (MAX_CONTRACT_BYTES + 1),
        }
        for name, raw in bad.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_contract_bytes(raw)


if __name__ == "__main__":
    unittest.main()
