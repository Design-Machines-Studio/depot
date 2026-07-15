import json
import copy
import unittest
from pathlib import Path

from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.schema import RunState
from workflow_kernel.shadow import ReceiptSet, ShadowComparator


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


def state(evidence):
    return RunState.from_dict({
        "schema_version": 1, "revision": 1, "run_id": "pipeline-1", "mode": "shadow", "status": "running",
        "created_at": "2026-07-14T00:00:00Z", "updated_at": "2026-07-14T00:10:00Z",
        "nodes": {}, "evidence": evidence, "cleanup_reconciled": False,
    })


class ShadowParityTests(unittest.TestCase):
    def load(self, name):
        return translate_pipeline_receipts(json.loads((FIXTURES / name).read_text()))

    def test_known_host_profiles_use_the_canonical_harness_profile_host_ids(self):
        from tests import canonical_harness_profile
        from workflow_kernel.shadow import CANONICAL_HOSTS, KNOWN_HOST_PROFILES

        declared = set(json.loads(
            canonical_harness_profile().read_text(encoding="utf-8"),
        )["hosts"])
        self.assertEqual(declared, CANONICAL_HOSTS)
        self.assertEqual(
            {profile[0] for profile in KNOWN_HOST_PROFILES}, CANONICAL_HOSTS,
        )
        # Finding 086: promotion evidence uses the same canonical host IDs --
        # native promotion must be satisfiable by real_shadow_run:claude-code.
        from workflow_kernel.promotion import SUPPORTED_PROMOTION_HOSTS
        self.assertEqual(set(SUPPORTED_PROMOTION_HOSTS), CANONICAL_HOSTS)
        self.assertEqual(
            len(SUPPORTED_PROMOTION_HOSTS), len(set(SUPPORTED_PROMOTION_HOSTS)),
        )

    def test_real_claude_code_host_receipts_classify_as_known_host_difference(self):
        codex = ReceiptSet.from_events(self.load("pipeline-codex.json"))
        claude = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        self.assertTrue(all(item["host"] == "claude-code" for item in claude))
        report = ShadowComparator().compare_receipt_sets(
            codex, ReceiptSet.from_events(translate_pipeline_receipts(claude)),
        )
        self.assertEqual(report.reason, "explained_host_difference")

    def test_known_claude_codex_mechanisms_are_explained_when_semantics_match(self):
        claude = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        codex = ReceiptSet.from_events(self.load("pipeline-codex.json"))
        report = ShadowComparator().compare_receipt_sets(codex, claude)
        self.assertEqual(report.reason, "explained_host_difference")
        self.assertTrue(report.semantic_match)
        self.assertFalse(report.safe_to_promote)

    def test_empty_receipt_sets_are_missing_evidence_not_a_safe_match(self):
        report = ShadowComparator().compare_receipt_sets(
            ReceiptSet.from_events(()), ReceiptSet.from_events(()),
        )
        self.assertEqual(report.reason, "missing_authoritative_evidence")
        self.assertFalse(report.semantic_match)
        self.assertFalse(report.safe_to_promote)

    def test_missing_authoritative_evidence_is_unsafe(self):
        authoritative = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        report = ShadowComparator().compare(state(()), authoritative)
        self.assertEqual(report.reason, "semantic_receipts_required")
        self.assertFalse(report.safe_to_promote)

    def test_exact_authoritative_evidence_matches(self):
        authoritative = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        refs = tuple(event.payload["authoritative_receipt"] for event in authoritative.events)
        report = ShadowComparator().compare(state(refs), authoritative)
        self.assertEqual(report.reason, "semantic_receipts_required")
        self.assertFalse(report.semantic_match)
        self.assertFalse(report.safe_to_promote)

    def test_semantic_mutations_never_report_safe_match(self):
        original = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        authoritative = ReceiptSet.from_events(translate_pipeline_receipts(original))
        changes = (
            (2, "status", "failed"), (2, "provider", "openrouter"),
            (2, "fallback_reason", "provider_unavailable"),
            (5, "persona_passed", 1), (7, "cleanup_blocked", 1),
            (10, "workflow_class", "bug"),
        )
        for index, key, value in changes:
            mutated = copy.deepcopy(original); mutated[index][key] = value
            if key == "workflow_class":
                for receipt in mutated: receipt[key] = value
            report = ShadowComparator().compare_receipt_sets(
                ReceiptSet.from_events(translate_pipeline_receipts(mutated)), authoritative,
            )
            with self.subTest(key=key):
                self.assertFalse(report.semantic_match)
                self.assertFalse(report.safe_to_promote)
                self.assertEqual(
                    report.reason,
                    "unsafe_to_promote" if key == "provider" else "kernel_prediction_gap",
                )

    def test_missing_and_extra_receipts_have_distinct_reasons(self):
        events = self.load("pipeline-claude.json")
        missing = ShadowComparator().compare_receipt_sets(ReceiptSet.from_events(events[:-1]), ReceiptSet.from_events(events))
        extra = ShadowComparator().compare_receipt_sets(ReceiptSet.from_events(events), ReceiptSet.from_events(events[:-1]))
        self.assertEqual(missing.reason, "missing_authoritative_evidence")
        self.assertEqual(extra.reason, "unexpected_authoritative_transition")

    def test_generic_host_fixture_is_semantically_equivalent(self):
        generic = ReceiptSet.from_events(self.load("pipeline-generic.json"))
        claude = ReceiptSet.from_events(self.load("pipeline-claude.json"))
        report = ShadowComparator().compare_receipt_sets(generic, claude)
        self.assertEqual(report.reason, "explained_host_difference")
        self.assertTrue(report.semantic_match)
        self.assertFalse(report.safe_to_promote)

    def test_same_host_provider_or_reference_mutation_is_unsafe(self):
        original = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        authoritative = ReceiptSet.from_events(translate_pipeline_receipts(original))
        for key, value in (
            ("provider", "openai"),
            ("authoritative_receipt", "receipts/codex/chunk-a-dispatch.json"),
        ):
            mutated = copy.deepcopy(original)
            mutated[2][key] = value
            report = ShadowComparator().compare_receipt_sets(
                ReceiptSet.from_events(translate_pipeline_receipts(mutated)),
                authoritative,
            )
            with self.subTest(key=key):
                self.assertFalse(report.semantic_match)
                self.assertFalse(report.safe_to_promote)
                self.assertEqual(
                    report.reason,
                    "unsafe_to_promote" if key == "provider" else "kernel_prediction_gap",
                )

    def test_routing_cleanup_and_convergence_mutations_are_semantic(self):
        original = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        authoritative = ReceiptSet.from_events(translate_pipeline_receipts(original))
        changes = {
            "attempt": 2, "retry_reason": "browser_restart",
            "isolation_mode": "worktree", "requested_executor": "builder",
            "isolation_strategy": "sequential-on-branch",
            "attempted_executor": "fallback", "cleanup_policy": "stop-remove",
            "resource_kind": "container", "resource_name": "review-box",
            "finding_count": 2, "prior_findings_signature": "prior-signature",
            "convergence_signature": "current-signature",
        }
        for key, value in changes.items():
            mutated = copy.deepcopy(original)
            if key == "isolation_strategy":
                for receipt in mutated:
                    receipt[key] = value
            else:
                mutated[2][key] = value
            report = ShadowComparator().compare_receipt_sets(
                ReceiptSet.from_events(translate_pipeline_receipts(mutated)), authoritative,
            )
            with self.subTest(key=key):
                self.assertFalse(report.semantic_match)
                self.assertFalse(report.safe_to_promote)
        mutated = copy.deepcopy(original)
        for receipt in mutated:
            receipt["workflow_class_defaulted"] = True
        report = ShadowComparator().compare_receipt_sets(
            ReceiptSet.from_events(translate_pipeline_receipts(mutated)), authoritative,
        )
        self.assertFalse(report.semantic_match)


if __name__ == "__main__":
    unittest.main()
