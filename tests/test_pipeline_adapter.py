import json
import copy
import unittest
from pathlib import Path

from workflow_kernel.model import BuilderOutcome, BuilderSessionDecision, HostCapabilities, HostCapability, ResumeStateContext, WorkflowClass
from workflow_kernel.pipeline_adapter import translate_builder_decision, translate_manifest, translate_pipeline_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class PipelineAdapterTests(unittest.TestCase):
    def profile(self):
        return HostCapabilities("codex", frozenset())

    def manifest(self, workflow_class="feature"):
        result = {
            "feature": "Pipeline 1", "executionMode": "codex_native",
            "changedPaths": ["src/app.py"],
            "chunks": [
                {"id": "chunk-b", "dependsOn": ["chunk-a"]},
                {"id": "chunk-a", "dependsOn": []},
            ],
            "executionPlan": {"levels": [
                {"level": 0, "strategy": "sequential", "chunks": ["chunk-b"]},
                {"level": 1, "strategy": "sequential", "chunks": ["chunk-a"]},
            ]},
        }
        if workflow_class is not None:
            result["workflowClass"] = workflow_class
        return result

    def test_recomputes_levels_from_authoritative_chunks_and_reports_cached_disagreement(self):
        spec = translate_manifest(self.manifest(), self.profile())
        self.assertEqual(spec.run_id, "pipeline-1")
        self.assertEqual(spec.execution_levels, (("chunk-a",), ("chunk-b",)))
        self.assertTrue(spec.execution_plan_disagreement)
        self.assertEqual(tuple(chunk.node_id for chunk in spec.chunks), ("chunk-b", "chunk-a"))

    def test_checked_in_manifest_translates_with_canonical_feature_and_object_plan(self):
        root = next(parent for parent in Path(__file__).parents if (parent / "plans" / "ai-developer-workflow-kernel" / "manifest.json").is_file())
        manifest = json.loads((root / "plans" / "ai-developer-workflow-kernel" / "manifest.json").read_text())
        spec = translate_manifest(manifest, self.profile())
        self.assertEqual(spec.run_id, "ai-developer-workflow-kernel")
        self.assertEqual(len(spec.execution_levels), 5)
        self.assertFalse(spec.execution_plan_disagreement)

    def test_run_spec_dict_retains_policy_and_gate_fields(self):
        encoded = translate_manifest(self.manifest("security"), self.profile()).to_dict()
        self.assertEqual(encoded["workflow_class"], "security")
        self.assertEqual(encoded["execution_mode"], "codex_native")
        for node in encoded["nodes"]:
            self.assertIn("gate_decision", node)
            self.assertIn("required_capability", node)
            self.assertIn("required_dispatch_capability", node)
            self.assertIn("executor_overridable", node)

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

    def test_receipts_require_one_run_contiguous_order_and_context_continuity(self):
        original = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        mutations = []
        duplicate = copy.deepcopy(original); duplicate[1]["sequence"] = 0; mutations.append(duplicate)
        gap = copy.deepcopy(original); gap[1]["sequence"] = 2; mutations.append(gap)
        reordered = copy.deepcopy(original); reordered[0], reordered[1] = reordered[1], reordered[0]; mutations.append(reordered)
        mixed_run = copy.deepcopy(original); mixed_run[-1]["run_id"] = "other"; mutations.append(mixed_run)
        mixed_class = copy.deepcopy(original); mixed_class[-1]["workflow_class"] = "bug"; mutations.append(mixed_class)
        mixed_mode = copy.deepcopy(original); mixed_mode[-1]["execution_mode"] = "codex_native"; mutations.append(mixed_mode)
        for receipts in mutations:
            with self.subTest(receipts=receipts[:2]), self.assertRaises(ValueError):
                translate_pipeline_receipts(receipts)

    def test_receipts_validate_workflow_class_and_preserve_default_provenance(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        invalid = copy.deepcopy(receipts)
        for receipt in invalid:
            receipt["workflow_class"] = "not-a-workflow-class"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(invalid)
        legacy = copy.deepcopy(receipts)
        for receipt in legacy:
            receipt.pop("workflow_class", None)
        events = translate_pipeline_receipts(legacy)
        self.assertTrue(all(event.payload["workflow_class_defaulted"] for event in events))
        self.assertTrue(all(event.payload["workflow_class"] == "feature" for event in events))
        explicit = copy.deepcopy(receipts)
        for receipt in explicit:
            receipt["workflow_class_defaulted"] = True
        events = translate_pipeline_receipts(explicit)
        self.assertTrue(all(event.payload["workflow_class_defaulted"] for event in events))
        explicit[2]["workflow_class_defaulted"] = "true"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(explicit)

    def test_receipt_redaction_preserves_safe_routing_facts_and_drops_secret_shapes(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2].update({
            "requested_provider": "claude", "attempted_provider": "claude",
            "implemented_by": "claude", "fallback_path": ["claude"],
            "lane": "builder", "password": "never-show", "authorization": "Bearer never-show",
        })
        event = translate_pipeline_receipts(receipts)[2]
        self.assertEqual(event.payload["requested_provider"], "claude")
        self.assertEqual(event.payload["implemented_by"], "claude")
        self.assertNotIn("password", event.payload)
        self.assertNotIn("authorization", event.payload)
        self.assertNotIn("never-show", repr(event.payload))

    def test_documented_camelcase_receipt_fields_are_preserved_not_dropped(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2].update({
            "requestedProvider": "claude", "attemptedProvider": "openrouter",
            "implementedBy": "claude", "fallbackReason": "provider_unavailable",
        })
        event = translate_pipeline_receipts(receipts)[2]
        self.assertEqual(event.payload["requested_provider"], "claude")
        self.assertEqual(event.payload["attempted_provider"], "openrouter")
        self.assertEqual(event.payload["implemented_by"], "claude")
        self.assertEqual(event.payload["fallback_reason"], "provider_unavailable")
        self.assertNotIn("requestedProvider", event.payload)
        agreeing = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        agreeing[2].update({
            "requestedProvider": "claude", "requested_provider": "claude",
        })
        self.assertEqual(
            translate_pipeline_receipts(agreeing)[2].payload["requested_provider"],
            "claude",
        )
        conflicting = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        conflicting[2].update({
            "requestedProvider": "claude", "requested_provider": "openrouter",
        })
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)

    def test_manifest_dual_keys_are_camel_primary_and_reject_conflicts(self):
        snake = self.manifest()
        snake["workflow_class"] = snake.pop("workflowClass")
        snake["execution_mode"] = snake.pop("executionMode")
        snake["changed_paths"] = snake.pop("changedPaths")
        spec = translate_manifest(snake, self.profile())
        self.assertEqual(spec.execution_mode, "codex_native")
        self.assertEqual(spec.workflow_class.value, "feature")
        conflicting = self.manifest()
        conflicting["execution_mode"] = "generic"
        with self.assertRaises(ValueError):
            translate_manifest(conflicting, self.profile())

    def test_hostile_mapping_callbacks_are_rejected_without_invocation(self):
        class Hostile(dict):
            def get(self, *_args, **_kwargs):
                raise AssertionError("callback invoked")
        with self.assertRaises(ValueError):
            translate_manifest(Hostile(self.manifest()), self.profile())
        with self.assertRaises(ValueError):
            translate_pipeline_receipts((Hostile(),))

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
