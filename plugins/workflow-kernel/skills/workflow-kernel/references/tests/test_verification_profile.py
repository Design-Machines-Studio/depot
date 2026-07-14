import json
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
        self.assertTrue(schema_matches({
            "schema_version": 1, "status": "blocked",
            "reason_code": "human_help_required", "attempts": [],
            "lifecycle": [], "missing_case_ids": [case.case_id],
        }, recovery_schema))
        self.assertTrue(schema_matches(policy, policy_schema))
        self.assertEqual(policy["verification"]["browser_engines"], ["chromium", "firefox"])
        self.assertEqual(policy["verification"]["desktop_viewport"], "1440x900")
        self.assertEqual(policy["verification"]["mobile_viewport"], "375x812")
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


if __name__ == "__main__":
    unittest.main()
