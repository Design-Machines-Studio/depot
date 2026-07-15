import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import workflow_kernel

from workflow_kernel.model import HostCapabilities, WorkflowClass
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

    def test_translation_works_from_installed_cache_layout_without_repo_ancestor(self):
        """An installed cache has no plugins/pipeline ancestor; the kernel must
        still translate manifests and expand workflow classes from its own
        kernel-owned safety data (finding 061)."""
        real_references = Path(workflow_kernel.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            references = (
                Path(directory) / ".claude" / "plugins" / "cache" / "depot"
                / "workflow-kernel" / "0.1.0" / "skills" / "workflow-kernel"
                / "references"
            )
            shutil.copytree(
                real_references, references,
                ignore=shutil.ignore_patterns("tests", "__pycache__"),
            )
            script = (
                "from workflow_kernel.model import HostCapabilities\n"
                "from workflow_kernel.pipeline_adapter import translate_manifest\n"
                "spec = translate_manifest({\n"
                "    'feature': 'cache-layout', 'workflowClass': 'feature',\n"
                "    'executionMode': 'generic', 'chunks': [],\n"
                "    'changedPaths': ['internal/auth/keys.py'],\n"
                "}, HostCapabilities('generic', frozenset()))\n"
                "assert spec.nodes[-1].node_id == 'cleanup'\n"
                "assert any(\n"
                "    node.routing_reason == 'sensitive_path_override'\n"
                "    for node in spec.nodes if node.executor is not None\n"
                ")\n"
            )
            completed = subprocess.run(
                (sys.executable, "-c", script), cwd=directory, text=True,
                capture_output=True, check=False,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "PYTHONPATH": str(references),
                    "HOME": directory,
                },
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)

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

    def test_runtime_discovery_uses_the_shared_semver_compatibility_rule(self):
        from workflow_kernel.cli import (
            compatible_kernel_version, resolve_workflow_kernel_runtime,
        )
        self.assertEqual(compatible_kernel_version("0.1.0"), (0, 1, 0))
        self.assertEqual(compatible_kernel_version("0.2.0"), (0, 2, 0))
        self.assertEqual(compatible_kernel_version("0.1.10"), (0, 1, 10))
        for incompatible in ("1.0.0", "0.0.9", "0.1", "0.1.0-rc1", 1, None):
            with self.subTest(version=incompatible):
                self.assertIsNone(compatible_kernel_version(incompatible))

        def install(root, cache_name, version, declared=None):
            plugin = (
                root / "home" / cache_name / "plugins" / "cache" / "depot"
                / "workflow-kernel" / version
            )
            package = plugin / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
            package.mkdir(parents=True)
            (package / "__main__.py").write_text("")
            (plugin / ".claude-plugin").mkdir()
            (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({
                "name": "workflow-kernel", "version": declared or version,
            }))
            return package.parent

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "depot" / "plugins" / "pipeline"
            pipeline.mkdir(parents=True)
            # Compatible same-major minor bump is discoverable.
            newer = install(root, ".claude", "0.2.0")
            install(root, ".claude", "0.1.9")
            self.assertEqual(
                resolve_workflow_kernel_runtime(pipeline, home=root / "home"),
                newer.resolve(),
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "depot" / "plugins" / "pipeline"
            pipeline.mkdir(parents=True)
            # Semver order, not lexical or mtime order: 0.1.10 > 0.1.9.
            newest = install(root, ".claude", "0.1.10")
            install(root, ".claude", "0.1.9")
            self.assertEqual(
                resolve_workflow_kernel_runtime(pipeline, home=root / "home"),
                newest.resolve(),
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pipeline = root / "depot" / "plugins" / "pipeline"
            pipeline.mkdir(parents=True)
            # A declared version that mismatches its path segment is rejected.
            install(root, ".claude", "0.1.5", declared="0.1.4")
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

    def test_runtime_trust_serves_any_plugins_sibling_but_rejects_foreign_roots(self):
        # Finding 089: the kernel never hardcodes a consumer allowlist; any
        # plugins/<name> sibling under the same depot boundary resolves, while
        # a path outside a plugins/ directory still fails closed.
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "home" / ".claude" / "plugins" / "cache" / "depot" / "workflow-kernel" / "0.1.0"
            package = plugin / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
            package.mkdir(parents=True)
            (package / "__main__.py").write_text("")
            (plugin / ".claude-plugin").mkdir()
            (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "workflow-kernel", "version": "0.1.0"}))
            future = root / "depot" / "plugins" / "future-orchestrator"
            future.mkdir(parents=True)
            self.assertEqual(
                resolve_workflow_kernel_runtime(future, home=root / "home"),
                package.parent.resolve(),
            )
            foreign = root / "depot" / "not-plugins" / "pipeline"
            foreign.mkdir(parents=True)
            with self.assertRaises(ValueError):
                resolve_workflow_kernel_runtime(foreign, home=root / "home")


if __name__ == "__main__":
    unittest.main()
