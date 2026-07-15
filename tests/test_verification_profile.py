import json
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tests import KERNEL_REFERENCES
from tests import detail_digest, schema_matches
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.policies import load_policy
from workflow_kernel.verification import (
    PersonaCase, VerificationProfile, _validate_route, digest_target_route,
    digest_target_origin,
)
from workflow_kernel.adapters.personas import _DeclarationTree, ProjectPersonaAdapter
from workflow_kernel._files import PinnedDirectory


ROOT = KERNEL_REFERENCES
FIXTURES = Path(__file__).parent / "fixtures" / "ux"


class VerificationProfileTests(unittest.TestCase):
    def test_origin_rejects_lone_surrogate_with_stable_policy_error(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            digest_target_origin("https://\ud800.invalid")
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_verification_target"),
        )

    def test_route_templates_require_explicit_task_scoped_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            task = project / "tests/ux/tasks/governance/sample-task.md"
            task.write_text(task.read_text().replace(
                "/governance/proposals/sample", "/governance/proposals/{id}",
            ))
            adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
            blocked = adapter.discover(project)
            self.assertEqual(blocked.selection_status, "blocked_route_bindings")
            self.assertEqual(
                blocked.coverage_diagnostics, ("unresolved_route_parameters",),
            )
            self.assertEqual(blocked.route_binding_gaps, ("gov-sample-001:id",))
            (project / "tests/ux/verification.json").write_text(json.dumps({
                "schema_version": 1,
                "route_bindings": {"gov-sample-001": {"id": "proposal-123"}},
            }))
            profile = adapter.discover(project)
        self.assertEqual({case.route for case in profile.cases}, {
            "/governance/proposals/proposal-123",
        })
        self.assertEqual(
            {case.declared_route_digest for case in profile.cases},
            {digest_target_route("/governance/proposals/{id}")},
        )
        self.assertTrue(all("{" not in case.route for case in profile.cases))

    def test_frontmatter_consumes_every_nonblank_line_exactly(self):
        mutations = (
            ("route: /governance/proposals/sample", "route : /attacker"),
            ("title: Review a proposal", "unknown_key: value\ntitle: Review a proposal"),
            ("title: Review a proposal", "meta-data: &loop\n  self: *loop\ntitle: Review a proposal"),
        )
        source = FIXTURES / "assembly/tasks/governance/sample-task.md"
        for old, new in mutations:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(old, new))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

    def test_credential_detection_is_ascii_exact(self):
        self.assertEqual(_validate_route("/\u017fk-secret"), "/\u017fk-secret")
        self.assertEqual(_validate_route("/s\u212a-secret"), "/s\u212a-secret")
        for route in ("/\u017fk-secret", "/s\u212a-secret"):
            case = PersonaCase(
                "member", "scenario", "member", route, "chromium",
                "1440x900", True,
            )
            schema = json.loads((ROOT / "verification-profile-schema.json").read_text())
            profile = VerificationProfile(
                1, "project_declaration", (case,), (),
                configured_engines=("chromium",),
            )
            self.assertTrue(schema_matches(profile.to_dict(), schema))

    def test_implicit_yaml_scalars_fail_in_every_scalar_authority(self):
        mutations = (
            ("id: GOV-SAMPLE-001", "id: 42"),
            ("title: Review a proposal", "title: null"),
            ("requires_auth: true", "requires_auth: 2026-01-01"),
            ("reason: \"A live-shape descriptive explanation that is never retained\"",
             "reason: .nan"),
        )
        for old, new in mutations:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(old, new))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

    def test_all_yaml_sexagesimal_and_timestamp_shapes_require_quotes(self):
        implicit = (
            "+12:34", "1:2", "123:45", "1:2:3", "+1:2",
            "2001-12-15  2:59:43.1",
            "2001-12-15 2:59:43.1",
            "2001-12-15 2:59:43.1 Z",
            "2001-12-15 2:59:43.1 +02:00",
            "2001-12-15T02:59:43.1Z",
        )
        for value in implicit:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(
                    "title: Review a proposal", "title: " + value,
                ))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

    def test_quoted_implicit_lookalikes_and_narrow_typed_scalars_remain_valid(self):
        lookalikes = (
            "+12:34", "1:2", "123:45", "1:2:3", "+1:2",
            "2001-12-15  2:59:43.1",
            "2001-12-15 2:59:43.1 Z",
            "2001-12-15 2:59:43.1 -07:30",
        )
        for value in lookalikes:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(
                    "title: Review a proposal", "title: " + json.dumps(value),
                ))
                persona = project / "tests/ux/personas/casual-member.md"
                persona.write_text(persona.read_text().replace(
                    "role: Member",
                    "role: Member\ntech_comfort: 0\ngovernance_knowledge: 5",
                ))
                profile = ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json",
                ).discover(project)
                self.assertEqual("runnable_cases", profile.selection_status)

    def test_yaml_percent_directives_require_quotes(self):
        for value in ("%TAG", "%YAML"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(
                    "title: Review a proposal", "title: " + value,
                ))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

            with self.subTest(value="quoted " + value), \
                    tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests/ux")
                task = project / "tests/ux/tasks/governance/sample-task.md"
                task.write_text(task.read_text().replace(
                    "title: Review a proposal", "title: " + json.dumps(value),
                ))
                profile = ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json",
                ).discover(project)
                self.assertEqual("runnable_cases", profile.selection_status)

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
        profile = adapter.discover(FIXTURES / "assembly", declaration_root=".")
        # 2 personas (casual-member required, reluctant-board-member optional)
        # x 2 configured engines.
        self.assertEqual(len(profile.cases), 4)
        self.assertEqual({case.browser_engine for case in profile.cases}, {"chromium", "firefox"})
        self.assertTrue(all(
            case.required for case in profile.cases
            if case.persona_id == "casual-member"
        ))
        self.assertTrue(all(
            not case.required for case in profile.cases
            if case.persona_id == "reluctant-board-member"
        ))
        self.assertTrue(all(case.legacy_status_defaulted for case in profile.cases))
        self.assertEqual(
            {case.persona_id for case in profile.cases},
            {"casual-member", "reluctant-board-member"},
        )
        self.assertEqual({case.expected_outcome for case in profile.cases}, {"FRICTION"})
        self.assertEqual({case.role for case in profile.cases}, {"member"})
        self.assertEqual(profile.auth_field_names, ("session_cookie",))

    def test_profile_identity_canonicalizes_case_and_auth_name_sets(self):
        first = PersonaCase(
            "member-b", "scenario-b", "member", "/b", "firefox",
            "1440x900", True,
        )
        second = PersonaCase(
            "member-a", "scenario-a", "member", "/a", "chromium",
            "1440x900", True,
        )
        left = VerificationProfile(
            1, "project_declaration", (first, second), ("session_cookie", "csrf_token"),
        )
        right = VerificationProfile(
            1, "project_declaration", (second, first), ("csrf_token", "session_cookie"),
        )
        self.assertEqual(left.profile_id, right.profile_id)
        self.assertEqual(left.cases, tuple(sorted(left.cases, key=lambda case: case.case_id)))
        self.assertEqual(left.auth_field_names, ("csrf_token", "session_cookie"))

    def test_live_assignment_shape_legacy_role_and_supporting_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
            # Exercise the legacy requires_auth-based role default: drop the
            # explicit requires_role and leave the governance area (which
            # requires an explicit role) for the onboarding area instead.
            # The area is path-derived (finding 090), so the relocated task
            # moves to tasks/onboarding/ to match its declared area.
            relocated = task.parents[1] / "onboarding" / task.name
            relocated.parent.mkdir()
            relocated.write_text("".join(
                line for line in task.read_text().replace(
                    "requires_auth: true", "requires_auth: false",
                ).replace(
                    "route: /governance/proposals/sample", "route: /register",
                ).replace(
                    "area: governance", "area: onboarding",
                ).splitlines(keepends=True)
                if not line.startswith("requires_role:")
            ))
            task.unlink()
            (relocated.parent / "supporting-checklist.md").write_text(
                "# Supporting checklist\n\nThis is not a task declaration.\n"
            )
            profile = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
        self.assertEqual({case.role for case in profile.cases}, {"public"})
        self.assertEqual({case.scenario_id for case in profile.cases}, {"gov-sample-001"})

    def test_only_tests_ux_is_implicit_and_alternate_fixture_root_is_explicit(self):
        adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
        implicit = adapter.discover(FIXTURES / "assembly")
        explicit = adapter.discover(FIXTURES / "assembly", declaration_root=".")
        self.assertEqual(implicit.discovery_status, "not_declared")
        self.assertEqual(explicit.discovery_status, "declared")

    def test_coverage_matrix_drift_is_diagnostic_not_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            baseline = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
            matrix = project / "tests" / "ux" / "coverage-matrix.md"
            matrix.write_text(matrix.read_text().replace("FRICTION", "SUCCESS"))
            profile = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
        self.assertEqual(profile.coverage_diagnostics, ("coverage_matrix_mismatch",))
        self.assertEqual({case.expected_outcome for case in profile.cases}, {"FRICTION"})
        self.assertEqual(profile.profile_id, baseline.profile_id)

    def test_live_assembly_declaration_shapes_are_readable_when_available(self):
        repositories = (
            Path("/Users/trav/Websites/design-machines/assembly"),
            Path("/Users/trav/Websites/design-machines/assembly-baseplate"),
        )
        adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
        for repository in repositories:
            if not (repository / "tests" / "ux").is_dir():
                continue
            with self.subTest(repository=repository.name):
                profile = adapter.discover(repository)
                self.assertEqual(profile.discovery_status, "declared")
                self.assertIn(profile.selection_status, {
                    "runnable_cases", "blocked_route_bindings",
                })
                if profile.selection_status == "blocked_route_bindings":
                    self.assertIn(
                        "unresolved_route_parameters",
                        profile.coverage_diagnostics,
                    )
                else:
                    self.assertTrue(profile.cases)

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

    def test_persona_index_drift_fails_closed_and_matrix_drift_is_advisory(self):
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
            profile = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
            self.assertEqual(profile.coverage_diagnostics, ("coverage_matrix_mismatch",))

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
            profile = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
            self.assertEqual(profile.coverage_diagnostics, ("coverage_matrix_mismatch",))

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
                ProjectPersonaAdapter(policy_path=path).discover(
                    FIXTURES / "assembly", declaration_root=".",
                )

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
                    "requires_auth: true", "requires_auth: true\nrequires_role: " + role,
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

    def test_nested_persona_assignment_structure_is_exact_and_fail_closed(self):
        replacements = (
            ("    expected: FRICTION", "    expected: FRICTION\n    expected: BLOCKED"),
            ("    expected: FRICTION", "    expected: FRICTION\n    required: nope"),
            ("    expected: FRICTION", "    expected: FRICTION\n    required: false\n    required: true"),
            ("personas:", "not_personas:"),
        )
        for old, new in replacements:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                task.write_text(task.read_text().replace(old, new, 1))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

    def test_unsupported_or_malformed_frontmatter_containers_fail_closed(self):
        replacements = (
            ("auth_fields:\n  - session_cookie", "auth_fields: [session_cookie]"),
            ("auth_fields:\n  - session_cookie", "auth_fields:\n  nested: session_cookie"),
            ('  - "A signed-in member has a proposal to review"',
             "  - key: value"),
            ('  - "A signed-in member has a proposal to review"',
             "  - [mobile, responsive]"),
            ('  - "A signed-in member has a proposal to review"',
             "  - {kind: mobile}"),
            ("preconditions:\n  - \"A signed-in member has a proposal to review\"",
             "preconditions:\n  viewport: 375x812"),
        )
        for old, new in replacements:
            with self.subTest(new=new), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                task.write_text(task.read_text().replace(old, new, 1))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

        yaml_structures = (
            "!!omap []", "!!pairs []", "!!set {}", "!!str value",
            "|", ">", "&anchor value", "*anchor", "- nested",
            "? key", "key: value", "[mobile, responsive]", "{kind: mobile}",
            "true", "42", "2026-01-01", "plain value",
        )
        for value in yaml_structures:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                task.write_text(task.read_text().replace(
                    '  - "A signed-in member has a proposal to review"',
                    "  - " + value,
                    1,
                ))
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
            task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
            task.write_text(task.read_text().replace(
                '  - "A signed-in member has a proposal to review"',
                '\n'.join(
                    "  - " + json.dumps(value)
                    for value in yaml_structures
                ),
            ))
            profile = ProjectPersonaAdapter(
                policy_path=ROOT / "workflow-policy.json",
            ).discover(project)
            self.assertTrue(profile.cases)

    def test_scalar_grammar_rejects_yaml_structures_in_all_scalar_positions(self):
        structures = (
            "!!omap []", "!!pairs []", "!!set {}", "!!str value",
            "|", ">", "&anchor value", "*anchor", "- nested",
            "? key", "key: value", "[mobile, responsive]", "{kind: mobile}",
        )
        replacements = (
            ("title: Review a proposal", "title: {}"),
            ('    reason: "A live-shape descriptive explanation that is never retained"',
             "    reason: {}"),
        )
        for original, template in replacements:
            for value in structures:
                with self.subTest(original=original, value=value), \
                        tempfile.TemporaryDirectory() as directory:
                    project = Path(directory)
                    shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                    task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                    task.write_text(task.read_text().replace(
                        original, template.format(value), 1,
                    ))
                    with self.assertRaises(InvalidSchemaError):
                        ProjectPersonaAdapter(
                            policy_path=ROOT / "workflow-policy.json",
                        ).discover(project)

    def test_quoted_yaml_structure_lookalikes_are_supported_scalars(self):
        lookalikes = ("!!omap []", "&anchor value", "|", "[mobile, responsive]")
        for value in lookalikes:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                shutil.copytree(FIXTURES / "assembly", project / "tests" / "ux")
                task = project / "tests" / "ux" / "tasks" / "governance" / "sample-task.md"
                task.write_text(task.read_text().replace(
                    "title: Review a proposal", "title: " + json.dumps(value), 1,
                ).replace(
                    '    reason: "A live-shape descriptive explanation that is never retained"',
                    "    reason: " + json.dumps(value), 1,
                ))
                profile = ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json",
                ).discover(project)
                self.assertTrue(profile.cases)

    def test_identifier_and_route_runtime_and_schema_boundaries_match(self):
        PersonaCase("p" * 128, "s" * 128, "m" * 128, "/" + "a" * 2047,
                    "chromium", "1440x900", True)
        for field, value in (
            ("persona", "p" * 129),
            ("scenario", "s" * 129),
            ("role", "m" * 129),
            ("route", "/" + "a" * 2048),
            ("route", "/../admin"),
            ("route", "/safe/../admin"),
        ):
            with self.subTest(field=field, length=len(value)), self.assertRaises(InvalidSchemaError):
                PersonaCase(
                    value if field == "persona" else "p",
                    value if field == "scenario" else "s",
                    value if field == "role" else "member",
                    value if field == "route" else "/safe",
                    "chromium", "1440x900", True,
                )
        schema = json.loads((ROOT / "verification-profile-schema.json").read_text())
        case = PersonaCase("p", "s", "member", "/safe", "chromium", "1440x900", True)
        profile = VerificationProfile(1, "project_declaration", (case,), ())
        payload = profile.to_dict()
        payload["cases"][0]["route"] = "/../admin"
        self.assertFalse(schema_matches(payload, schema))
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile(
                1, "project_declaration", (case,), ("a" * 129,),
            )

    def test_routes_reject_secret_values_without_rejecting_benign_names(self):
        schema = json.loads((ROOT / "verification-profile-schema.json").read_text())
        for route in ("/monkey", "/account/password", "/keys/overview"):
            case = PersonaCase(
                "p", "s", "member", route, "chromium", "1440x900", True,
            )
            profile = VerificationProfile(1, "project_declaration", (case,), ())
            self.assertTrue(schema_matches(profile.to_dict(), schema), route)
        for route in (
            "/sk-live-secret", "/session/sk-live-secret",
            "/token/ghp_abcdefghijklmnopqrstuvwxyz",
            "//member:password@example.invalid/private", "/safe/%2e%2e/admin",
        ):
            with self.subTest(route=route), self.assertRaises(InvalidSchemaError):
                PersonaCase(
                    "p", "s", "member", route, "chromium", "1440x900", True,
                )
            safe = PersonaCase(
                "p", "s", "member", "/safe", "chromium", "1440x900", True,
            )
            payload = VerificationProfile(
                1, "project_declaration", (safe,), (),
            ).to_dict()
            payload["cases"][0]["route"] = route
            self.assertFalse(schema_matches(payload, schema), route)

    def test_route_decoding_corpus_matches_runtime_and_schema(self):
        schema = json.loads((ROOT / "verification-profile-schema.json").read_text())
        safe = PersonaCase(
            "p", "s", "member", "/safe", "chromium", "1440x900", True,
        )
        invalid_routes = (
            "/safe/%2fadmin", "/safe/%5cadmin", "/safe/%252fadmin",
            "/safe/%252e%252e/admin", "/safe/%2e./admin",
            "/safe/.%2e/admin", "/safe/%00admin", "/safe/%2500admin",
            "/%73k-live-secret", "/Bearer%20credential", "/safe/%23fragment",
            "/safe/%3Fquery", "/safe/%",
            "/safe/%2", "/safe/%GG", "/safe/\x1fcontrol",
            "/safe/%80", "/safe/%C2", "/safe/%E2%82",
            "/safe/%F0%9F%92", "/safe/%C0%AF", "/safe/%ED%A0%80",
            "/safe\n", "/safe/" + chr(0xD800), "/safe/" + chr(0xDFFF),
        )
        for route in invalid_routes:
            with self.subTest(route=route), self.assertRaises(InvalidSchemaError):
                PersonaCase(
                    "p", "s", "member", route, "chromium", "1440x900", True,
                )
            payload = VerificationProfile(
                1, "project_declaration", (safe,), (),
            ).to_dict()
            payload["cases"][0]["route"] = route
            self.assertFalse(schema_matches(payload, schema), route)
            with self.assertRaises(InvalidSchemaError):
                digest_target_route(route)

        for encoded in (
            "%C2%A2", "%C3%A9", "%E2%82%AC", "%F0%90%80%80",
            "%F0%9F%92%A9", "%F0%A0%80%80", "%F0%BF%BF%BF",
            "%F4%8F%BF%BF",
        ):
            route = "/safe/" + encoded
            case = PersonaCase(
                "p", "s", "member", route, "chromium", "1440x900", True,
            )
            payload = VerificationProfile(
                1, "project_declaration", (case,), (),
            ).to_dict()
            self.assertTrue(schema_matches(payload, schema), route)

        for byte in range(256):
            route = "/safe/%{:02X}".format(byte)
            try:
                PersonaCase(
                    "p", "s", "member", route, "chromium", "1440x900", True,
                )
                runtime_valid = True
            except InvalidSchemaError:
                runtime_valid = False
            payload = VerificationProfile(
                1, "project_declaration", (safe,), (),
            ).to_dict()
            payload["cases"][0]["route"] = route
            self.assertEqual(
                runtime_valid, schema_matches(payload, schema), route,
            )

        route_pattern = re.compile(
            schema["$defs"]["case"]["properties"]["route"]["pattern"],
        )
        boundary_bytes = (0x00, 0x7F, 0x80, 0x8F, 0x90, 0x9F,
                          0xA0, 0xBF, 0xC0, 0xFF)
        mismatches = []

        def compare(route):
            try:
                digest_target_route(route)
                runtime_valid = True
            except (InvalidSchemaError, UnicodeEncodeError):
                runtime_valid = False
            schema_valid = route_pattern.search(route) is not None
            if runtime_valid != schema_valid:
                mismatches.append((route, runtime_valid, schema_valid))

        for first in range(256):
            for second in range(256):
                compare("/safe/%{:02X}%{:02X}".format(first, second))
        for first in range(0xE0, 0xF0):
            for second in range(256):
                for third in boundary_bytes:
                    compare(
                        "/safe/%{:02X}%{:02X}%{:02X}".format(
                            first, second, third,
                        ),
                    )
        for first in range(0xF0, 0xF5):
            for second in range(256):
                for third in boundary_bytes:
                    for fourth in boundary_bytes:
                        compare(
                            "/safe/%{:02X}%{:02X}%{:02X}%{:02X}".format(
                                first, second, third, fourth,
                            ),
                        )
        compare("/safe\n")
        for codepoint in range(0x110000):
            compare("/safe/" + chr(codepoint))
        self.assertEqual(mismatches, [])

    def test_declaration_root_pin_rejects_ancestor_swap_before_open(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            ux = project / "tests" / "ux"
            shutil.copytree(FIXTURES / "assembly", ux)
            victim = ux / "tasks" / "governance" / "sample-task.md"
            outside = Path(directory) / "outside-tasks"
            shutil.copytree(ux / "tasks", outside)
            injected = outside / "governance" / "sample-task.md"
            injected.write_text(injected.read_text().replace(
                "/governance/proposals/sample", "/outside-swapped",
            ))
            original = os.open
            swapped = []

            def swap_ancestor(path, *args, **kwargs):
                if (not swapped and path == "tasks"
                        and kwargs.get("dir_fd") is not None):
                    (ux / "tasks").rename(ux / "tasks-owned")
                    (ux / "tasks").symlink_to(outside, target_is_directory=True)
                    swapped.append(True)
                return original(path, *args, **kwargs)

            with mock.patch("os.open", side_effect=swap_ancestor), \
                    self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json",
                ).discover(project)
            self.assertTrue(swapped)

    def test_bound_child_directory_rejects_ordinary_replacement_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            ux = project / "tests" / "ux"
            shutil.copytree(FIXTURES / "assembly", ux)
            replacement = Path(directory) / "replacement-tasks"
            shutil.copytree(ux / "tasks", replacement)
            injected = replacement / "governance" / "sample-task.md"
            injected.write_text(injected.read_text().replace(
                "/governance/proposals/sample", "/ordinary-directory-swap",
            ))
            original = _DeclarationTree.read_text
            swapped = []

            def replace_child(declarations, path):
                if not swapped and path == ux / "tasks" / "governance" / "sample-task.md":
                    (ux / "tasks").rename(ux / "tasks-owned")
                    replacement.rename(ux / "tasks")
                    swapped.append(True)
                return original(declarations, path)

            with mock.patch.object(_DeclarationTree, "read_text", replace_child), \
                    self.assertRaises(InvalidSchemaError):
                ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json",
                ).discover(project)
            self.assertTrue(swapped)

    def test_declaration_reads_reject_hardlinks_for_every_owned_document(self):
        relative_paths = (
            "verification.json", "personas/_index.md", "personas/casual-member.md",
            "tasks/governance/sample-task.md", "coverage-matrix.md",
        )
        for relative in relative_paths:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                ux = project / "tests" / "ux"
                shutil.copytree(FIXTURES / "assembly", ux)
                victim = ux / relative
                content = (
                    '{"schema_version": 1}' if relative == "verification.json"
                    else victim.read_text()
                )
                if victim.exists():
                    victim.unlink()
                outside = Path(directory) / "outside-owned-document"
                outside.write_text(content)
                os.link(outside, victim)
                with self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)

    def test_declaration_reads_revalidate_identity_after_descriptor_open(self):
        relative_paths = (
            "verification.json", "personas/_index.md", "personas/casual-member.md",
            "tasks/governance/sample-task.md", "coverage-matrix.md",
        )
        original = PinnedDirectory.require_identity
        for relative in relative_paths:
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "project"
                ux = project / "tests" / "ux"
                shutil.copytree(FIXTURES / "assembly", ux)
                victim = ux / relative
                if relative == "verification.json":
                    victim.write_text('{"schema_version": 1}')
                replacement = Path(directory) / "replacement-owned-document"
                replacement.write_text(victim.read_text())
                swapped = []

                def swap_after_open(pinned, descriptor, name):
                    original(pinned, descriptor, name)
                    if not swapped and pinned.path / name == victim:
                        os.replace(replacement, victim)
                        swapped.append(True)

                with mock.patch.object(
                    PinnedDirectory, "require_identity", swap_after_open,
                ), self.assertRaises(InvalidSchemaError):
                    ProjectPersonaAdapter(
                        policy_path=ROOT / "workflow-policy.json",
                    ).discover(project)
                self.assertTrue(swapped)

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
            FIXTURES / "assembly", declaration_root=".",
        )
        self.assertIsNone(profile.target_origin_digest)
        bound = profile.bind_target_origin("https://assembly.example.invalid")
        self.assertRegex(bound.target_origin_digest, r"^origin-sha256:[0-9a-f]{64}$")
        self.assertNotEqual(profile.profile_id, bound.profile_id)
        self.assertNotIn("assembly.example.invalid", json.dumps(bound.to_dict()))

        direct = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(
            FIXTURES / "assembly", target_origin="https://assembly.example.invalid",
            declaration_root=".",
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

    def test_dm_review_matrix_is_diagnostic_and_task_declarations_are_authority(self):
        reviewer = ROOT.parents[3] / "dm-review" / "agents" / "review" / "ux-quality-reviewer.md"
        text = reviewer.read_text()
        self.assertIn("task declarations", text.lower())
        self.assertIn("diagnostic", text.lower())
        self.assertIn("never emit a P1, P2, or P3 finding from `coverage-matrix.md`", text)
        self.assertNotIn("A reviewed page has no corresponding row in the coverage matrix (P3)", text)
        self.assertNotIn("New routes added in the diff have zero persona coverage in the matrix (P2)", text)


if __name__ == "__main__":
    unittest.main()
