"""Contract checks for generated Codex command-skill adapters.

These assertions keep the shared adapter policy from drifting. They are not a
behavioral substitute for the isolated fresh-session canary.
"""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_codex_command_skills",
    REPO / "tools/generate-codex-command-skills.py",
)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class CodexCommandAdapterContractTests(unittest.TestCase):
    def generated(self, plugin: str, command: str) -> str:
        path = REPO / "plugins" / plugin / "commands" / f"{command}.md"
        return GENERATOR.generated_skill(path)

    def test_dm_review_uses_installed_inline_workflow_and_router_receipts(self) -> None:
        alias = self.generated("dm-review", "dm-review")
        self.assertIn("execute in **Full** mode", alias)
        for required in (
            "workflow entrypoint",
            "current Codex harness",
            "host-selected coherent installed bundle",
            "when no generic Skill tool exists",
            "use required model-router role-dispatch and retain its outputs and receipts",
            "Use native subagents only when that workflow explicitly permits them",
            "Do not launch another harness solely for its source or cache format",
            "Explicit cross-harness requests and router-selected participant transports remain supported",
            "never manual-substitute required lanes or fabricate receipts",
            "## Command Workflow",
        ):
            with self.subTest(required=required):
                self.assertIn(required, alias)
        self.assertNotIn("Embedded Claude Command", alias)

    def test_pipeline_keeps_its_explicit_native_mechanism(self) -> None:
        main_alias = self.generated("pipeline", "pipeline")
        self.assertIn("current Codex harness", main_alias)
        self.assertIn("Codex runs its installed workflow in-session", main_alias)
        alias = self.generated("pipeline", "pipeline-run")
        self.assertIn("Use native subagents only when that workflow explicitly permits them", alias)
        self.assertIn("codex-native-execution-adapter.md", alias)
        adapter = (REPO / "plugins/pipeline/references/codex-native-execution-adapter.md").read_text()
        self.assertIn("role-dispatch.sh", adapter)

    def test_nested_review_owners_are_explicit(self) -> None:
        loop = (REPO / "plugins/dm-review/commands/dm-review-loop.md").read_text()
        repair = (REPO / "plugins/dm-review/commands/dm-review-fix.md").read_text()
        quick = (REPO / "plugins/dm-review/commands/dm-review-quick.md").read_text()
        full = (REPO / "plugins/dm-review/commands/dm-review.md").read_text()
        self.assertIn('terminalModelReportOwner = "dm-review-loop"', loop)
        self.assertIn("Nested commands MUST NOT re-default, infer, or change the class.", loop)
        self.assertIn("Run /dm-review-fix for required_finding_files only", loop)
        self.assertIn("already owned by\nPipeline or dm-review-loop", quick)
        self.assertIn("reuse the\nloop's single terminal report", quick)
        self.assertIn("Nested reviews return findings to their repair\nowner without recursion.", full)
        self.assertIn("Fix pending review findings", repair)

    def test_review_kernel_commands_use_the_initialized_state_directory(self) -> None:
        sources = (
            "plugins/dm-review/commands/dm-review.md",
            "plugins/dm-review/commands/dm-review-loop.md",
            "plugins/dm-review/commands/dm-review-visual.md",
            "plugins/dm-review/skills/review/SKILL.md",
            "plugins/dm-review/skills/review/references/review-docker-create.md",
            "plugins/dm-review/skills/review/references/review-docker-cleanup.md",
        )
        for source in sources:
            with self.subTest(source=source):
                content = (REPO / source).read_text()
                self.assertNotIn("--state-dir <exact-run-root>/review", content)
                self.assertIn("--state-dir .workflow-kernel/runs/<run-id>", content)
        review = (REPO / "plugins/dm-review/skills/review/SKILL.md").read_text()
        self.assertIn("init .workflow-kernel/runs/<run-id>", review)
        self.assertIn("Produce nonempty independent `review_request` prediction receipts", review)

    def test_review_before_publication_and_owner_only_merge_contract(self) -> None:
        direct = (REPO / "plugins/dm-review/skills/review/references/automatic-implementation-closeout.md").read_text()
        pipeline = (REPO / "plugins/pipeline/commands/pipeline.md").read_text()
        full = (REPO / "plugins/pipeline/agents/workflow/execution-orchestrator.md").read_text()
        adapter = (REPO / "plugins/pipeline/references/codex-native-execution-adapter.md").read_text()
        schema = (REPO / "plugins/pipeline/skills/promptcraft/references/manifest-schema.md").read_text()
        prompt = (REPO / "plugins/pipeline/skills/promptcraft/references/prompt-template.md").read_text()
        self.assertIn('"noMergeOnCompletion": true', schema)
        for text in (pipeline, full, adapter, prompt):
            with self.subTest(surface=text.splitlines()[0]):
                self.assertIn("noMergeOnCompletion=true", text)
                self.assertIn("publish-reviewed-pr.sh", text)
                self.assertIn("read-only", text)
        self.assertNotIn('default `false`', full)
        self.assertNotIn('**If `false`:** proceed', full)
        self.assertNotIn('Recommended next action: create the PR', pipeline)
        self.assertNotIn('**If the user chooses PR:**', pipeline)
        self.assertLess(full.index('## Step 4: Approved Final Review'), full.index('<!-- reviewed-pr-full:start -->'))
        self.assertLess(pipeline.index('### Caller Verification Checklist'), pipeline.index('<!-- reviewed-pr-lean:start -->'))
        self.assertLess(pipeline.index('**Requirements cross-check (ledger item 11):**'), pipeline.index('<!-- reviewed-pr-lean:start -->'))
        self.assertIn('The orchestrator defers create and ready', pipeline)
        self.assertIn('Both Full and Lean modes invoke', pipeline)
        for operation in ('full', 'full-ready'):
            snippet = full.split(f'<!-- reviewed-pr-{operation}:start -->')[1].split(f'<!-- reviewed-pr-{operation}:end -->')[0]
            self.assertLess(snippet.index('pipeline) printf'), snippet.index('pipeline-run)'))
            self.assertLess(snippet.index('pipeline-run)'), snippet.index('publish-reviewed-pr.sh'))
            self.assertIn('*) exit 2', snippet)
        for operation in ('lean', 'lean-ready'):
            snippet = pipeline.split(f'<!-- reviewed-pr-{operation}:start -->')[1].split(f'<!-- reviewed-pr-{operation}:end -->')[0]
            self.assertLess(snippet.index('CALLER_VERIFICATION_PASSED:-false'), snippet.index('publish-reviewed-pr.sh'))
        for text in (pipeline, full, adapter):
            self.assertIn('TERMINAL_MODEL_REPORT_OWNER', text)
        self.assertIn('`pipeline` defers both create and ready', adapter)
        self.assertIn('`pipeline-run` executes Step 4c', adapter)
        self.assertLess(direct.index('Independently review,'), direct.index('<!-- reviewed-pr-direct:start -->'))
        for caller, text in (("direct", direct), ("full", full), ("lean", pipeline)):
            with self.subTest(caller=caller):
                for operation in ("create", "ready"):
                    self.assertIn(f'--operation {operation} --repository-root "$REVIEW_ROOT" --run-root "$REVIEW_RUN_ROOT"', text)
                self.assertIn('not_applicable', text)
                self.assertIn(f'<!-- review-gap-{caller}:start -->', text)
                self.assertIn('hook activation unavailable', text)
                self.assertNotRegex(text, r"(?m)^\s*gh pr (create|ready|merge)(?: |$)")
        self.assertIn('rebind', direct.lower())
        self.assertIn('SessionStart/Stop', direct)
        self.assertIn('private ownership, single-link containment', direct)
        self.assertIn('never bind/update/clear', direct)

    def test_handoff_check_schema_matches_documented_runtime_statuses(self) -> None:
        refs = REPO / "plugins/dm-review/skills/review/references"
        doc = (refs / "output-format.md").read_text()
        runtime = (refs / "operator-handoff.sh").read_text()
        documented = re.search(r"Nonempty `checks`:.*?`status`\s*\(`([^`]+)`\)", doc, re.S)
        supported = re.search(r'\(\.name \| str\) and \(\.status \| IN\(([^)]+)\)\)', runtime)
        self.assertIsNotNone(documented)
        self.assertIsNotNone(supported)
        self.assertEqual(set(documented.group(1).split("|")), set(re.findall(r'"([^"\n]+)"', supported.group(1))))
        checks_doc = doc.split("- Nonempty `checks`:", 1)[1].split("- `ui`:", 1)[0]
        for rule in ("optional", "`required`", "Omitted/null defaults to required", "`stage: pr`", "non-null evidence link", "block readiness unless `required: false`"):
            self.assertIn(rule, checks_doc)

    def test_aliases_retain_canonical_command_bodies(self) -> None:
        expected = GENERATOR.expected_files()
        self.assertEqual(36, len(expected))
        self.assertIn("## Command Workflow", (REPO / "plugins/project-manager/skills/agent-board/SKILL.md").read_text())
        for command in ("dm-review", "dm-review-quick", "dm-review-loop", "pipeline"):
            path = REPO / "plugins" / ("pipeline" if command == "pipeline" else "dm-review") / "skills" / command / "SKILL.md"
            self.assertIn("## Command Workflow", path.read_text())


if __name__ == "__main__":
    unittest.main()
