import ast
import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import workflow_kernel
from workflow_kernel import inspection


ROOT = Path(__file__).resolve().parents[1]


class ReviewFixContractTests(unittest.TestCase):
    def test_quality_pulse_summary_binds_trend_before_rendering(self):
        skill = (
            ROOT / "plugins/dm-review/skills/quality-pulse/SKILL.md"
        ).read_text()
        workflow = skill.split("## Workflow", 1)[1].split("### 1.", 1)[0]
        self.assertLess(
            workflow.index("compare compatible trend"),
            workflow.index("render Markdown"),
        )

    def test_output_contract_explains_markdown_staleness_plainly(self):
        contract = (
            ROOT
            / "plugins/dm-review/skills/quality-pulse/references/output-contract.md"
        ).read_text()
        self.assertIn(
            "without making the Markdown stale when publication status changes",
            contract,
        )

    def test_authoritative_validator_is_a_short_coordinator(self):
        source_lines, start = inspect.getsourcelines(
            inspection.validate_authoritative_result,
        )
        self.assertLessEqual(
            len(source_lines),
            80,
            f"validate_authoritative_result starts at line {start}",
        )

    def test_package_root_exports_only_stable_inspection_facade(self):
        for name in (
            "SubprocessAdapter",
            "execute_inspection_lanes",
            "classify_observations",
            "normalize_owned_path",
            "build_authoritative_result",
            "stable_projection",
            "validate_host_attestation",
            "load_host_attestation",
        ):
            self.assertNotIn(name, workflow_kernel.__all__)
            self.assertFalse(hasattr(workflow_kernel, name))
            self.assertNotIn(name, inspection.__all__)

    def test_kernel_docker_controls_are_fixed_and_digest_bound(self):
        lane = {
            "argv": [
                "docker",
                "run",
                "--rm",
                "example/tool@sha256:" + "1" * 64,
            ],
            "image_identity": "example/tool@sha256:" + "1" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = inspection._execution_argv(lane, root, root / "evidence")
        for expected in (
            "--pids-limit=256",
            "--memory=1g",
            "--cpus=2",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
        ):
            self.assertIn(expected, argv)
        digest_source = inspect.getsource(inspection._execution_policy_digest)
        for policy_key in (
            "pids_limit",
            "memory",
            "cpus",
            "capabilities",
            "no_new_privileges",
        ):
            self.assertIn(policy_key, digest_source)

    def test_publication_command_is_a_thin_adapter(self):
        cli_path = (
            ROOT
            / "plugins/workflow-kernel/skills/workflow-kernel/references"
            / "workflow_kernel/cli.py"
        )
        module = ast.parse(cli_path.read_text())
        command = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "command_inspection_publish"
        )
        self.assertLessEqual(len(command.body), 4)
        self.assertIn("publish_authoritative_result", ast.unparse(command))

    def test_artifact_snapshot_rejects_symlink_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir()
            destination.chmod(0o700)
            private = root / "private.txt"
            private.write_text("private")
            (source / "HANDOFF.md").symlink_to(private)
            with self.assertRaises(inspection.InspectionError) as caught:
                inspection.snapshot_regular_files(
                    source,
                    destination,
                    ("HANDOFF.md",),
                )
        self.assertEqual(caught.exception.reason_code, "snapshot_source_invalid")

    def test_snapshot_cli_copies_exact_regular_file_bytes(self):
        launcher = (
            ROOT
            / "plugins/workflow-kernel/skills/workflow-kernel/references"
            / "workflow-kernel-launcher.sh"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            destination.mkdir(mode=0o700)
            payload = b"handoff bytes\n"
            (source / "HANDOFF.md").write_bytes(payload)
            result = subprocess.run(
                [
                    launcher,
                    "snapshot-files",
                    "--source-root",
                    source,
                    "--destination-root",
                    destination,
                    "--name",
                    "HANDOFF.md",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["files"][0]["size"],
                len(payload),
            )
            self.assertEqual((destination / "HANDOFF.md").read_bytes(), payload)

    def test_kernel_info_compares_semver_minimums(self):
        launcher = (
            ROOT
            / "plugins/workflow-kernel/skills/workflow-kernel/references"
            / "workflow-kernel-launcher.sh"
        )
        for minimum, expected in (
            ("0.3.0", 0),
            ("0.5.0", 0),
            ("0.5.1", 2),
            ("not-semver", 2),
        ):
            with self.subTest(minimum=minimum):
                result = subprocess.run(
                    [
                        launcher,
                        "kernel-info",
                        "--minimum-version",
                        minimum,
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_airlift_delegation_uses_trusted_snapshot_command(self):
        for relative in (
            "plugins/airlift/commands/airlift-in.md",
            "plugins/airlift/prompts/airlift-in.md",
            "plugins/airlift/skills/airlift-in/SKILL.md",
        ):
            surface = (ROOT / relative).read_text()
            delegation = surface.split("SNAPSHOT_DIR=", 1)[1]
            self.assertIn(
                '"$WORKFLOW_KERNEL" snapshot-files',
                delegation,
                relative,
            )
            self.assertNotIn('cp "$RESUME_FILE"', delegation, relative)

    def test_dm_review_owns_fail_closed_result_policy(self):
        from tests.test_quality_pulse_kernel import result_policy_document

        schema = json.loads((
            ROOT
            / "plugins/workflow-kernel/skills/workflow-kernel/references"
            / "inspection-profile-schema.json"
        ).read_text())
        self.assertNotIn("result_policy", schema["properties"])
        asset = json.loads((
            ROOT
            / "plugins/dm-review/skills/quality-pulse/references"
            / "result-policy-v1.json"
        ).read_text())
        self.assertEqual(asset, result_policy_document())
        self.assertEqual(
            set(asset["lane_gap_statuses"]),
            {"unavailable", "failed"},
        )
        self.assertEqual(
            set(asset["lane_blocker_statuses"]),
            {"unavailable", "failed"},
        )
        self.assertEqual(
            set(asset["observation_blocker_evidence_statuses"]),
            {"unavailable", "failed", "skipped"},
        )
        inspection.validate_result_policy(asset)

    def test_result_completion_labels_are_workflow_policy_owned(self):
        from tests.test_quality_pulse_kernel import (
            profile_document,
            result_policy_document,
        )

        document = profile_document()
        policy_document = result_policy_document()
        policy_document["completion_labels"]["clean"] = "healthy"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("src").mkdir()
            profile = inspection.validate_inspection_profile(document, root)
            policy = inspection.validate_result_policy(policy_document)
            state = inspection._derive_result_state(
                profile,
                policy,
                [],
                [],
                {
                    "purpose": "repository-audit",
                    "selected_lane_ids": [],
                },
            )
        self.assertEqual(state["completion_state"], "healthy")


if __name__ == "__main__":
    unittest.main()
