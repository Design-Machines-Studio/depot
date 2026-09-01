import json
from pathlib import Path
import unittest

from workflow_kernel.observation_index import validate_observation_index


ROOT = Path(__file__).parents[1]
PIPELINE_COMMAND = ROOT / "plugins" / "pipeline" / "commands" / "pipeline.md"
PIPELINE_RUN = ROOT / "plugins" / "pipeline" / "commands" / "pipeline-run.md"
ORCHESTRATOR = ROOT / "plugins" / "pipeline" / "agents" / "workflow" / "execution-orchestrator.md"
REVIEW_COMMAND = ROOT / "plugins" / "dm-review" / "commands" / "dm-review.md"
REVIEW_SKILL = ROOT / "plugins" / "dm-review" / "skills" / "review" / "SKILL.md"
FIXTURES = ROOT / "tests" / "fixtures" / "observation-index"


class ObservationProducerContractTests(unittest.TestCase):
    def text(self, path):
        return path.read_text(encoding="utf-8")

    def test_pipeline_contract_has_exact_terminal_command_and_binding(self):
        for path, slug in ((PIPELINE_COMMAND, "<feature-slug>"), (PIPELINE_RUN, "<feature>")):
            with self.subTest(path=path):
                text = self.text(path)
                command = (
                    f'"$WORKFLOW_KERNEL" emit-observation-index --input plans/{slug}/observation-index-input.json '
                    f'--output plans/{slug}/observation-index.json'
                )
                self.assertEqual(text.count(command), 1)
                self.assertIn("producer.name", text)
                self.assertIn("pipeline", text)
                self.assertIn("role", text)
                self.assertIn("producer", text)
                self.assertIn("invalid-or-unsafe-input|runtime-unavailable|write-conflict|emission-failed", text)

    def test_orchestrator_preserves_exact_source_handoff_until_caller_emits(self):
        text = self.text(ORCHESTRATOR)
        self.assertIn("Observation index source handoff:", text)
        self.assertIn("after its cost-summary", text)
        self.assertIn("producer.name: pipeline", text)
        self.assertIn("source `role: producer`", text)
        self.assertIn("never\nchanges authoritative completion", text)

    def test_dm_review_uses_same_envelope_for_complete_and_partial_runs(self):
        command = (
            '"$WORKFLOW_KERNEL" emit-observation-index --input '
            '<exact-run-root>/review/observation-index-input.json --output '
            '.claude/ux-review/observation-index-<run-id>.json'
        )
        for path in (REVIEW_COMMAND, REVIEW_SKILL):
            with self.subTest(path=path):
                text = self.text(path)
                self.assertEqual(text.count(command), 1)
                self.assertIn("producer.name", text)
                self.assertIn("dm-review", text)
                self.assertIn("complete", text)
                self.assertIn("partial", text)
                self.assertIn("unavailable", text)
                self.assertIn("raw finding", text.lower())
                self.assertIn("reference-bound", text.lower())
                self.assertIn("validated exact-owned run ID", text)
                self.assertIn("Phase 8 preserves", text)

    def test_dm_review_output_format_links_durable_observation_companion(self):
        output_format = ROOT / "plugins" / "dm-review" / "skills" / "review" / "references" / "output-format.md"
        text = self.text(output_format)
        self.assertIn("Observation index: .claude/ux-review/observation-index-<run-id>.json", text)

    def test_dm_review_run_scoped_outputs_do_not_collide(self):
        template = ".claude/ux-review/observation-index-<run-id>.json"
        first = template.replace("<run-id>", "dm-review-run-1")
        second = template.replace("<run-id>", "dm-review-run-2")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith(".claude/ux-review/observation-index-"))

    def test_complete_and_partial_producer_fixtures_validate(self):
        for name in (
            "pipeline-complete-v1.json", "dm-review-complete-v1.json",
            "dm-review-partial-v1.json",
        ):
            with self.subTest(name=name):
                validate_observation_index(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
