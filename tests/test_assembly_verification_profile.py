import copy
import json
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.repository_verification import (
    derive_verification_plan,
    repository_profile_digest,
    resolve_repository_profile,
    validate_repository_profile,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = (
    ROOT / "plugins/assembly/skills/assembly-build/references/"
    "assembly-baseplate-verification-profile.json"
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


def select_runtime_argv(resolved, lane_id, runtime_evidence=None):
    """Model the documented consumer gate without adding a second planner."""
    profile = resolved["profile"]
    argv = lanes(profile)[lane_id]["argv"]
    if argv[:3] != ["docker", "compose", "exec"]:
        return argv
    expected = {
        "status": "running",
        "service": argv[3],
        "profile_digest": repository_profile_digest(profile),
        "state_generation": "current",
    }
    if runtime_evidence != expected:
        raise ValueError("declared runtime service proof unavailable")
    return argv


def repository_profile_status(paths):
    required = {"go.mod", "docker-compose.yml", "cmd/assembly"}
    return "resolved" if required <= set(paths) else "unavailable"


def ux_declaration_status(documents):
    if not documents:
        return "not_declared"
    required = (
        "implementation_status:", "route:", "requires_auth:", "personas:",
        "expected:", "screenshot_points:",
    )
    task_count = 0
    for path, text in documents.items():
        if "coverage-matrix" in path:
            continue
        task_count += 1
        if not text.startswith("---\n") or any(field not in text for field in required):
            return "blocked"
    return "declared" if task_count else "not_declared"


class AssemblyVerificationProfileTests(unittest.TestCase):
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
        for lane in canonical["lanes"]:
            self.assertNotIn("sh", lane["argv"])
            self.assertNotIn("bash", lane["argv"])
            self.assertFalse(any(token in {";", "&&", "||", "|"} for token in lane["argv"]))

    def test_project_override_precedes_plugin_and_incomplete_project_blocks(self):
        plugin = load_profile()
        project = project_exec_override(plugin)
        resolved = resolve_repository_profile(project_profile=project, plugin_profile=plugin)
        self.assertEqual(resolved["source"], "project")
        incomplete = copy.deepcopy(project)
        incomplete["lanes"][0].pop("authority")
        with self.assertRaises(ValueError):
            resolve_repository_profile(project_profile=incomplete, plugin_profile=plugin)
        self.assertEqual(resolve_repository_profile(), {
            "status": "unavailable", "source": "none", "profile": None,
        })

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

    def test_exec_requires_current_matching_service_proof_and_run_does_not(self):
        plugin = load_profile()
        plugin_resolved = resolve_repository_profile(plugin_profile=plugin)
        self.assertEqual(select_runtime_argv(plugin_resolved, "full-test")[:6], [
            "docker", "compose", "run", "--rm", "--no-deps", "app",
        ])
        project = project_exec_override(plugin)
        resolved = resolve_repository_profile(project_profile=project, plugin_profile=plugin)
        current = {
            "status": "running", "service": "app",
            "profile_digest": repository_profile_digest(resolved["profile"]),
            "state_generation": "current",
        }
        self.assertEqual(select_runtime_argv(resolved, "full-test", current)[:4], [
            "docker", "compose", "exec", "app",
        ])
        for evidence in (
            None,
            {**current, "status": "stopped"},
            {**current, "state_generation": "stale"},
            {**current, "service": "worker"},
            {**current, "profile_digest": DIGEST},
        ):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                select_runtime_argv(resolved, "full-test", evidence)

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
        self.assertEqual(by_id["container-scan"]["authority"], "github-actions-non-pr")

    def test_ux_task_frontmatter_is_authority_absent_is_not_declared_and_malformed_blocks(self):
        valid = """---
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
        self.assertEqual(ux_declaration_status({}), "not_declared")
        self.assertEqual(ux_declaration_status({"tests/ux/tasks/members.md": valid}), "declared")
        self.assertEqual(ux_declaration_status({
            "tests/ux/tasks/members.md": valid.replace("route: /members\n", ""),
        }), "blocked")
        self.assertEqual(ux_declaration_status({
            "tests/ux/coverage-matrix.md": "not authoritative",
        }), "not_declared")

    def test_unsupported_repository_is_unavailable(self):
        self.assertEqual(repository_profile_status({"README.md", "go.mod"}), "unavailable")
        self.assertEqual(repository_profile_status({
            "go.mod", "docker-compose.yml", "cmd/assembly",
        }), "resolved")

    def test_docs_preserve_browser_recovery_and_fail_closed_standalone(self):
        command = (ROOT / "plugins/assembly/commands/assembly-build.md").read_text()
        runner = (ROOT / "plugins/assembly/agents/workflow/go-test-runner.md").read_text()
        setup = (ROOT / "plugins/assembly/skills/development/setup.md").read_text()
        for document in (command, runner, setup):
            self.assertIn("assembly-baseplate-verification-profile.json", document)
            self.assertIn("Workflow Kernel", document)
        normalized = " ".join(command.split())
        for phrase in ("primary browser", "fresh primary", "different configured engine", "human_help_required", "diagnostic only"):
            self.assertIn(phrase, normalized)
        self.assertIn("unavailable", command)


if __name__ == "__main__":
    unittest.main()
