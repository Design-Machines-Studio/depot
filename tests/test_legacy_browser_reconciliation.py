import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest import mock

from workflow_kernel import _translation
from workflow_kernel._translation import canonical_observation_receipt_digest
from workflow_kernel.pipeline_adapter import (
    build_legacy_browser_reconciliation,
    translate_pipeline_receipts,
)
from workflow_kernel.redaction import freeze_json


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
        with self.assertRaisesRegex(ValueError, "multiple"):
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

    def test_multiple_distinct_reconciliation_targets_fail(self):
        receipts = self.receipts()
        first_claim = self.reconciled()[-1]
        second_target = copy.deepcopy(receipts[1])
        second_target.update({
            "sequence": 3,
            "occurred_at": "2026-01-01T00:03:00Z",
            "authoritative_receipt": "receipts/second-target.json",
        })
        first_claim.update({
            "sequence": 4,
            "occurred_at": "2026-01-01T00:04:00Z",
        })
        second_claim = copy.deepcopy(first_claim)
        second_claim.update({
            "sequence": 5,
            "occurred_at": "2026-01-01T00:05:00Z",
            "authoritative_receipt": "receipts/second-reconciliation.json",
            "target_sequence": 3,
            "target_receipt_digest": canonical_observation_receipt_digest(
                second_target,
            ),
        })
        with self.assertRaisesRegex(ValueError, "multiple"):
            translate_pipeline_receipts([
                *receipts, second_target, first_claim, second_claim,
            ])

    def test_reconciliation_timestamp_must_be_aware_and_later_than_target(self):
        original = self.receipts()
        for name, occurred_at in (
            ("earlier", "2025-12-31T23:59:00Z"),
            ("equal", "2026-01-01T00:01:00Z"),
            ("naive", "2026-01-01T00:03:00"),
            ("malformed", "not-a-timestamp"),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_legacy_browser_reconciliation(
                    original,
                    target_sequence=1,
                    occurred_at=occurred_at,
                    authoritative_receipt="receipts/reconciliation.json",
                )
            self.assertEqual(original, self.receipts())

        for name, target_occurred_at in (
            ("naive-target", "2026-01-01T00:01:00"),
            ("malformed-target", "not-a-timestamp"),
        ):
            candidate = copy.deepcopy(original)
            candidate[1]["occurred_at"] = target_occurred_at
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_legacy_browser_reconciliation(
                    candidate,
                    target_sequence=1,
                    occurred_at="2026-01-01T00:03:00Z",
                    authoritative_receipt="receipts/reconciliation.json",
                )
            self.assertEqual(len(candidate), len(original))

        offset_target = copy.deepcopy(original)
        offset_target[1]["occurred_at"] = "2026-01-01T01:01:00+01:00"
        offset_reconciled = build_legacy_browser_reconciliation(
            offset_target,
            target_sequence=1,
            occurred_at="2026-01-01T00:02:00Z",
            authoritative_receipt="receipts/reconciliation.json",
        )
        self.assertEqual(len(offset_reconciled), len(offset_target) + 1)

        reconciled = build_legacy_browser_reconciliation(
            original,
            target_sequence=1,
            occurred_at="2026-01-01T01:02:00+01:00",
            authoritative_receipt="receipts/reconciliation.json",
        )
        self.assertEqual(len(reconciled), len(original) + 1)

    def test_existing_reconciliation_timestamp_must_be_aware_and_later(self):
        for name, field, occurred_at in (
            ("earlier-claim", "claim", "2025-12-31T23:59:00Z"),
            ("equal-claim", "claim", "2026-01-01T00:01:00Z"),
            ("naive-claim", "claim", "2026-01-01T00:03:00"),
            ("malformed-claim", "claim", "not-a-timestamp"),
            ("naive-target", "target", "2026-01-01T00:01:00"),
            ("malformed-target", "target", "not-a-timestamp"),
        ):
            candidate = copy.deepcopy(self.reconciled())
            candidate[-1 if field == "claim" else 1]["occurred_at"] = occurred_at
            with self.subTest(name=name), self.assertRaises(ValueError):
                translate_pipeline_receipts(candidate)

        offset = copy.deepcopy(self.reconciled())
        offset[1]["occurred_at"] = "2026-01-01T01:01:00+01:00"
        offset[-1]["target_receipt_digest"] = (
            canonical_observation_receipt_digest(offset[1])
        )
        offset[-1]["occurred_at"] = "2026-01-01T01:03:00+01:00"
        self.assertEqual(len(translate_pipeline_receipts(offset)), len(offset))

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

    def test_digest_is_canonical_raw_json_and_byte_sensitive(self):
        target = self.receipts()[1]
        encoded = json.dumps(
            target, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        expected = "sha256:" + hashlib.sha256(encoded).hexdigest()
        self.assertEqual(canonical_observation_receipt_digest(target), expected)

        reordered = dict(reversed(tuple(target.items())))
        self.assertEqual(canonical_observation_receipt_digest(reordered), expected)

        changed = copy.deepcopy(target)
        changed["human_intervention_id"] = (
            "browser-help-sha256:" + "c" * 64
        )
        self.assertNotEqual(
            canonical_observation_receipt_digest(changed), expected,
        )

    def test_digest_boundary_retains_all_bounded_exact_json_requirements(self):
        target = self.receipts()[1]

        for name, value in (
            ("non-finite", float("nan")),
            ("unsupported", object()),
        ):
            candidate = copy.deepcopy(target)
            candidate["extra"] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                canonical_observation_receipt_digest(candidate)

        class StringSubclass(str):
            pass

        class IntSubclass(int):
            pass

        class FloatSubclass(float):
            pass

        class NestedDictSubclass(dict):
            pass

        for name, value in (
            ("string-subclass", StringSubclass("value")),
            ("integer-subclass", IntSubclass(1)),
            ("float-subclass", FloatSubclass(1.0)),
            ("mapping-subclass", NestedDictSubclass({"key": "value"})),
        ):
            candidate = copy.deepcopy(target)
            candidate["extra"] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                canonical_observation_receipt_digest(candidate)

        key_subclass = copy.deepcopy(target)
        key_subclass[StringSubclass("extra")] = "value"
        with self.assertRaises(ValueError):
            canonical_observation_receipt_digest(key_subclass)

        cycle = copy.deepcopy(target)
        cycle["extra"] = cycle
        with self.assertRaises(ValueError):
            canonical_observation_receipt_digest(cycle)

        with mock.patch.object(_translation, "MAX_PAYLOAD_DEPTH", 1):
            with self.assertRaises(ValueError):
                canonical_observation_receipt_digest({"outer": {"inner": 1}})
        with mock.patch.object(_translation, "MAX_PAYLOAD_ITEMS", 3):
            with self.assertRaises(ValueError):
                canonical_observation_receipt_digest({"a": 1, "b": 2, "c": 3})
        with mock.patch.object(_translation, "MAX_STRING_LENGTH", 3):
            with self.assertRaises(ValueError):
                canonical_observation_receipt_digest({"key": "four"})
        with mock.patch.object(_translation, "MAX_TOTAL_STRING_BYTES", 4):
            with self.assertRaises(ValueError):
                canonical_observation_receipt_digest({"k": "éé"})

    def test_digestibility_does_not_grant_durable_eligibility(self):
        candidate = {"value": "custom-scheme://private.example/path"}
        digest = canonical_observation_receipt_digest(candidate)
        self.assertRegex(digest, r"\Asha256:[0-9a-f]{64}\Z")
        with self.assertRaises((TypeError, ValueError)):
            freeze_json(candidate)

    def test_schema_owned_case_digest_identifiers_remain_exact_and_closed(self):
        reconciled = self.reconciled()
        self.assertEqual(
            reconciled[1]["missing_case_ids"],
            self.receipts()[1]["missing_case_ids"],
        )

        malformed = self.receipts()
        malformed[1]["missing_case_ids"][0] = "case-sha256:" + "A" * 64
        self.assertRegex(
            canonical_observation_receipt_digest(malformed[1]),
            r"\Asha256:[0-9a-f]{64}\Z",
        )
        with self.assertRaises(ValueError):
            build_legacy_browser_reconciliation(
                malformed,
                target_sequence=1,
                occurred_at="2026-01-01T00:03:00Z",
                authoritative_receipt="receipts/reconciliation.json",
            )


if __name__ == "__main__":
    unittest.main()
