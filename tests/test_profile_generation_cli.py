"""Supported profile generation, exact selection and immutable binding."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import KERNEL_REFERENCES
from tests.test_runtime_cli import verification_contract
from workflow_kernel import behavioral_contract, cli
from workflow_kernel.adapters.personas import ProjectPersonaAdapter
from workflow_kernel.policies import load_policy
from workflow_kernel.schema import InvalidSchemaError


FIXTURE = Path(__file__).parent / "fixtures/ux/assembly"
LAUNCHER = KERNEL_REFERENCES / "workflow-kernel-launcher.sh"
SECRET = "sk-profile-secret-must-not-survive"


class ProfileGenerationCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.ux = self.project / "tests/ux"
        shutil.copytree(FIXTURE, self.ux)
        self.output = self.project / "plans/profile.json"

    def run_cli(self, *args):
        return subprocess.run(
            [str(LAUNCHER), *map(str, args)], cwd=self.project,
            capture_output=True, text=True, check=False,
        )

    def generate(self, *args, output=None, project=None):
        return self.run_cli(
            "generate-verification-profile", "--project-root", project or self.project,
            "--output", output or self.output, *args,
        )

    def discover(self, **kwargs):
        return ProjectPersonaAdapter(policy_document=load_policy()).discover(
            self.project, **kwargs,
        )

    def config(self, **kwargs):
        (self.ux / "verification.json").write_text(json.dumps({
            "schema_version": 1, **kwargs,
        }))

    def second_task(self, *, unresolved=False, future=False):
        original = self.ux / "tasks/governance/sample-task.md"
        text = original.read_text().replace("GOV-SAMPLE-001", "GOV-OTHER-002")
        text = text.replace("/governance/proposals/sample", "/other/{id}" if unresolved else "/other")
        if future:
            text = text.replace("title:", "implementation_status: future-product\ntitle:", 1)
        (original.parent / "other-task.md").write_text(text)

    def assert_rejected(self, result, *, code=2):
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIsInstance(json.loads(result.stderr)["error"], dict)
        self.assertFalse(self.output.exists())

    def test_launcher_deterministic_bytes_and_bounded_reload_receipt(self):
        first = self.generate("--target-origin", "https://private-host.example.invalid")
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        document = behavioral_contract.load_profile(self.output)
        self.assertEqual(document, self.discover(target_origin="https://private-host.example.invalid").to_dict())
        self.assertEqual(receipt["profile_id"], document["profile_id"])
        self.assertEqual(receipt["profile_digest"], behavioral_contract.verification_profile_digest(document))
        self.assertEqual(receipt["proof_kind"], "plan_generation_and_reload")
        self.assertTrue(receipt["reload_verified"])
        self.assertEqual(receipt["selected_task_ids"], ["gov-sample-001"])
        self.assertEqual(receipt["selected_case_ids"], [case["case_id"] for case in document["cases"]])
        self.assertEqual(receipt["required_case_ids"], [case["case_id"] for case in document["cases"] if case["required"]])
        other = self.project / "plans/other.json"
        second = self.generate("--target-origin", "https://private-host.example.invalid", output=other)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.output.read_bytes(), other.read_bytes())
        self.assertEqual(first.stdout, second.stdout)
        self.assertNotIn("private-host", first.stdout + first.stderr + self.output.read_text())

    def test_platform_symlink_ancestor_preserves_project_and_output_boundaries(self):
        # Like macOS /var -> /private/var, the alias sits above the workspace.
        alias = self.root / "platform-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        project = alias / "project"
        result = self.generate(project=project, output=project / "plans/profile.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(behavioral_contract.load_profile(self.output), self.discover().to_dict())

    def test_suite_default_and_explicit_task_union_override(self):
        self.second_task(future=True)
        suites = self.ux / "suites"
        suites.mkdir(exist_ok=True)
        (suites / "focused.md").write_text("---\nid: focused\ntask_ids:\n  - GOV-SAMPLE-001\n---\n")
        self.config(suite="focused", browser_engines=["webkit", "chromium"], viewports=["1024x768", "375x812"])
        default = self.discover()
        self.assertEqual({case.scenario_id for case in default.cases}, {"gov-sample-001"})
        selected = self.discover(task_ids=["gov-sample-001", "gov-other-002"])
        self.assertEqual({case.scenario_id for case in selected.cases}, {"gov-sample-001", "gov-other-002"})
        self.assertEqual(len(selected.cases), 16)
        result = self.generate("--task-id", "gov-sample-001", "--task-id", "gov-other-002")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(behavioral_contract.load_profile(self.output), selected.to_dict())

    def test_task_union_overrides_status_and_validates_existing_config_first(self):
        self.second_task(future=True)
        self.assertEqual({case.scenario_id for case in self.discover().cases}, {"gov-sample-001"})
        self.assertEqual({case.scenario_id for case in self.discover(task_ids=["gov-other-002"]).cases}, {"gov-other-002"})
        for config in ({"include_statuses": ["future-product"]}, {"suite": "missing"}, {"browser_engines": []}):
            with self.subTest(config=config):
                self.config(**config)
                self.assert_rejected(self.generate("--task-id", "gov-other-002"))

    def test_exact_case_subset_preserves_all_selected_primitives(self):
        self.second_task()
        self.config(browser_engines=["firefox", "chromium"], viewports=["1024x768", "375x812"])
        candidate = self.discover(task_ids=["gov-sample-001", "gov-other-002"])
        cases = [next(case for case in candidate.cases if case.scenario_id == task and not case.required)
                 for task in ("gov-sample-001", "gov-other-002")]
        result = self.generate(
            "--task-id", "gov-sample-001", "--task-id", "gov-other-002",
            "--case-id", cases[0].case_id, "--case-id", cases[1].case_id,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        document = behavioral_contract.load_profile(self.output)
        self.assertEqual(document["cases"], sorted([case.to_dict() for case in cases], key=lambda case: case["case_id"]))
        self.assertEqual(document["selection_status"], "optional_cases_only")
        self.assertEqual(json.loads(result.stdout)["required_case_ids"], [])
        for name in ("configured_engines", "auth_field_names", "source", "discovery_status", "target_origin_digest", "coverage_diagnostics"):
            self.assertEqual(document[name], candidate.to_dict()[name])

    def test_case_subset_cannot_drop_an_explicit_task(self):
        self.second_task()
        case = self.discover(task_ids=["gov-sample-001"]).cases[0]
        self.assert_rejected(self.generate(
            "--task-id", "gov-sample-001", "--task-id", "gov-other-002", "--case-id", case.case_id,
        ))

    def test_unknown_duplicate_empty_and_malformed_selectors(self):
        case_id = self.discover().cases[0].case_id
        selectors = [
            ("--task-id", "unknown"), ("--task-id", ""), ("--task-id", "GOV-SAMPLE-001"),
            ("--task-id", "x" * 129), ("--task-id", "gov-sample-001", "--task-id", "gov-sample-001"),
            ("--case-id", "case-sha256:" + "0" * 64), ("--case-id", ""), ("--case-id", "made-up"),
            ("--case-id", case_id.upper()), ("--case-id", case_id, "--case-id", case_id),
        ]
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assert_rejected(self.generate(*selector))
        for kwargs in ({"task_ids": []}, {"case_ids": []}, {"task_ids": "gov-sample-001"}, {"case_ids": {case_id}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(InvalidSchemaError):
                self.discover(**kwargs)

    def test_absent_declarations_stay_not_declared_with_task_selector(self):
        shutil.rmtree(self.project / "tests")
        result = self.generate("--task-id", "gov-sample-001")
        self.assertEqual(result.returncode, 0, result.stderr)
        profile = behavioral_contract.load_profile(self.output)
        self.assertEqual(profile["discovery_status"], "not_declared")
        self.assertEqual(profile["selection_status"], "not_declared")
        self.assertEqual(profile["cases"], [])
        self.assertEqual(profile["configured_engines"], [])
        self.output.unlink()
        self.assert_rejected(self.generate("--case-id", "case-sha256:" + "0" * 64))

    def test_incomplete_and_invalid_declarations_write_nothing(self):
        (self.ux / "personas/_index.md").unlink()
        self.assert_rejected(self.generate())
        shutil.rmtree(self.ux)
        shutil.copytree(FIXTURE, self.ux)
        self.config(unknown=SECRET)
        result = self.generate()
        self.assert_rejected(result)
        self.assertNotIn(SECRET, result.stderr)

    def test_explicit_fixture_root_and_default_absent_discovery(self):
        fixture_root = self.root / "fixture"
        shutil.copytree(FIXTURE, fixture_root)
        result = self.generate(project=fixture_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["discovery_status"], "not_declared")
        self.output.unlink()
        result = self.generate("--declaration-root", ".", project=fixture_root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["discovery_status"], "declared")

    def test_unresolved_selected_route_blocks_before_case_filtering(self):
        self.second_task(unresolved=True)
        case = self.discover(task_ids=["gov-sample-001"]).cases[0]
        result = self.generate("--task-id", "gov-other-002", "--case-id", case.case_id)
        self.assert_rejected(result, code=3)
        self.assertEqual(json.loads(result.stderr)["error"]["route_binding_gaps"], ["gov-other-002:id"])
        result = self.generate("--task-id", "gov-sample-001")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bound_route_retains_template_digest(self):
        self.second_task(unresolved=True)
        self.config(route_bindings={"gov-other-002": {"id": "item-123"}})
        profile = self.discover(task_ids=["gov-other-002"])
        result = self.generate("--task-id", "gov-other-002", "--case-id", profile.cases[0].case_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(behavioral_contract.load_profile(self.output)["cases"], [profile.cases[0].to_dict()])

    def test_unsafe_directory_symlink_and_hardlink_paths(self):
        missing = self.root / "missing"
        self.assert_rejected(self.generate(project=missing))
        regular = self.root / "regular"
        regular.write_text("ordinary file")
        self.assert_rejected(self.generate(project=regular))
        linked = self.root / "linked"
        linked.symlink_to(self.project, target_is_directory=True)
        self.assert_rejected(self.generate(project=linked))
        plans = self.project / "plans"
        plans.symlink_to(self.root, target_is_directory=True)
        self.assert_rejected(self.generate())
        plans.unlink()
        plans.mkdir()
        self.output.symlink_to(regular)
        result = self.generate()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(regular.read_text(), "ordinary file")
        self.output.unlink()
        os.link(regular, self.output)
        result = self.generate()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(regular.read_text(), "ordinary file")
        self.output.unlink()
        task = self.ux / "tasks/governance/sample-task.md"
        os.link(task, self.root / "task-hardlink")
        self.assert_rejected(self.generate())

    def test_origins_and_declaration_credentials_never_escape(self):
        bad_origins = [
            "https://user:" + SECRET + "@example.invalid", "https://example.invalid/?token=" + SECRET,
            "https://example.invalid/#" + SECRET, "not-an-origin:" + SECRET,
        ]
        for origin in bad_origins:
            with self.subTest(origin=origin):
                result = self.generate("--target-origin", origin)
                self.assert_rejected(result)
                self.assertNotIn(SECRET, result.stdout + result.stderr)
                self.config(target_origin=origin)
                result = self.generate()
                self.assert_rejected(result)
                self.assertNotIn(SECRET, result.stderr)
                (self.ux / "verification.json").unlink()
        self.config(target_origin="https://configured.example.invalid")
        self.assert_rejected(self.generate("--target-origin", "https://different.example.invalid"))
        result = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr)
        published = result.stdout + result.stderr + self.output.read_text()
        for value in ("configured.example.invalid", "member@example.invalid", "sk-fixture-persona-password-must-not-survive"):
            self.assertNotIn(value, published)

    def test_hostile_route_diagnostic_is_not_printed(self):
        task = self.ux / "tasks/governance/sample-task.md"
        task.write_text(task.read_text().replace("GOV-SAMPLE-001", SECRET).replace("/governance/proposals/sample", "/other/{id}"))
        result = self.generate()
        self.assert_rejected(result)
        self.assertNotIn(SECRET, result.stderr)

    def test_output_conflict_is_structured_and_preserves_file(self):
        self.output.parent.mkdir()
        self.output.write_bytes(b"existing output\n")
        result = self.generate()
        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "verification_profile_output_conflict")
        self.assertEqual(self.output.read_bytes(), b"existing output\n")

    def test_concurrent_output_claim_is_not_overwritten_or_removed(self):
        writer = cli._write_json_once

        def claimed(path, document, **kwargs):
            self.output.parent.mkdir()
            self.output.write_text("another task claimed the output")
            return writer(path, document, **kwargs)

        with mock.patch.object(cli, "_write_json_once", side_effect=claimed):
            code, emitted = self.local_generation()
        self.assertEqual(code, 6)
        self.assertEqual(emitted[0]["error"]["code"], "verification_profile_output_conflict")
        self.assertEqual(self.output.read_text(), "another task claimed the output")

    def local_generation(self):
        emitted = []
        with mock.patch.object(cli, "_emit", side_effect=lambda value, *args: emitted.append(value)):
            code = cli.main(["generate-verification-profile", "--project-root", str(self.project), "--output", str(self.output)])
        return code, emitted

    def test_serialization_is_bounded_before_any_write(self):
        with mock.patch.object(behavioral_contract, "MAX_CONTRACT_BYTES", 10), mock.patch.object(cli, "_write_json_once") as writer:
            code, _emitted = self.local_generation()
        self.assertEqual(code, 2)
        writer.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_write_fsync_reload_and_mismatch_failures_remove_only_new_output(self):
        failures = [
            mock.patch.object(cli.os, "write", side_effect=OSError(SECRET)),
            mock.patch.object(cli.os, "fsync", side_effect=OSError(SECRET)),
            mock.patch.object(behavioral_contract, "load_profile", side_effect=ValueError(SECRET)),
            mock.patch.object(behavioral_contract, "load_profile", return_value={}),
        ]
        for failure in failures:
            with self.subTest(failure=failure), failure:
                code, emitted = self.local_generation()
            self.assertEqual(code, 2)
            self.assertNotIn(SECRET, json.dumps(emitted))
            self.assertFalse(self.output.exists())
            self.assertEqual(list(self.output.parent.iterdir()), [])

    def test_reload_failure_cleanup_preserves_a_replaced_output(self):
        def swapped(_path):
            self.output.unlink()
            self.output.write_text("replacement owned by another task")
            raise ValueError(SECRET)
        with mock.patch.object(behavioral_contract, "load_profile", side_effect=swapped):
            code, emitted = self.local_generation()
        self.assertEqual(code, 2)
        self.assertNotIn(SECRET, json.dumps(emitted))
        self.assertEqual(self.output.read_text(), "replacement owned by another task")

    def initialize_run(self):
        subprocess.run(["git", "init", "-q", str(self.project)], check=True, capture_output=True)
        state = self.project / ".workflow-kernel/runs/profile-test"
        result = self.run_cli("init", state, "--run-id", "profile-test", "--occurred-at", "2026-10-08T00:00:00Z")
        self.assertEqual(result.returncode, 0, result.stderr)
        return state

    def bind_profile(self, state, profile):
        contract = verification_contract()
        contract["verification_profile_id"] = profile["profile_id"]
        contract["verification_profile_digest"] = behavioral_contract.verification_profile_digest(profile)
        required = [case["case_id"] for case in profile["cases"] if case["required"]]
        contract["persona_case_ids"] = required
        contract["browser_case_ids"] = required
        contract["revision_justification"]["added_obligation_ids"] = sorted(behavioral_contract.obligations(contract))
        path = self.project / "contract.json"
        path.write_text(json.dumps(contract))
        return self.run_cli("bind-verification-contract", "--state-dir", state, "--contract", path, "--verification-profile", self.output)

    def test_generated_profile_binding_exact_retry_and_digest_or_case_conflict(self):
        state = self.initialize_run()
        result = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr)
        profile = behavioral_contract.load_profile(self.output)
        bound = self.bind_profile(state, profile)
        self.assertEqual(bound.returncode, 0, bound.stderr)
        receipt = json.loads(bound.stdout)
        self.assertEqual(receipt["verification_profile_digest"], json.loads(result.stdout)["profile_digest"])
        before = (state / "events.jsonl").read_bytes()
        retried = self.bind_profile(state, profile)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual(bound.stdout, retried.stdout)
        self.assertEqual((state / "events.jsonl").read_bytes(), before)
        profile["coverage_diagnostics"] = ["coverage_matrix_mismatch"]
        self.output.unlink()
        self.output.write_text(json.dumps(profile))
        rejected = self.bind_profile(state, profile)
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertEqual((state / "events.jsonl").read_bytes(), before)
        self.output.unlink()
        candidate = self.discover()
        required = next(case for case in candidate.cases if case.required)
        result = self.generate("--case-id", required.case_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        rejected = self.bind_profile(state, behavioral_contract.load_profile(self.output))
        self.assertEqual(rejected.returncode, 2, rejected.stderr)
        self.assertEqual((state / "events.jsonl").read_bytes(), before)

    def test_non_rendered_contract_binds_null_profile_without_generation(self):
        state = self.initialize_run()
        path = self.project / "contract.json"
        path.write_text(json.dumps(verification_contract()))
        result = self.run_cli("bind-verification-contract", "--state-dir", state, "--contract", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertIsNone(receipt["verification_profile_id"])
        self.assertIsNone(receipt["verification_profile_digest"])
        self.assertIsNone(receipt["verification_profile_ref"])
        self.assertFalse(self.output.exists())
