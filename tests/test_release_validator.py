import importlib.util
import unittest
from pathlib import Path


ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "tools").is_dir())
SPEC = importlib.util.spec_from_file_location(
    "validate_workflow_kernel", ROOT / "tools" / "validate-workflow-kernel.py",
)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ReleaseValidatorTests(unittest.TestCase):
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
            "bind-verification-contract", "revise-verification-contract",
            "observe-pipeline", "observe-review", "compare", "metrics",
            "plan-create", "plan-compose", "record-create", "plan-cleanup",
            "next-cleanup-step", "execute-cleanup-step", "record-cleanup",
            "plan-reconcile",
            "verification-plan", "verification-run", "verification-result",
            "evidence-match", "artifact-classify", "staging-allowlist",
            "browser-scenario-validate", "browser-bundle-record", "review-record",
            "ci-evidence-normalize", "closeout-audit", "improvement-index",
            "improvement-finalize", "improvement-render",
        }
        self.assertEqual(set(VALIDATOR.BEHAVIORAL_CLI_CASES), expected)
        self.assertEqual(set(VALIDATOR.SUCCESSFUL_CLI_COMMANDS), expected)
        self.assertEqual(set(VALIDATOR.BEHAVIORAL_CLI_EXITS), expected)
        self.assertEqual(
            VALIDATOR.DETERMINISTIC_CLI_COMMANDS,
            expected - {
                "init", "validate", "append", "replay", "status",
                "decide-validation-retry", "bind-prediction",
                "bind-verification-contract", "revise-verification-contract",
                "observe-pipeline", "observe-review", "compare", "metrics",
                "plan-create", "plan-compose", "record-create", "plan-cleanup",
                "next-cleanup-step", "execute-cleanup-step", "record-cleanup",
                "plan-reconcile", "verification-run",
            },
        )
        self.assertEqual(
            {value for command, value in VALIDATOR.BEHAVIORAL_CLI_EXITS.items()
             if command not in {"init", "validate", "append", "replay", "status",
                                "plan-cleanup"}},
            {2},
        )
        self.assertTrue(all("--help" not in case for case in VALIDATOR.BEHAVIORAL_CLI_CASES.values()))

    def test_schema_inventory_is_exactly_the_twenty_two_released_documents(self):
        expected = {
            "artifact-classification-schema.json",
            "behavioral-verification-contract-schema.json",
            "browser-evidence-bundle-schema.json",
            "browser-recovery-schema.json",
            "browser-scenario-schema.json",
            "ci-evidence-schema.json",
            "cleanup-plan-schema.json",
            "cleanup-receipt-schema.json",
            "closeout-audit-schema.json",
            "evidence-binding-schema.json",
            "improvement-input-index-schema.json",
            "improvement-report-schema.json",
            "repository-verification-profile-schema.json",
            "resource-registry-schema.json",
            "review-finding-record-schema.json",
            "review-lane-record-schema.json",
            "staging-allowlist-schema.json",
            "verification-plan-schema.json",
            "verification-profile-schema.json",
            "verification-result-schema.json",
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
