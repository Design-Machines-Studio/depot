import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.repository_verification import (
    derive_verification_plan,
    repository_profile_digest,
    validate_repository_profile,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "plugins/assembly/skills/assembly-build/references"
PROFILE_PATH = REFERENCES / "assembly-baseplate-verification-profile.json"
sys.path.insert(0, str(REFERENCES))

from assembly_verification_adapter import (  # noqa: E402
    discover_ux_tasks,
    plan_assembly_verification,
    resolve_assembly_profile,
)


DIGEST = "sha256:" + "a" * 64


def load_profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def lanes(profile):
    return {item["id"]: item for item in validate_repository_profile(profile)["lanes"]}


def repository():
    return {
        "scope_id": "b" * 64,
        "commit_sha": "c" * 40,
        "tree_digest": DIGEST,
        "tracked_diff_digest": DIGEST,
        "untracked_digest": DIGEST,
        "branch": "feature",
        "worktree_state": "dirty",
    }


def project_exec_override(plugin_profile):
    result = copy.deepcopy(plugin_profile)
    result["profile_id"] = "assembly-baseplate-project"
    result["source"] = {
        "kind": "project", "reference": ".assembly/verification-profile.json",
    }
    for item in result["lanes"]:
        if item["id"] == "full-test":
            item["argv"] = [
                "docker", "compose", "exec", "app", "go", "test",
                "-tags=dev", "-count=1", "./...",
            ]
            item["prerequisites"].append(
                {"kind": "service", "id": "app", "required": True},
            )
    return result


def valid_task():
    return """---
implementation_status: current
route: /members
requires_auth: true
personas:
  - id: member
    expected: SUCCESS
viewport: 1440x900
engine: chromium
screenshot_points:
  - members list
---
"""


class AssemblyVerificationProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repository_root = Path(self.temporary.name) / "assembly-baseplate"
        (self.repository_root / "cmd/assembly").mkdir(parents=True)
        (self.repository_root / "go.mod").write_text("module example.test/baseplate\n")
        (self.repository_root / "docker-compose.yml").write_text("services: {}\n")

    def tearDown(self):
        self.temporary.cleanup()

    def write_task(self, text=None, name="members.md"):
        directory = self.repository_root / "tests/ux/tasks"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(valid_task() if text is None else text)
        return path

    def plan(self, **changes):
        arguments = dict(
            changed_paths=[], changed_packages=[], risk_inputs=[],
            required_lane_ids=["full-test"],
            generated_at="2026-07-22T00:00:00Z",
        )
        arguments.update(changes)
        return plan_assembly_verification(
            self.repository_root, repository(), **arguments,
        )

    def test_valid_baseplate_defaults_are_strict_safe_and_schema_valid(self):
        profile = load_profile()
        canonical = validate_repository_profile(profile)
        schema = json.loads(
            (KERNEL_REFERENCES / "repository-verification-profile-schema.json").read_text(),
        )
        self.assertTrue(schema_matches(canonical, schema))
        by_id = lanes(profile)
        self.assertEqual(
            by_id["templ-generate"]["argv"],
            ["docker", "compose", "run", "--rm", "--no-deps", "app", "go", "tool", "templ", "generate"],
        )
        self.assertEqual(by_id["build-assembly"]["argv"][-1], "./cmd/assembly")
        self.assertEqual(
            by_id["full-test"]["argv"],
            ["docker", "compose", "run", "--rm", "--no-deps", "app", "go", "test", "-tags=dev", "-count=1", "./..."],
        )
        self.assertEqual(canonical["source"]["kind"], "plugin")
        self.assertEqual(len(canonical["declaration_digests"]), 1)
        for lane in canonical["lanes"]:
            self.assertNotIn("sh", lane["argv"])
            self.assertNotIn("bash", lane["argv"])
            self.assertFalse(any(token in {";", "&&", "||", "|"} for token in lane["argv"]))

    def test_production_adapter_returns_kernel_selected_safe_argv(self):
        result = self.plan()
        self.assertEqual((result["status"], result["source"]), ("resolved", "plugin"))
        selected = {item["lane_id"]: item["argv"] for item in result["selected_argv"]}
        self.assertIn("doctor-diff", selected)
        self.assertEqual(selected["full-test"], lanes(load_profile())["full-test"]["argv"])
        self.assertEqual(result["plan"]["profile_id"], "assembly-baseplate")

    def test_project_override_precedes_plugin_and_incomplete_project_is_unavailable(self):
        plugin = load_profile()
        project = project_exec_override(plugin)
        resolved = resolve_assembly_profile(
            self.repository_root, project_profile=project, plugin_profile=plugin,
        )
        self.assertEqual((resolved["status"], resolved["source"]), ("resolved", "project"))
        incomplete = copy.deepcopy(project)
        incomplete["lanes"][0].pop("authority")
        invalid = resolve_assembly_profile(
            self.repository_root, project_profile=incomplete, plugin_profile=plugin,
        )
        self.assertEqual((invalid["status"], invalid["reason"]), (
            "unavailable", "invalid_repository_profile",
        ))

    def test_changed_packages_select_focus_without_forcing_full_or_race(self):
        plan = derive_verification_plan(
            load_profile(), repository(),
            changed_paths=["internal/auth/permissions.go"],
            changed_packages=["./internal/auth"], risk_inputs=[],
            generated_at="2026-07-22T00:00:00Z",
        )
        selected = {item["id"]: item["selected"] for item in plan["lanes"]}
        self.assertTrue(selected["focused-permissions"])
        self.assertFalse(selected["full-test"])
        self.assertFalse(selected["race-test"])

    def test_high_risk_escalates_declared_tiers_without_collapsing_them(self):
        plan = derive_verification_plan(
            load_profile(), repository(), changed_paths=[], changed_packages=[],
            risk_inputs=["auth-boundary", "concurrency"],
            generated_at="2026-07-22T00:00:00Z",
        )
        by_id = {item["id"]: item for item in plan["lanes"]}
        self.assertEqual((by_id["full-test"]["selected"], by_id["full-test"]["reason"]), (True, "risk_escalated"))
        self.assertEqual((by_id["race-test"]["selected"], by_id["race-test"]["reason"]), (True, "risk_escalated"))
        self.assertEqual(by_id["security-scan"]["tier"], "security")

    def test_all_fresh_go_test_lanes_disable_cache(self):
        test_lanes = [
            item for item in lanes(load_profile()).values()
            if "go" in item["argv"] and "test" in item["argv"]
        ]
        self.assertEqual({item["id"] for item in test_lanes}, {
            "focused-permissions", "full-test", "race-test",
        })
        self.assertTrue(all("-tags=dev" in item["argv"] and "-count=1" in item["argv"] for item in test_lanes))

    def test_exec_requires_exact_current_matching_service_proof(self):
        plugin = load_profile()
        project = project_exec_override(plugin)
        base = dict(
            project_profile=project, plugin_profile=plugin,
            required_lane_ids=["full-test"],
        )
        missing = self.plan(**base)
        self.assertEqual((missing["status"], missing["reason"], missing["selected_argv"]), (
            "unavailable", "compose_service_proof_unavailable", [],
        ))
        evidence = {
            "status": "running", "service": "app",
            "profile_digest": repository_profile_digest(project),
            "repository_scope_id": repository()["scope_id"],
            "compose_project": self.repository_root.name,
            "state_generation": "current", "commit_sha": repository()["commit_sha"],
        }
        current = self.plan(**base, compose_service_evidence=evidence)
        selected = {item["lane_id"]: item["argv"] for item in current["selected_argv"]}
        self.assertEqual(selected["full-test"][:4], ["docker", "compose", "exec", "app"])
        for field, value in (
            ("status", "stopped"), ("service", "worker"),
            ("profile_digest", DIGEST), ("repository_scope_id", "d" * 64),
            ("compose_project", "other"), ("state_generation", "stale"),
            ("commit_sha", "e" * 40),
        ):
            hostile = {**evidence, field: value}
            with self.subTest(field=field):
                result = self.plan(**base, compose_service_evidence=hostile)
                self.assertEqual((result["status"], result["reason"]), (
                    "unavailable", "compose_service_proof_unavailable",
                ))

    def test_noncanonical_exec_argv_cannot_bypass_service_proof(self):
        plugin = load_profile()
        project = project_exec_override(plugin)
        for item in project["lanes"]:
            if item["id"] == "full-test":
                item["argv"] = [
                    "docker", "compose", "--ansi", "never", "exec", "app",
                    "go", "test", "-tags=dev", "-count=1", "./...",
                ]
        result = self.plan(
            project_profile=project, plugin_profile=plugin,
            required_lane_ids=["full-test"],
        )
        self.assertEqual((result["status"], result["reason"], result["selected_argv"]), (
            "unavailable", "unsupported_exec_argv", [],
        ))

    def test_ci_scopes_remain_distinct_and_pr_is_not_non_pr_authority(self):
        by_id = lanes(load_profile())
        expected = {
            "pr-test": ("remote_pr", "github-actions-pr"),
            "push-test": ("push", "github-actions-push"),
            "scheduled-test": ("schedule", "github-actions-schedule"),
            "merge-group-test": ("merge_group", "github-actions-merge-group"),
            "post-merge-test": ("post_merge", "github-actions-post-merge"),
        }
        self.assertEqual(
            {key: (by_id[key]["tier"], by_id[key]["authority"]) for key in expected},
            expected,
        )
        self.assertNotEqual(by_id["pr-test"]["authority"], by_id["race-test"]["authority"])
        self.assertNotEqual(by_id["pr-test"]["authority"], by_id["container-scan"]["authority"])

    def test_ux_frontmatter_is_mechanically_parsed_and_matrix_is_not_authority(self):
        self.assertEqual(discover_ux_tasks(self.repository_root)["status"], "not_declared")
        matrix = self.repository_root / "tests/ux/coverage-matrix.md"
        matrix.parent.mkdir(parents=True)
        matrix.write_text(valid_task())
        self.assertEqual(discover_ux_tasks(self.repository_root)["status"], "not_declared")
        self.write_task()
        result = discover_ux_tasks(self.repository_root)
        self.assertEqual((result["status"], result["reason"]), (
            "declared", "task_frontmatter_authority",
        ))
        self.assertEqual(result["tasks"][0], {
            "path": "tests/ux/tasks/members.md", "implementation_status": "current",
            "route": "/members", "requires_auth": True,
            "personas": [{"id": "member", "expected": "SUCCESS"}],
            "viewport": "1440x900", "engine": "chromium",
            "screenshot_points": ["members list"],
        })

    def test_each_required_ux_declaration_field_fails_closed_when_missing(self):
        valid = valid_task()
        hostile = {
            "implementation_status": valid.replace("implementation_status: current\n", ""),
            "route": valid.replace("route: /members\n", ""),
            "requires_auth": valid.replace("requires_auth: true\n", ""),
            "personas": valid.replace("personas:\n  - id: member\n    expected: SUCCESS\n", ""),
            "persona_id": valid.replace("  - id: member\n", ""),
            "persona_expected": valid.replace("    expected: SUCCESS\n", ""),
            "viewport": valid.replace("viewport: 1440x900\n", ""),
            "engine": valid.replace("engine: chromium\n", ""),
            "screenshot_points": valid.replace("screenshot_points:\n  - members list\n", ""),
        }
        for field, document in hostile.items():
            with self.subTest(field=field):
                path = self.write_task(document)
                result = discover_ux_tasks(self.repository_root)
                self.assertEqual((result["status"], result["reason"], result["path"]), (
                    "blocked", "invalid_task_declaration", "tests/ux/tasks/members.md",
                ))
                planned = self.plan()
                self.assertEqual((planned["status"], planned["reason"]), (
                    "blocked", "invalid_ux_declaration",
                ))
                path.unlink()

    def test_unsupported_or_incomplete_repository_is_unavailable(self):
        unsupported = Path(self.temporary.name) / "unsupported"
        unsupported.mkdir()
        unsupported.joinpath("go.mod").write_text("module example.test/unsupported\n")
        result = resolve_assembly_profile(unsupported)
        self.assertEqual((result["status"], result["reason"]), (
            "unavailable", "unsupported_repository",
        ))
        self.repository_root.joinpath("cmd/assembly").rename(self.repository_root / "cmd/other")
        result = self.plan()
        self.assertEqual((result["status"], result["reason"]), (
            "unavailable", "unsupported_repository",
        ))

    def test_selected_non_runnable_lane_returns_unavailable_not_partial_argv(self):
        result = self.plan(required_lane_ids=["container-scan"])
        self.assertEqual((result["status"], result["reason"], result["selected_argv"]), (
            "unavailable", "selected_lane_unavailable", [],
        ))
        self.assertIn("container-scan", result["unavailable_lane_ids"])

    def test_docs_invoke_adapter_and_preserve_browser_recovery(self):
        command = (ROOT / "plugins/assembly/commands/assembly-build.md").read_text()
        runner = (ROOT / "plugins/assembly/agents/workflow/go-test-runner.md").read_text()
        setup = (ROOT / "plugins/assembly/skills/development/setup.md").read_text()
        for document in (command, runner, setup):
            self.assertIn("assembly_verification_adapter.py", document)
            self.assertIn("plan_assembly_verification", document)
            self.assertIn("Workflow Kernel", document)
        normalized = " ".join(command.split())
        for phrase in ("primary browser", "fresh primary", "different configured engine", "human_help_required", "diagnostic only"):
            self.assertIn(phrase, normalized)


if __name__ == "__main__":
    unittest.main()
