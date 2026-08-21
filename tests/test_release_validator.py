import importlib.util
import json
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "tools").is_dir())
SPEC = importlib.util.spec_from_file_location(
    "validate_workflow_kernel", ROOT / "tools" / "validate-workflow-kernel.py",
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ReleaseValidatorTests(unittest.TestCase):
    def test_real_tracked_authoritative_ledger_is_discoverable(self):
        ledgers = VALIDATOR.tracked_authoritative_receipt_ledgers(VALIDATOR.ROOT)
        self.assertIn(
            VALIDATOR.ROOT / "plans/adaptive-fusion-verification/authoritative-receipts.json",
            ledgers,
        )

    def test_untracked_invalid_receipts_are_excluded_from_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            tracked = repository / "plans/tracked/authoritative-receipts.json"
            ignored = repository / "plans/ignored/authoritative-receipts.json"
            untracked = repository / "plans/untracked/authoritative-receipts.json"
            tracked.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            untracked.parent.mkdir(parents=True)
            tracked.write_text("[]\n")
            ignored.write_text("not-json\n")
            untracked.write_text("not-json\n")
            (repository / ".gitignore").write_text(
                "plans/ignored/authoritative-receipts.json\n"
            )
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(
                ["git", "add", ".gitignore", str(tracked)],
                cwd=repository,
                check=True,
            )
            subprocess.run(
                [
                    "git", "-c", "user.name=Test", "-c",
                    "user.email=test@example.com", "commit", "-qm",
                    "tracked ledger",
                ],
                cwd=repository,
                check=True,
            )

            self.assertEqual(
                VALIDATOR.tracked_authoritative_receipt_ledgers(repository),
                (tracked,),
            )

    def test_discovered_tracked_ledgers_receive_semantic_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            ledger = repository / "plans/invalid/authoritative-receipts.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text('[{"stage": "progress"}]\n')
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            subprocess.run(["git", "add", str(ledger)], cwd=repository, check=True)
            subprocess.run(
                [
                    "git", "-c", "user.name=Test", "-c",
                    "user.email=test@example.com", "commit", "-qm",
                    "invalid tracked ledger",
                ],
                cwd=repository,
                check=True,
            )

            with self.assertRaises(ValueError):
                with mock.patch.object(VALIDATOR, "ROOT", repository):
                    VALIDATOR.check_documents({})

    def test_missing_tracked_ledger_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)

            with self.assertRaisesRegex(
                VALIDATOR.ValidationFailure,
                "checked-in authoritative receipt ledger missing",
            ):
                with mock.patch.object(VALIDATOR, "ROOT", repository):
                    VALIDATOR.check_documents({})

    def test_git_discovery_failure_cannot_look_like_an_empty_success(self):
        failed = subprocess.CompletedProcess(
            args=["git", "ls-files"], returncode=1, stdout=b"", stderr=b"fatal"
        )
        with mock.patch.object(
            VALIDATOR.subprocess, "run", return_value=failed
        ):
            with self.assertRaisesRegex(
                VALIDATOR.ValidationFailure, "Git receipt-ledger discovery failed"
            ):
                VALIDATOR.tracked_authoritative_receipt_ledgers(VALIDATOR.ROOT)

    def test_failure_text_never_republishes_secret_or_raw_exception(self):
        secret = VALIDATOR.SECRET_SENTINEL
        rendered = VALIDATOR.safe_failure_text(RuntimeError(f"broken: {secret}"))
        self.assertNotIn(secret, rendered)
        self.assertNotIn("broken", rendered)
        self.assertIn("value-sha256:", rendered)

    def test_cli_behavior_cases_cover_every_command_without_help_only_probes(self):
        expected = {
            "init", "validate", "append", "replay", "status",
            "decide-validation-retry", "bind-prediction",
            "bind-verification-contract",
            "observe-pipeline", "observe-review", "export-review-contributions",
            "compare", "metrics", "run-cost-summary", "emit-cost-summary",
            "resolve-plugin-asset",
            "openrouter-usage",
            "lane-input-bytes",
            "record-attempt",
            "plan-create", "plan-compose", "record-create", "plan-cleanup",
            "next-cleanup-step", "execute-cleanup-step", "record-cleanup",
            "plan-reconcile",
            "plan-verification", "run-verification",
        }
        self.assertEqual(set(VALIDATOR.BEHAVIORAL_CLI_CASES), expected)
        self.assertEqual(set(VALIDATOR.SUCCESSFUL_CLI_COMMANDS), expected)
        self.assertTrue(all("--help" not in case for case in VALIDATOR.BEHAVIORAL_CLI_CASES.values()))

    def test_schema_inventory_is_exactly_the_released_documents(self):
        expected = {
            "behavioral-verification-contract-schema.json",
            "browser-recovery-schema.json",
            "cleanup-plan-schema.json",
            "cleanup-receipt-schema.json",
            "repository-verification-plan-schema.json",
            "repository-verification-profile-schema.json",
            "repository-verification-result-schema.json",
            "resource-registry-schema.json",
            "run-cost-summary-schema.json",
            "verification-profile-schema.json",
            "workflow-classes-schema.json",
            "workflow-policy-schema.json",
        }
        self.assertEqual(VALIDATOR.SCHEMA_DOCUMENTS, expected)

    def test_promotion_evidence_is_derived_from_completed_checks(self):
        complete = {
            name: True
            for sources in VALIDATOR.PROMOTION_CHECK_SOURCES.values()
            for name in sources
        }
        evidence = VALIDATOR.derive_promotion_evidence(complete)
        self.assertTrue(all(item.satisfied for item in evidence))
        complete["scenario replay"] = False
        evidence = VALIDATOR.derive_promotion_evidence(complete)
        self.assertTrue(any(not item.satisfied for item in evidence))

    def test_default_release_evidence_path_is_deterministic(self):
        self.assertEqual(
            VALIDATOR.DEFAULT_EVIDENCE_OUTPUT,
            ROOT / "plans" / "ai-developer-workflow-kernel" / "receipts" /
            "06-workflow-kernel-release-evidence.json",
        )

    def test_checked_in_closeout_ledger_uses_literal_stages_and_real_artifacts(self):
        ledger_path = (
            ROOT / "plans" / "adaptive-fusion-verification" /
            "authoritative-receipts.json"
        )
        receipts = json.loads(ledger_path.read_text())
        closeout = receipts[-4:]
        self.assertEqual(
            [receipt["stage"] for receipt in closeout],
            [
                "final_dm_review", "requirements_cross_check",
                "terminal_reconciliation", "run_summary",
            ],
        )
        self.assertEqual(
            [receipt["authoritative_receipt"] for receipt in closeout],
            [
                "plans/adaptive-fusion-verification/receipts/final-dm-review.json",
                "plans/adaptive-fusion-verification/final-requirements-crosscheck.md",
                "plans/adaptive-fusion-verification/docker/terminal-current-run-receipt.json",
                "plans/adaptive-fusion-verification/receipt.md",
            ],
        )
        for receipt in closeout:
            self.assertTrue((ROOT / receipt["authoritative_receipt"]).is_file())

    def test_generated_host_compatibility_uses_canonical_host_ids(self):
        context = {}
        VALIDATOR.check_hosts(context)
        from workflow_kernel.shadow import CANONICAL_HOSTS
        self.assertEqual(set(context["host_compatibility"]), CANONICAL_HOSTS)

    def test_canonical_host_ids_have_one_dependency_neutral_owner(self):
        shadow = (VALIDATOR.REFERENCES / "workflow_kernel" / "shadow.py").read_text()
        promotion = (VALIDATOR.REFERENCES / "workflow_kernel" / "promotion.py").read_text()
        self.assertNotIn('"claude-code", "codex", "generic"', shadow)
        self.assertNotIn('"claude-code", "codex", "generic"', promotion)

    def test_docker_scan_catches_split_and_shell_built_broad_cleanup(self):
        cases = (
            'COMMAND = ("docker", "system", "prune")',
            'COMMAND = ["docker", "container", "prune"]',
            'COMMAND = ("docker", kind, "prune")',
            'subprocess.run(" ".join(("docker", "volume", "prune")), shell=True)',
            'os.system("docker " + "network prune")',
            'subprocess.Popen(f"docker {kind} prune", shell=True)',
        )
        for number, source in enumerate(cases, 1):
            with self.subTest(source=source):
                violations = VALIDATOR.docker_safety_violations_from_source(
                    f"injected-{number}.py", source,
                )
                self.assertTrue(violations)

    def test_docker_scan_allows_exact_id_argv_without_shell(self):
        source = 'COMMAND = ("docker", "container", "rm", "exact-id")'
        self.assertEqual(
            VALIDATOR.docker_safety_violations_from_source("safe.py", source),
            (),
        )


if __name__ == "__main__":
    unittest.main()
