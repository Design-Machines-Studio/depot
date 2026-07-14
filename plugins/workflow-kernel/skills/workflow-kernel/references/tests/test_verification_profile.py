import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest, schema_matches
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.policies import load_policy
from workflow_kernel.verification import PersonaCase, VerificationProfile
from workflow_kernel.adapters.personas import ProjectPersonaAdapter


ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "ux"


class VerificationProfileTests(unittest.TestCase):
    def test_schemas_accept_runtime_receipts_and_policy_defaults(self):
        profile_schema = json.loads((ROOT / "verification-profile-schema.json").read_text())
        recovery_schema = json.loads((ROOT / "browser-recovery-schema.json").read_text())
        policy_schema = json.loads((ROOT / "workflow-policy-schema.json").read_text())
        policy = json.loads((ROOT / "workflow-policy.json").read_text())
        case = PersonaCase(
            "casual-member", "gov-sample-001", "member", "/dashboard",
            "chromium", "1440x900", True,
        )
        profile = VerificationProfile(1, "project_declaration", (case,), ("session_cookie",))
        self.assertTrue(schema_matches(profile.to_dict(), profile_schema))
        self.assertFalse(schema_matches({
            "schema_version": 1, "status": "blocked",
            "reason_code": "human_help_required", "attempts": [],
            "lifecycle": [], "missing_case_ids": [case.case_id],
        }, recovery_schema))
        self.assertTrue(schema_matches(policy, policy_schema))
        self.assertEqual(policy["verification"]["browser_engines"], ["chromium", "firefox"])
        self.assertEqual(policy["verification"]["desktop_viewport"], "1440x900")
        self.assertEqual(policy["verification"]["mobile_viewport"], "375x812")
        viewport_pattern = policy_schema["properties"]["verification"]["properties"]["desktop_viewport"]["pattern"]
        self.assertIsNotNone(re.fullmatch(viewport_pattern, "16384x16384"))
        self.assertIsNone(re.fullmatch(viewport_pattern, "16385x16384"))
        retained = load_policy(ROOT / "workflow-policy.json").verification_defaults
        self.assertEqual(tuple(retained["browser_engines"]), ("chromium", "firefox"))

    def test_legacy_assembly_task_is_runnable_required_and_matrix_is_not_authority(self):
        adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
        profile = adapter.discover(FIXTURES / "assembly")
        self.assertEqual(len(profile.cases), 2)
        self.assertEqual({case.browser_engine for case in profile.cases}, {"chromium", "firefox"})
        self.assertTrue(all(case.required for case in profile.cases))
        self.assertTrue(all(case.legacy_status_defaulted for case in profile.cases))
        self.assertEqual({case.persona_id for case in profile.cases}, {"casual-member"})
        self.assertEqual({case.expected_outcome for case in profile.cases}, {"FRICTION"})
        self.assertEqual(profile.auth_field_names, ("session_cookie",))

    def test_config_suite_and_viewport_precedence_expand_complete_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            shutil.copytree(
                FIXTURES / "assembly-baseplate" / "tasks",
                project / "tests" / "ux" / "tasks",
                dirs_exist_ok=True,
            )
            shutil.copytree(
                FIXTURES / "assembly-baseplate" / "suites",
                project / "tests" / "ux" / "suites",
            )
            (project / "tests" / "ux" / "coverage-matrix.md").write_text(
                "# Coverage Matrix\n\n"
                "| Task | Persona | Expected |\n"
                "| --- | --- | --- |\n"
                "| GOV-SAMPLE-001 | casual-member | FRICTION |\n"
                "| BP-MOBILE-001 | casual-member | SUCCESS |\n"
            )
            (project / "tests" / "ux" / "verification.json").write_text(json.dumps({
                "schema_version": 1,
                "suite": "permissions",
                "browser_engines": ["firefox"],
                "viewports": ["390x844", "1440x900"],
            }))
            profile = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)
        required = tuple(case for case in profile.cases if case.required)
        self.assertEqual(len(required), 2)
        self.assertEqual(len(profile.cases), 2)
        self.assertEqual({case.viewport for case in required}, {"390x844", "1440x900"})
        self.assertEqual({case.browser_engine for case in profile.cases}, {"firefox"})
        self.assertTrue(all(case.browser_source == "project_config" for case in profile.cases))
        self.assertTrue(all(case.viewport_source == "project_config" for case in profile.cases))

    def test_invalid_declarations_fail_closed_with_stable_reasons(self):
        base = FIXTURES / "assembly"
        mutations = {
            "duplicate_case": "\n".join((base / "tasks/governance/sample-task.md").read_text().splitlines()),
            "traversal": "/../admin",
            "unknown_engine": "netscape",
            "bad_viewport": "wide",
        }
        for name in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(base, project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                if name == "duplicate_case":
                    duplicate = task.with_name("duplicate.md")
                    duplicate.write_text(task.read_text())
                elif name == "traversal":
                    task.write_text(task.read_text().replace("/governance/proposals/sample", mutations[name]))
                else:
                    config = {"schema_version": 1}
                    config["browser_engines" if name == "unknown_engine" else "viewports"] = [mutations[name]]
                    (project / "tests" / "ux" / "verification.json").write_text(json.dumps(config))
                with self.assertRaises(InvalidSchemaError) as raised:
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_verification_declaration"),
                )

    def test_status_filters_and_unknown_task_statuses_fail_closed(self):
        mutations = (
            {"include_statuses": []},
            {"include_statuses": ["currnet"]},
            {"include_statuses": "current"},
            {"include_statuses": ["future-product"]},
        )
        for config_update in mutations:
            with self.subTest(config_update=config_update), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                config = {"schema_version": 1, **config_update}
                (project / "tests" / "ux" / "verification.json").write_text(json.dumps(config))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
            task.write_text(task.read_text().replace("route:", "implementation_status: currnet\nroute:"))
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_persona_index_and_coverage_matrix_drift_fail_closed(self):
        def project_copy(directory):
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            return project

        with tempfile.TemporaryDirectory() as directory:
            project = project_copy(directory)
            (project / "tests" / "ux" / "personas" / "casual-member.md").unlink()
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = project_copy(directory)
            source = project / "tests" / "ux" / "personas" / "casual-member.md"
            (source.parent / "stray-member.md").write_text(
                source.read_text().replace("id: casual-member", "id: stray-member")
            )
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = project_copy(directory)
            matrix = project / "tests" / "ux" / "coverage-matrix.md"
            matrix.write_text(matrix.read_text().replace("FRICTION", "SUCCESS"))
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = project_copy(directory)
            shutil.copytree(
                FIXTURES / "assembly-baseplate" / "tasks",
                project / "tests" / "ux" / "tasks",
                dirs_exist_ok=True,
            )
            matrix = project / "tests" / "ux" / "coverage-matrix.md"
            matrix.write_text(
                "| Task ID | CM |\n| --- | --- |\n| GOV-SAMPLE-001 | F |\n"
            )
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_persona_and_task_discovery_reject_symlinks_before_reading(self):
        for target_kind in ("persona", "task", "directory"):
            with self.subTest(target_kind=target_kind), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                outside = Path(directory) / "outside.md"
                if target_kind == "persona":
                    victim = project / "tests" / "ux" / "personas" / "casual-member.md"
                    outside.write_text(victim.read_text())
                    victim.unlink(); victim.symlink_to(outside)
                elif target_kind == "task":
                    victim = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                    outside.write_text(victim.read_text())
                    victim.unlink(); victim.symlink_to(outside)
                else:
                    victim = project / "tests" / "ux" / "personas"
                    outside_dir = Path(directory) / "outside-personas"
                    victim.rename(outside_dir); victim.symlink_to(outside_dir, target_is_directory=True)
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            real_tests = project / "real-tests"
            real_tests.mkdir()
            shutil.copytree(FIXTURES / "assembly", real_tests / "ux")
            (project / "tests").symlink_to(real_tests, target_is_directory=True)
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_exact_bool_and_schema_version_types_fail_closed(self):
        with self.assertRaises(InvalidSchemaError):
            PersonaCase(
                "member", "task", "member", "/", "chromium", "1440x900",
                True, legacy_status_defaulted=1,
            )
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile(True, "project_declaration", (), (),
                                selection_status="no_runnable_tasks")
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            (project / "tests" / "ux" / "verification.json").write_text(
                json.dumps({"schema_version": True})
            )
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_existing_incomplete_ux_tree_is_invalid_not_not_declared(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "tests" / "ux" / "personas").mkdir(parents=True)
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_policy_viewport_limit_is_shared_with_verification_runtime(self):
        canonical = json.loads((ROOT / "workflow-policy.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            canonical["verification"]["desktop_viewport"] = "16384x16384"
            path.write_text(json.dumps(canonical))
            self.assertEqual(
                load_policy(path).verification_defaults["desktop_viewport"],
                "16384x16384",
            )
            canonical["verification"]["desktop_viewport"] = "16385x16384"
            path.write_text(json.dumps(canonical))
            with self.assertRaises(InvalidSchemaError):
                load_policy(path)

    def test_persona_discovery_uses_canonical_policy_normalization(self):
        policy = json.loads((ROOT / "workflow-policy.json").read_text())
        policy["verification"]["browser_engines"] = ["webkit"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(policy))
            with self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(policy_path=path).discover(FIXTURES / "assembly")

    def test_injected_policy_document_is_snapshotted_against_its_origin(self):
        document = load_policy(ROOT / "workflow-policy.json")
        object.__setattr__(document, "verification_defaults", {
            "browser_engines": ("webkit",),
            "desktop_viewport": "1440x900",
            "mobile_viewport": "375x812",
        })
        with self.assertRaises(InvalidSchemaError):
            ProjectPersonaAdapter(policy_document=document)

    def test_secret_shaped_durable_declaration_fields_fail_closed(self):
        for role in ("API_TOKEN=leaked-secret", "api_token"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                task.write_text(task.read_text().replace(
                    "requires_role: member", "requires_role: " + role,
                ))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_malformed_config_containers_are_normalized_before_deduplication(self):
        for field in ("browser_engines", "include_statuses"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                (project / "tests" / "ux" / "verification.json").write_text(
                    json.dumps({"schema_version": 1, field: [{}]})
                )
                try:
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)
                except BaseException as error:
                    self.assertIsInstance(error, InvalidSchemaError)
                else:
                    self.fail("malformed config was accepted")

    def test_duplicate_frontmatter_scalar_and_list_keys_fail_closed(self):
        for duplicate in (
            "route: /governance/proposals/sample\n",
            "tags:\n  - mobile\ntags:\n  - responsive\n",
        ):
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                text = task.read_text()
                task.write_text(text.replace("title:", duplicate + "title:", 1))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(project)

    def test_profile_runtime_loader_rejects_schema_valid_cross_field_drift(self):
        case = PersonaCase(
            "casual-member", "gov-sample-001", "member", "/dashboard",
            "chromium", "1440x900", True,
        )
        profile = VerificationProfile(1, "project_declaration", (case,), ("session_cookie",))
        payload = profile.to_dict()
        payload["selection_status"] = "optional_cases_only"
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile.from_dict(payload)

    def test_runtime_target_origin_binding_is_opaque_and_part_of_profile_identity(self):
        profile = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(
            FIXTURES / "assembly"
        )
        self.assertIsNone(profile.target_origin_digest)
        bound = profile.bind_target_origin("https://assembly.example.invalid")
        self.assertRegex(bound.target_origin_digest, r"^origin-sha256:[0-9a-f]{64}$")
        self.assertNotEqual(profile.profile_id, bound.profile_id)
        self.assertNotIn("assembly.example.invalid", json.dumps(bound.to_dict()))

        direct = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(
            FIXTURES / "assembly", target_origin="https://assembly.example.invalid",
        )
        self.assertEqual(bound.target_origin_digest, direct.target_origin_digest)

        payload = profile.to_dict()
        payload["cases"][0]["case_id"] = "case-sha256:" + "0" * 64
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile.from_dict(payload)

    def test_assessment_instruction_never_skips_required_target_unavailable(self):
        assess = ROOT.parents[3] / "pipeline" / "skills" / "assess" / "SKILL.md"
        text = assess.read_text()
        self.assertNotIn("UX assessment skipped -- no dev server detected", text)
        self.assertIn("target unavailable", text)
        self.assertIn("human_help_required", text)

    def test_dm_review_instructions_emit_terminal_receipt_when_target_is_unavailable(self):
        dm_review = ROOT.parents[3] / "dm-review"
        paths = (
            dm_review / "agents" / "review" / "visual-browser-tester.md",
            dm_review / "skills" / "visual-test" / "SKILL.md",
        )
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text()
                self.assertIn("target unavailable", text)
                self.assertIn("human_help_required", text)
                self.assertIn("exact missing", text)


if __name__ == "__main__":
    unittest.main()
