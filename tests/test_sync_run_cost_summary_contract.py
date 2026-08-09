"""Behavioral failure tests for the canonical cost-contract synchronizer."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY = Path(__file__).parents[1]
SCRIPT = REPOSITORY / "tools/sync-run-cost-summary-contract.sh"
CANONICAL = (
    REPOSITORY / "plugins/workflow-kernel/skills/workflow-kernel/references"
    / "run-cost-summary-contract.md"
)
CONSUMERS = (
    "plugins/dm-review/skills/review/SKILL.md",
    "plugins/dm-review/commands/dm-review.md",
    "plugins/dm-review/skills/dm-review/SKILL.md",
    "plugins/dm-review/commands/dm-review-loop.md",
    "plugins/dm-review/skills/dm-review-loop/SKILL.md",
    "plugins/dm-review/commands/dm-review-visual.md",
    "plugins/dm-review/skills/dm-review-visual/SKILL.md",
    "plugins/pipeline/commands/pipeline.md",
    "plugins/pipeline/skills/pipeline/SKILL.md",
    "plugins/pipeline/commands/pipeline-run.md",
    "plugins/pipeline/skills/pipeline-run/SKILL.md",
)


class SyncRunCostSummaryContractTests(unittest.TestCase):
    def _fixture(self, root: Path):
        script = root / "tools/sync-run-cost-summary-contract.sh"
        script.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, script)
        canonical = (
            root / "plugins/workflow-kernel/skills/workflow-kernel/references"
            / "run-cost-summary-contract.md"
        )
        canonical.parent.mkdir(parents=True)
        shutil.copy2(CANONICAL, canonical)
        canonical_text = canonical.read_text(encoding="utf-8")
        paragraph = canonical_text.split(
            "<!-- CANONICAL-PARAGRAPH-START -->\n", 1,
        )[1].split("\n<!-- CANONICAL-PARAGRAPH-END -->", 1)[0]
        flag = re.search(
            r"^<!-- CANONICAL-INVOCATION-FLAG: (.*) -->$",
            canonical_text, re.MULTILINE,
        ).group(1)
        resolution = re.search(
            r"^<!-- CANONICAL-MATRIX-RESOLUTION: (.*) -->$",
            canonical_text, re.MULTILINE,
        ).group(1)
        for relative in CONSUMERS:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "before\n"
                + resolution + "\n"
                + "kernel emit-cost-summary --events events --output output "
                + "--receipt receipt " + flag + " --repository-commit HEAD\n"
                + paragraph + "\nafter\n",
                encoding="utf-8",
            )
        return script, canonical

    def test_consumer_mutation_is_detected_then_repeatably_repaired(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            consumer = root / CONSUMERS[0]
            original = consumer.read_text(encoding="utf-8")
            consumer.write_text(
                original.replace(
                    "The `emit-cost-summary` command is one transaction: it owns",
                    "The `emit-cost-summary` command is one transaction: it borrows",
                    1,
                ).replace("--plugin openrouter", "--plugin drifted-provider", 1),
                encoding="utf-8",
            )
            self.assertEqual(subprocess.run(
                [script, "--check"], capture_output=True, text=True,
            ).returncode, 1)
            self.assertEqual(subprocess.run(
                [script], capture_output=True, text=True,
            ).returncode, 0)
            repaired = consumer.read_bytes()
            self.assertEqual(subprocess.run(
                [script], capture_output=True, text=True,
            ).returncode, 0)
            self.assertEqual(consumer.read_bytes(), repaired)
            self.assertEqual(subprocess.run(
                [script, "--check"], capture_output=True, text=True,
            ).returncode, 0)

    def test_invalid_canonical_markers_fail_without_mutating_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, canonical = self._fixture(root)
            consumer = root / CONSUMERS[0]
            before = consumer.read_bytes()
            canonical.write_text(
                canonical.read_text(encoding="utf-8").replace(
                    "<!-- CANONICAL-PARAGRAPH-END -->", "", 1,
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [script], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("exactly one start and one end marker", result.stderr)
            self.assertEqual(consumer.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
