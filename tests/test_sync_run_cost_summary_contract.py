"""Behavioral failure tests for the canonical cost-contract synchronizer."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
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

    def _canonical_values(self, canonical: Path):
        text = canonical.read_text(encoding="utf-8")
        flag = re.search(
            r"^<!-- CANONICAL-INVOCATION-FLAG: (.*) -->$",
            text, re.MULTILINE,
        ).group(1)
        resolution = re.search(
            r"^<!-- CANONICAL-MATRIX-RESOLUTION: (.*) -->$",
            text, re.MULTILINE,
        ).group(1)
        return flag, resolution

    def _invocation_flag_count(self, consumer: Path, flag: str):
        return sum(
            line.count(flag)
            for line in consumer.read_text(encoding="utf-8").splitlines()
            if "emit-cost-summary --events" in line
        )

    def _consumer_bytes(self, root: Path):
        return {
            relative: (root / relative).read_bytes()
            for relative in CONSUMERS
        }

    def _sync_artifacts(self, root: Path):
        return sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob(".sync-rcs*")
        )

    def _install_mv_wrapper(self, root: Path, script: Path, body: str):
        test_bin = root / "test-bin"
        test_bin.mkdir()
        wrapper = test_bin / "mv"
        wrapper.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        wrapper.chmod(0o755)
        script.write_text(
            script.read_text(encoding="utf-8").replace(
                'export PATH="/usr/bin:/bin:/usr/sbin:/sbin"',
                f'export PATH="{test_bin}:/usr/bin:/bin:/usr/sbin:/sbin"',
                1,
            ),
            encoding="utf-8",
        )

    def _inject_failing_mv(self, root: Path, script: Path, fail_on: int):
        count_file = root / "mv-count"
        self._install_mv_wrapper(
            root,
            script,
            f'count_file="{count_file}"\n'
            'count=$(cat "$count_file" 2>/dev/null || printf 0)\n'
            'count=$((count + 1))\n'
            'printf "%s\\n" "$count" > "$count_file"\n'
            f'if [ "$count" -eq {fail_on} ]; then exit 42; fi\n'
            'exec /bin/mv "$@"\n',
        )

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
            self.assertEqual(self._sync_artifacts(root), [])

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

    def test_missing_or_duplicate_invocation_flag_is_repaired_once(self):
        for mutation in ("missing", "duplicate"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                script, canonical = self._fixture(root)
                flag, _resolution = self._canonical_values(canonical)
                consumer = root / CONSUMERS[0]
                text = consumer.read_text(encoding="utf-8")
                if mutation == "missing":
                    text = text.replace(" " + flag, "", 1)
                else:
                    text = text.replace(" " + flag, " " + flag + " " + flag, 1)
                consumer.write_text(text, encoding="utf-8")

                self.assertEqual(subprocess.run(
                    [script, "--check"], capture_output=True, text=True,
                ).returncode, 1)
                self.assertEqual(subprocess.run(
                    [script], capture_output=True, text=True,
                ).returncode, 0)
                self.assertEqual(self._invocation_flag_count(consumer, flag), 1)

    def test_missing_or_duplicate_resolution_line_is_repaired_once(self):
        for mutation in ("missing", "duplicate"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                script, canonical = self._fixture(root)
                _flag, resolution = self._canonical_values(canonical)
                consumer = root / CONSUMERS[0]
                text = consumer.read_text(encoding="utf-8")
                if mutation == "missing":
                    text = text.replace(resolution + "\n", "", 1)
                else:
                    text = text.replace(
                        resolution + "\n",
                        resolution + "\n" + resolution + "\n",
                        1,
                    )
                consumer.write_text(text, encoding="utf-8")

                self.assertEqual(subprocess.run(
                    [script, "--check"], capture_output=True, text=True,
                ).returncode, 1)
                self.assertEqual(subprocess.run(
                    [script], capture_output=True, text=True,
                ).returncode, 0)
                self.assertEqual(
                    consumer.read_text(encoding="utf-8")
                    .splitlines().count(resolution),
                    1,
                )

    def test_missing_repository_commit_marker_fails_without_mutating_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            consumer = root / CONSUMERS[0]
            consumer.write_text(
                consumer.read_text(encoding="utf-8").replace(
                    " --repository-commit HEAD", "", 1,
                ),
                encoding="utf-8",
            )
            before = consumer.read_bytes()

            result = subprocess.run(
                [script], capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("could not generate replacement", result.stderr)
            self.assertEqual(consumer.read_bytes(), before)

    def test_late_prepare_failure_leaves_every_consumer_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            first = root / CONSUMERS[0]
            last = root / CONSUMERS[-1]
            first.write_text(
                first.read_text(encoding="utf-8").replace(
                    "one transaction: it owns", "one transaction: it drifts", 1,
                ),
                encoding="utf-8",
            )
            last.write_text(
                last.read_text(encoding="utf-8").replace(
                    " --repository-commit HEAD", "", 1,
                ),
                encoding="utf-8",
            )
            before = self._consumer_bytes(root)

            result = subprocess.run(
                [script], capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("could not generate replacement", result.stderr)
            self.assertEqual(self._consumer_bytes(root), before)
            self.assertEqual(self._sync_artifacts(root), [])

    def test_commit_move_failure_rolls_back_every_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            for relative in CONSUMERS[:2]:
                consumer = root / relative
                consumer.write_text(
                    consumer.read_text(encoding="utf-8").replace(
                        "one transaction: it owns",
                        "one transaction: it drifts",
                        1,
                    ),
                    encoding="utf-8",
                )
            before = self._consumer_bytes(root)
            self._inject_failing_mv(root, script, fail_on=2)

            result = subprocess.run(
                [script], capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("could not replace", result.stderr)
            self.assertEqual(self._consumer_bytes(root), before)
            self.assertEqual(self._sync_artifacts(root), [])

    def test_signal_after_first_move_rolls_back_and_cleans_own_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            for relative in CONSUMERS[:2]:
                consumer = root / relative
                consumer.write_text(
                    consumer.read_text(encoding="utf-8").replace(
                        "one transaction: it owns",
                        "one transaction: it drifts",
                        1,
                    ),
                    encoding="utf-8",
                )
            before = self._consumer_bytes(root)
            self._install_mv_wrapper(
                root,
                script,
                '/bin/mv "$@" || exit $?\n'
                'kill -TERM "$PPID"\n'
                'exit 0\n',
            )

            result = subprocess.run(
                [script], capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 130)
            self.assertEqual(self._consumer_bytes(root), before)
            self.assertEqual(self._sync_artifacts(root), [])

    def test_concurrent_invocation_fails_closed_without_touching_owner_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script, _canonical = self._fixture(root)
            consumer = root / CONSUMERS[0]
            consumer.write_text(
                consumer.read_text(encoding="utf-8").replace(
                    "one transaction: it owns", "one transaction: it drifts", 1,
                ),
                encoding="utf-8",
            )
            entered = root / "move-entered"
            release = root / "move-release"
            self._install_mv_wrapper(
                root,
                script,
                f'if [ ! -e "{entered}" ]; then\n'
                f'  : > "{entered}"\n'
                f'  while [ ! -e "{release}" ]; do sleep 0.05; done\n'
                'fi\n'
                'exec /bin/mv "$@"\n',
            )
            owner = subprocess.Popen(
                [script], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                while not entered.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(entered.exists(), "owner never reached commit move")

                contender = subprocess.run(
                    [script], capture_output=True, text=True, timeout=5,
                )
                release.touch()
                owner_stdout, owner_stderr = owner.communicate(timeout=5)
            finally:
                release.touch()
                if owner.poll() is None:
                    owner.kill()
                    owner.communicate()

            self.assertEqual(contender.returncode, 2)
            self.assertIn("already running", contender.stderr)
            self.assertEqual(owner.returncode, 0, owner_stdout + owner_stderr)
            self.assertEqual(self._sync_artifacts(root), [])


if __name__ == "__main__":
    unittest.main()
