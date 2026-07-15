import json
import unittest
from pathlib import Path

from workflow_kernel.adapters.base import BuilderOutcome, BuilderSessionDecision, HostCapabilities, HostCapability, ResumeStateContext, WorkflowClass
from workflow_kernel.pipeline_adapter import translate_builder_decision, translate_manifest, translate_pipeline_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class PipelineAdapterTests(unittest.TestCase):
    def profile(self):
        return HostCapabilities("codex", frozenset())

    def manifest(self, workflow_class="feature"):
        result = {
            "runId": "pipeline-1", "executionMode": "codex_native",
            "changedPaths": ["src/app.py"],
            "chunks": [
                {"id": "chunk-b", "dependsOn": ["chunk-a"]},
                {"id": "chunk-a", "dependsOn": []},
            ],
            "executionPlan": [["chunk-b"], ["chunk-a"]],
        }
        if workflow_class is not None:
            result["workflowClass"] = workflow_class
        return result

    def test_recomputes_levels_from_authoritative_chunks_and_reports_cached_disagreement(self):
        spec = translate_manifest(self.manifest(), self.profile())
        self.assertEqual(spec.execution_levels, (("chunk-a",), ("chunk-b",)))
        self.assertTrue(spec.execution_plan_disagreement)
        self.assertEqual(tuple(chunk.node_id for chunk in spec.chunks), ("chunk-b", "chunk-a"))

    def test_all_workflow_classes_and_legacy_default_survive_translation(self):
        for value in ("chore", "bug", "feature", "hotfix", "security", "investigation", "migration"):
            with self.subTest(value=value):
                spec = translate_manifest(self.manifest(value), self.profile())
                self.assertEqual(spec.workflow_class, WorkflowClass(value))
                self.assertFalse(spec.workflow_class_defaulted)
                self.assertTrue(spec.nodes)
        legacy = translate_manifest(self.manifest(None), self.profile())
        self.assertEqual(legacy.workflow_class, WorkflowClass.FEATURE)
        self.assertTrue(legacy.workflow_class_defaulted)
        with self.assertRaises(ValueError):
            translate_manifest(self.manifest("unknown"), self.profile())

    def test_pipeline_receipts_map_named_stages_and_keep_authoritative_refs(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        events = translate_pipeline_receipts(receipts)
        self.assertEqual(len(events), len(receipts))
        self.assertEqual([event.payload["stage"] for event in events], [item["stage"] for item in receipts])
        self.assertTrue(all(event.kind == "evidence.recorded" for event in events))
        self.assertTrue(all(event.payload["authoritative_receipt"] in event.payload["evidence"] for event in events))

    def test_receipt_without_authoritative_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(({"run_id": "r", "sequence": 0, "stage": "run_summary", "status": "succeeded", "occurred_at": "2026-07-14T00:00:00Z"},))

    def test_builder_decision_is_observation_only_and_requires_authoritative_receipt(self):
        context = ResumeStateContext("run-1", "build", "attempt-1", "anthropic", "native", HostCapability.CLAUDE_EXECUTION)
        decision = BuilderSessionDecision(BuilderOutcome.NODE_GATE_BLOCKED, context)
        with self.assertRaises(ValueError):
            translate_builder_decision(decision, authoritative_receipt_reference="", sequence=3, occurred_at="2026-07-14T00:00:00Z")
        event = translate_builder_decision(decision, authoritative_receipt_reference="receipts/builder.json", sequence=3, occurred_at="2026-07-14T00:00:00Z")
        self.assertEqual(event.kind, "evidence.recorded")
        self.assertEqual(event.node_id, "build")
        self.assertIn("receipts/builder.json", event.payload["evidence"])
        self.assertIn("builder-observation/dispatch-blocked", event.payload["evidence"])


if __name__ == "__main__":
    unittest.main()
