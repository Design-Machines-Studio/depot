import json
import tempfile
import unittest
from pathlib import Path

from workflow_kernel.adapters.base import HostCapabilities, WorkflowClass
from workflow_kernel.pipeline_adapter import translate_manifest, translate_pipeline_receipts
from workflow_kernel.shadow import ReceiptSet, ShadowComparator


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class CompatibilityTests(unittest.TestCase):
    def test_claude_codex_and_generic_receipts_have_equal_semantics(self):
        documents = []
        for host in ("claude", "codex", "generic"):
            events = translate_pipeline_receipts(json.loads((FIXTURES / f"pipeline-{host}.json").read_text()))
            documents.append(ReceiptSet.from_events(events))
        for candidate in documents[1:]:
            report = ShadowComparator().compare_receipt_sets(candidate, documents[0])
            self.assertTrue(report.semantic_match)
            self.assertEqual(report.reason, "explained_host_difference")
            self.assertFalse(report.safe_to_promote)

    def test_every_workflow_class_expands_for_every_supported_host(self):
        for host in ("claude", "codex", "generic"):
            profile = HostCapabilities(host, frozenset())
            for workflow_class in WorkflowClass:
                with self.subTest(host=host, workflow_class=workflow_class.value):
                    spec = translate_manifest({
                        "feature": f"compat-{host}-{workflow_class.value}",
                        "workflowClass": workflow_class.value,
                        "executionMode": "generic", "chunks": [],
                    }, profile)
                    self.assertEqual(spec.workflow_class, workflow_class)
                    self.assertEqual(spec.nodes[-1].node_id, "cleanup")

    def test_missing_runtime_can_fall_back_without_changing_shadow_default(self):
        from workflow_kernel.schema import RunMode
        self.assertEqual(RunMode.SHADOW.value, "shadow")
        self.assertNotIn("native_default", {mode.value for mode in RunMode})

    def test_runtime_trust_rejects_project_shadow_symlink_wrong_name_and_incompatible_version(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            depot = root / "depot"
            pipeline = depot / "plugins" / "pipeline"
            pipeline.mkdir(parents=True)
            forged = root / "project" / "plugins" / "workflow-kernel"
            forged.mkdir(parents=True)
            escaped = root / "escape"
            (escaped / "skills" / "workflow-kernel" / "references" / "workflow_kernel").mkdir(parents=True)
            (escaped / "skills" / "workflow-kernel" / "references" / "workflow_kernel" / "__main__.py").write_text("")
            (depot / "plugins" / "workflow-kernel").symlink_to(escaped, target_is_directory=True)
            for cache_name, version, plugin_name in (
                (".claude", "1.0.0", "workflow-kernel"),
                (".codex", "0.1.9", "wrong-name"),
            ):
                plugin = root / "home" / cache_name / "plugins" / "cache" / "depot" / "workflow-kernel" / version
                package = plugin / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
                package.mkdir(parents=True)
                (package / "__main__.py").write_text("")
                (plugin / ".claude-plugin").mkdir()
                (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": plugin_name, "version": version}))
            with self.assertRaises(FileNotFoundError):
                resolve_workflow_kernel_runtime(pipeline, home=root / "home")

    def test_runtime_trust_accepts_both_supported_cache_roots_deterministically(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        for cache_name in (".claude", ".codex"):
            with self.subTest(cache_name=cache_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                pipeline = root / "depot" / "plugins" / "pipeline"
                pipeline.mkdir(parents=True)
                plugin = root / "home" / cache_name / "plugins" / "cache" / "depot" / "workflow-kernel" / "0.1.0"
                package = plugin / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
                package.mkdir(parents=True)
                (package / "__main__.py").write_text("")
                (plugin / ".claude-plugin").mkdir()
                (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "workflow-kernel", "version": "0.1.0"}))
                self.assertEqual(resolve_workflow_kernel_runtime(pipeline, home=root / "home"), package.parent.resolve())


if __name__ == "__main__":
    unittest.main()
