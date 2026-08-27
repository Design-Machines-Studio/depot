import copy
import json
import unittest
from pathlib import Path

from workflow_kernel._translation import canonical_observation_receipt_digest
from workflow_kernel.pipeline_adapter import (
    build_legacy_browser_reconciliation,
    translate_pipeline_receipts,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "receipts"
    / "pipeline-legacy-browser-recovery.json"
)


class LegacyBrowserReconciliationTests(unittest.TestCase):
    def receipts(self):
        return json.loads(FIXTURE.read_text())

    def reconciled(self):
        return list(build_legacy_browser_reconciliation(
            self.receipts(),
            target_sequence=1,
            occurred_at="2026-01-01T00:03:00Z",
            authoritative_receipt="receipts/legacy-reconciliation.json",
        ))

    def test_exact_reconciliation_preserves_block_and_allows_later_evidence(self):
        original = self.receipts()
        reconciled = self.reconciled()
        self.assertEqual(reconciled[:-1], original)
        events = translate_pipeline_receipts(reconciled)
        self.assertEqual(events[1].payload["stage"], "browser_recovery")
        self.assertEqual(events[1].payload["status"], "blocked")
        self.assertEqual(events[1].payload["reason_code"], "human_help_required")
        self.assertTrue(events[1].payload["human_intervention"])
        self.assertEqual(events[2].payload["stage"], "browser_verification")
        self.assertEqual(events[2].payload["status"], "passed")
        self.assertEqual(events[2].payload["browser_passed"], 1)
        self.assertEqual(events[3].payload["stage"], "legacy_browser_reconciliation")
        self.assertEqual(events[3].payload["status"], "recorded")

    def test_wrong_identity_contract_order_or_reason_fails_closed(self):
        mutations = {}
        for name, field, value in (
            ("run", "target_run_id", "another-run"),
            ("sequence", "target_sequence", 0),
            ("stage", "target_stage", "dispatch"),
            ("digest", "target_receipt_digest", "sha256:" + "d" * 64),
            ("target_contract", "target_contract_digest", "sha256:" + "d" * 64),
            ("claim_contract", "contract_digest", "sha256:" + "d" * 64),
            ("reason", "reconciliation_reason", "generic_legacy_exception"),
        ):
            candidate = copy.deepcopy(self.reconciled())
            candidate[-1][field] = value
            mutations[name] = candidate
        reordered = copy.deepcopy(self.reconciled())
        claim = reordered.pop()
        reordered.insert(1, claim)
        for sequence, receipt in enumerate(reordered):
            receipt["sequence"] = sequence
        claim["target_sequence"] = 2
        mutations["order"] = reordered
        for name, candidate in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                translate_pipeline_receipts(candidate)

    def test_duplicate_conflicting_and_already_canonical_targets_fail(self):
        duplicate = copy.deepcopy(self.reconciled())
        second = copy.deepcopy(duplicate[-1])
        second.update({
            "sequence": len(duplicate),
            "occurred_at": "2026-01-01T00:04:00Z",
            "authoritative_receipt": "receipts/duplicate-reconciliation.json",
        })
        duplicate.append(second)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            translate_pipeline_receipts(duplicate)

        conflicting = copy.deepcopy(duplicate)
        conflicting[-1]["target_receipt_digest"] = "sha256:" + "d" * 64
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)

        broadened = copy.deepcopy(self.reconciled())
        broadened[-1]["browser_passed"] = 1
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(broadened)

        canonical = self.receipts()
        canonical[1]["recovery_receipts"] = []
        with self.assertRaises(ValueError):
            build_legacy_browser_reconciliation(
                canonical,
                target_sequence=1,
                occurred_at="2026-01-01T00:03:00Z",
                authoritative_receipt="receipts/reconciliation.json",
            )

    def test_reconciliation_alone_cannot_create_passing_or_terminal_semantics(self):
        receipts = self.receipts()[:2]
        candidate = build_legacy_browser_reconciliation(
            receipts,
            target_sequence=1,
            occurred_at="2026-01-01T00:02:00Z",
            authoritative_receipt="receipts/reconciliation.json",
        )
        events = translate_pipeline_receipts(candidate)
        self.assertFalse(any(
            event.payload.get("stage") in {"browser_verification", "run_summary"}
            for event in events
        ))
        self.assertFalse(any(
            event.payload.get("status") in {"passed", "succeeded", "clean"}
            for event in events
        ))
        self.assertNotIn("browser_passed", events[-1].payload)

    def test_digest_boundary_rejects_bounds_and_non_exact_builtins(self):
        oversized = self.receipts()[1]
        oversized["extra"] = list(range(10_001))
        with self.assertRaises(ValueError):
            canonical_observation_receipt_digest(oversized)

        class ListSubclass(list):
            pass

        non_exact = self.receipts()[1]
        non_exact["missing_case_ids"] = ListSubclass(["case-browser-primary"])
        with self.assertRaises(ValueError):
            canonical_observation_receipt_digest(non_exact)

        class DictSubclass(dict):
            pass

        with self.assertRaises(ValueError):
            canonical_observation_receipt_digest(DictSubclass(self.receipts()[1]))


if __name__ == "__main__":
    unittest.main()
