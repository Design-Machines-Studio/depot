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
        "REQ-001", "PROOF:CHK-001:REQ-001", "PROOF:CHK-001:REG-001",
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
            "proves_regression_ids": ["REG-001"],
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
            "proves_regression_ids": [],
            "baseline_expectation": "may_pass",
        })
        contract["revision_justification"]["added_obligation_ids"].extend([
            "REQ-002", "PROOF:CHK-002:REQ-001", "PROOF:CHK-002:REQ-002",
        ])
        reordered = json.loads(json.dumps(contract))
        for name in ("requirements", "checks", "persona_case_ids", "browser_case_ids"):
            reordered[name].reverse()
        reordered["checks"][0]["proves_requirement_ids"].reverse()
        reordered["checks"][0]["proves_regression_ids"].reverse()
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
        for argv in (
            ["sh", "-c", "touch should-not-run"],
            ["bash", "-lc", "touch should-not-run"],
            ["zsh", "-fc", "touch should-not-run"],
            ["bash.exe", "-c", "touch should-not-run"],
            ["sh.exe", "-lc", "touch should-not-run"],
            ["zsh.exe", "-fc", "touch should-not-run"],
            ["mksh", "-c", "touch should-not-run"],
            ["yash", "-c", "touch should-not-run"],
            ["fish", "--command", "touch should-not-run"],
            ["fish", "--init-command=touch should-not-run"],
            ["fish", "--init-command", "touch should-not-run"],
            ["fish", "-C", "touch should-not-run"],
            ["/usr/bin/env", "bash", "-ec", "touch should-not-run"],
            ["bash", "-O", "extglob", "-c", "touch should-not-run"],
            ["bash", "--rcfile", "/dev/null", "-c", "touch should-not-run"],
            ["bash", "--init-file=/dev/null", "-c", "touch should-not-run"],
            ["/usr/bin/env", "-S", "bash -c touch should-not-run"],
            ["/usr/bin/env", "--split-string=bash -c touch should-not-run"],
            ["/usr/bin/env", "-uNAME", "bash", "-c", "touch should-not-run"],
            ["/usr/bin/env", "-C/tmp", "bash", "-c", "touch should-not-run"],
            ["/usr/bin/env", "-iS", "bash -c touch should-not-run"],
            ["/usr/bin/env", "-iu", "NAME", "bash", "-c", "touch should-not-run"],
            ["/usr/bin/env", "-", "bash", "-c", "touch should-not-run"],
            ["env.exe", "-S", "bash -c touch should-not-run"],
            ["env.exe", "--split-string=bash -c touch should-not-run"],
            ["pwsh", "-Command", "Write-Output should-not-run"],
            ["pwsh", "-ep", "Bypass", "-c", "Write-Output should-not-run"],
            ["pwsh", "-o", "text", "-c", "Write-Output should-not-run"],
            ["pwsh", "-ec", "ZgBvAG8A"],
            ["pwsh", "-cwa", "Write-Output should-not-run"],
            ["pwsh", "-ConfigurationFile", "config.ps1", "-c", "Write-Output should-not-run"],
            ["powershell.exe", "-EncodedCommand", "ZgBvAG8A"],
            ["pwsh.exe", "-e", "ZgBvAG8A"],
            ["pwsh.exe", "-en", "ZgBvAG8A"],
            ["cmd.exe", "/c", "echo should-not-run"],
            ["cmd.exe", "/d", "/q", "/s", "/c", "echo should-not-run"],
            ["cmd", "/K", "echo should-not-run"],
        ):
            shell = contract_one(); shell["checks"][0]["argv"] = argv; mutations.append(shell)
        unknown_proof = contract_one(); unknown_proof["checks"][0]["proves_requirement_ids"] = ["REQ-999"]; mutations.append(unknown_proof)
        unknown_regression = contract_one(); unknown_regression["checks"][0]["proves_regression_ids"] = ["REG-999"]; mutations.append(unknown_regression)
        unproved_regression = contract_one(); unproved_regression["checks"][0]["proves_regression_ids"] = []; mutations.append(unproved_regression)
        no_proof = contract_one(); no_proof["checks"][0]["proves_requirement_ids"] = []; no_proof["checks"][0]["proves_regression_ids"] = []; mutations.append(no_proof)
        for argv in (
            ["tool", "--api-key", "sk-live-credential"],
            ["tool", "--api-key=opaque-credential-value"],
            ["tool", "--api_key=opaque-credential-value"],
            ["tool", "--token", "opaque-credential"],
            ["tool", "sk-live-credential"],
            ["tool", "gho_abcdefghijk"],
            ["tool", "AKIAIOSFODNN7EXAMPLE"],
            ["tool", "sk_live_1234567890abcdef"],
            ["tool", "--client-secret", "opaque-credential-value"],
            ["tool", "--clientauth", "opaque-credential-value"],
            ["tool", "--client-auth=opaque-credential-value"],
            ["tool", "--github-token", "opaque-credential-value"],
            ["tool", "--githubtoken=opaque-credential-value"],
            ["tool", "--apikey", "opaque-credential-value"],
            ["tool", "--apikey=opaque-credential-value"],
            ["tool", "--oauth-token", "opaque-credential-value"],
            ["tool", "--session-token=opaque-credential-value"],
            ["tool.exe", "/password", "opaque-credential-value"],
            ["tool.exe", "/api-key", "opaque-credential-value"],
            ["tool.exe", "/client-secret=opaque-credential-value"],
            ["tool", "--credentials", "opaque-credential-value"],
            ["tool", "--creds=opaque-credential-value"],
            ["tool", "--passphrase", "opaque-credential-value"],
            ["tool", "--bearer", "opaque-credential-value"],
            ["curl", "--oauth2-bearer", "opaque-credential-value"],
            ["tool", "--private-key", "opaque-credential-value"],
            ["tool", "ASIAIOSFODNN7EXAMPLE"],
        ):
            secret = contract_one(); secret["checks"][0]["argv"] = argv; mutations.append(secret)
        duplicate = contract_one(); duplicate["requirements"].append(duplicate["requirements"][0].copy()); mutations.append(duplicate)
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_contract(mutation)
        script = contract_one()
        script["checks"][0]["argv"] = ["bash", "scripts/check-contract.sh"]
        self.assertEqual(
            validate_contract(script)["checks"][0]["argv"],
            ["bash", "scripts/check-contract.sh"],
        )
        script_args = contract_one()
        script_args["checks"][0]["argv"] = [
            "bash", "scripts/check-contract.sh", "-c", "config.json",
        ]
        self.assertEqual(
            validate_contract(script_args)["checks"][0]["argv"],
            ["bash", "scripts/check-contract.sh", "-c", "config.json"],
        )
        powershell_file = contract_one()
        powershell_file["checks"][0]["argv"] = [
            "pwsh", "-ExecutionPolicy", "Bypass", "-File", "scripts/check.ps1",
        ]
        self.assertEqual(
            validate_contract(powershell_file)["checks"][0]["argv"],
            ["pwsh", "-ExecutionPolicy", "Bypass", "-File", "scripts/check.ps1"],
        )
        positional_shell_name = contract_one()
        positional_shell_name["checks"][0]["argv"] = [
            "tool", "bash", "-c", "config.json",
        ]
        self.assertEqual(
            validate_contract(positional_shell_name)["checks"][0]["argv"],
            ["tool", "bash", "-c", "config.json"],
        )
        wrapped_program_args = contract_one()
        wrapped_program_args["checks"][0]["argv"] = [
            "env", "tool", "-Sdata", "--split-string=value",
        ]
        self.assertEqual(
            validate_contract(wrapped_program_args)["checks"][0]["argv"],
            ["env", "tool", "-Sdata", "--split-string=value"],
        )
        attached_env_operand = contract_one()
        attached_env_operand["checks"][0]["argv"] = [
            "env", "-uSHELL", "bash", "scripts/check-contract.sh",
        ]
        self.assertEqual(
            validate_contract(attached_env_operand)["checks"][0]["argv"],
            ["env", "-uSHELL", "bash", "scripts/check-contract.sh"],
        )
        ordinary = contract_one()
        ordinary["requirements"][0]["statement"] = (
            "Use primary_key=account_id, cache-key: request-path, and max_token=4096."
        )
        self.assertEqual(validate_contract(ordinary)["requirements"][0]["id"], "REQ-001")

    def test_manual_and_not_runnable_requirements_remain_explicit(self):
        contract = contract_one()
        contract["checks"][0]["proves_requirement_ids"] = []
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
        revision["checks"][0]["proves_regression_ids"] = []
        revision["checks"][0]["baseline_expectation"] = "may_pass"
        revision["revision_justification"] = {
            "reason_code": "approved_scope_change", "summary": "Approved narrower baseline.",
            "added_obligation_ids": [],
            "retained_obligation_ids": [
                "BROWSER:browser-primary", "PERSONA:persona-editor", "REQ-001",
                "PROOF:CHK-001:REQ-001",
            ],
            "removed_obligation_ids": ["REG-001", "PROOF:CHK-001:REG-001"],
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

    def test_behavior_mutation_digest_and_weakening_matrix(self):
        base = contract_one()
        base["requirements"].append({
            "id": "REQ-002", "source_ref": "original-prompt.md#manual",
            "statement": "Human review confirms the qualitative behavior.",
        })
        base["checks"][0]["proves_requirement_ids"].append("REQ-002")
        base["manual_requirements"] = [
            {"requirement_id": "REQ-001", "reason_code": "human_judgment_required",
             "evidence_ref": "plans/adaptive/plan.html#req-1"},
            {"requirement_id": "REQ-002", "reason_code": "human_judgment_required",
             "evidence_ref": "plans/adaptive/plan.html#req-2"},
        ]
        base["revision_justification"]["added_obligation_ids"].extend([
            "REQ-002", "PROOF:CHK-001:REQ-002",
        ])
        previous = validate_initial_binding(base)
        previous_digest = contract_digest(previous)

        def change_requirement(value):
            value["requirements"][0]["statement"] += " More specifically."

        def change_regression(value):
            value["prohibited_regressions"][0]["statement"] += " On every route."

        def remove_proof_link(value):
            value["checks"][0]["proves_requirement_ids"].remove("REQ-002")

        def remove_persona(value):
            value["persona_case_ids"].remove("persona-editor")

        def remove_browser(value):
            value["browser_case_ids"].remove("browser-primary")

        def baseline_may_pass(value):
            value["checks"][0]["baseline_expectation"] = "may_pass"

        def baseline_not_runnable(value):
            value["checks"][0]["baseline_expectation"] = "not_runnable"

        def change_argv(value):
            value["checks"][0]["argv"][-1] = "tests.test_changed"

        def change_manual(value):
            value["manual_requirements"][0]["reason_code"] = "accessibility_review"

        def remove_manual(value):
            value["manual_requirements"].pop(0)

        mutations = {
            "requirement": change_requirement,
            "regression": change_regression,
            "proof_link": remove_proof_link,
            "persona": remove_persona,
            "browser": remove_browser,
            "must_fail_to_may_pass": baseline_may_pass,
            "must_fail_to_not_runnable": baseline_not_runnable,
            "argv": change_argv,
            "manual_mutation": change_manual,
            "manual_removal": remove_manual,
        }
        for name, mutate in mutations.items():
            behavior = json.loads(json.dumps(previous))
            mutate(behavior)
            with self.subTest(name=name, assertion="digest"):
                self.assertNotEqual(contract_digest(behavior), previous_digest)

            revision = json.loads(json.dumps(previous))
            mutate(revision)
            revision.update({"revision": 2, "previous_contract_digest": previous_digest})
            old_obligations = obligations(previous)
            new_obligations = obligations(revision)
            revision["revision_justification"] = {
                "reason_code": "behavior_revision", "summary": f"Revise {name}.",
                "added_obligation_ids": sorted(new_obligations - old_obligations),
                "retained_obligation_ids": sorted(new_obligations & old_obligations),
                "removed_obligation_ids": sorted(old_obligations - new_obligations),
                "human_approval_evidence_ref": None,
            }
            with self.subTest(name=name, assertion="approval"), self.assertRaises(ValueError):
                validate_revision(previous, revision, previous_digest)
            revision["revision_justification"]["human_approval_evidence_ref"] = (
                "plans/adaptive/plan.html#approval"
            )
            with self.subTest(name=name, assertion="approved"):
                self.assertEqual(
                    validate_revision(previous, revision, previous_digest)["revision"], 2,
                )

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
