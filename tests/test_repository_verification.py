import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.verification_errors import VerificationPlannerError
from workflow_kernel.verification_execution import run_bounded_capture
from workflow_kernel.verification_orchestrator import execute_plan
from workflow_kernel.verification_repository import (
    git_changed_paths, tree_input_digests, validate_profile,
)
from workflow_kernel.verification_planning import build_plan as kernel_build_plan


PROFILE_SCHEMA = KERNEL_REFERENCES / "repository-verification-profile-schema.json"
PLAN_SCHEMA = KERNEL_REFERENCES / "repository-verification-plan-schema.json"
RESULT_SCHEMA = KERNEL_REFERENCES / "repository-verification-result-schema.json"
ASSEMBLY_EXAMPLE = (
    KERNEL_REFERENCES.parents[3]
    / "assembly/references/repository-verification-profile.example.json"
)
BASE_REF = "refs/verification/base"
TEST_ENVIRONMENT = {
    "DM_VERIFICATION_SUBSTRATE": "test-host-containment",
}


def test_environment(environment=None):
    return {**TEST_ENVIRONMENT, **({} if environment is None else environment)}


def git_commit(repository, ref="HEAD"):
    return subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", ref],
        capture_output=True, check=True, text=True,
    ).stdout.strip()


def prepare_candidate(repository, changed_paths):
    changed_paths = sorted(set(changed_paths))
    profile_path = repository / ".dm/verification.json"
    if subprocess.run(
        ["git", "-C", str(repository), "diff", "--quiet", "--", str(profile_path)],
        check=False,
    ).returncode:
        subprocess.run(
            ["git", "-C", str(repository), "add", ".dm/verification.json"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "test profile"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "update-ref", BASE_REF, "HEAD"],
            check=True,
        )
    dirty = subprocess.run(
        [
            "git", "-C", str(repository), "status", "--porcelain=v1",
            "--untracked-files=all",
        ],
        capture_output=True, check=True, text=True,
    ).stdout
    if dirty:
        subprocess.run(
            ["git", "-C", str(repository), "add", "--all"], check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "test candidate"],
            check=True, capture_output=True,
        )
    actual = git_changed_paths(
        repository, git_commit(repository, BASE_REF), head_ref="HEAD",
    )
    if actual == changed_paths:
        return git_commit(repository, BASE_REF), git_commit(repository)
    for relative in changed_paths:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("candidate\n", encoding="utf-8")
        elif relative.endswith(".go"):
            path.write_text(
                path.read_text(encoding="utf-8") + "\n// candidate change\n",
                encoding="utf-8",
            )
        else:
            path.write_text(
                path.read_text(encoding="utf-8") + "\ncandidate change\n",
                encoding="utf-8",
            )
        subprocess.run(
            ["git", "-C", str(repository), "add", "--", relative],
            check=True,
        )
    if changed_paths:
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "test candidate"],
            check=True, capture_output=True,
        )
    return git_commit(repository, BASE_REF), git_commit(repository)


def build_plan(
    profile, repository, profile_ref, changed_paths, boundary, risk, **kwargs,
):
    base_commit, head_commit = prepare_candidate(repository, changed_paths)
    environment = test_environment(kwargs.get("environment"))
    kwargs["environment"] = environment
    kwargs.setdefault("base_commit", base_commit)
    kwargs.setdefault("head_commit", head_commit)
    return kernel_build_plan(
        profile, repository, profile_ref, changed_paths, boundary, risk,
        **kwargs,
    )


def execute(profile, repository, plan, *, environment=None):
    environment = test_environment(environment)
    result = execute_plan(
        profile, repository, plan,
        environment=environment,
    )
    return result, result["status"]


def profile_document(command=None):
    command = command or [
        sys.executable, "-c", "raise SystemExit(0)", "{packages}",
    ]
    return {
        "schema_version": 1,
        "profile_id": "fixture-go",
        "lanes": [
            {
                "id": "doctor",
                "tier": "doctor",
                "cadences": [
                    "chunk", "revision_batch", "execution_level",
                    "merge_candidate", "post_merge",
                ],
                "owner": "local",
                "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                "input_paths": [".dm/verification.json"],
                "execution_paths": [".dm/verification.json"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
            },
            {
                "id": "go-focused",
                "tier": "focused",
                "cadences": ["chunk", "revision_batch"],
                "owner": "local",
                "argv": command,
                "changed_paths": ["**/*.go", "go.mod", "go.sum"],
                "input_paths": [
                    "**/*.go", "go.mod", "go.sum", ".dm/verification.json",
                ],
                "execution_paths": [".dm/verification.json"],
                "package_selector": "go_changed",
                "declared_dependents": {
                    "./internal/source": ["./internal/dependent"],
                },
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
            },
            {
                "id": "go-full",
                "tier": "full",
                "cadences": [
                    "execution_level", "merge_candidate", "post_merge",
                ],
                "owner": "local",
                "argv": [sys.executable, "-c", "raise SystemExit(0)"],
                "changed_paths": ["**/*.go", "go.mod", "go.sum"],
                "input_paths": [
                    "**/*.go", "go.mod", "go.sum", ".dm/verification.json",
                ],
                "execution_paths": [".dm/verification.json"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
            },
            {
                "id": "go-race",
                "tier": "race",
                "cadences": ["merge_candidate", "post_merge"],
                "owner": "github",
                "argv": ["go", "test", "-race", "-count=1", "./..."],
                "changed_paths": ["**/*.go", "go.mod", "go.sum"],
                "input_paths": [
                    "**/*.go", "go.mod", "go.sum", ".dm/verification.json",
                ],
            },
        ],
    }


class RepositoryVerificationTests(unittest.TestCase):
    def repository(self, root, profile=None):
        repository = Path(root)
        repository.mkdir(parents=True, exist_ok=True)
        (repository / ".dm").mkdir()
        (repository / "internal/source").mkdir(parents=True)
        (repository / "internal/dependent").mkdir(parents=True)
        (repository / "docs").mkdir()
        (repository / "go.mod").write_text("module example.invalid/project\n")
        (repository / "internal/source/source.go").write_text("package source\n")
        (repository / "internal/dependent/dependent.go").write_text(
            "package dependent\n",
        )
        (repository / "docs/readme.md").write_text("fixture\n")
        document = profile or profile_document()
        (repository / ".dm/verification.json").write_text(
            json.dumps(document), encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(repository), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.email", "test@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "add", "."], check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "test base"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "update-ref", BASE_REF, "HEAD"],
            check=True,
        )
        return repository, document

    def execution_repository(self, directory):
        repository, profile = self.repository(directory)
        script = repository / "tools/verify.py"
        script.parent.mkdir()
        script.write_text("print('trusted')\n", encoding="utf-8")
        profile["lanes"][0]["execution_paths"].append("tools/verify.py")
        profile["lanes"][0]["execution_environment"] = [
            "GOFLAGS", "DM_VERIFICATION_SUBSTRATE",
        ]
        (repository / ".dm/verification.json").write_text(
            json.dumps(profile), encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(repository), "add", "."], check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "execution"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "update-ref", BASE_REF, "HEAD"],
            check=True,
        )
        return repository, profile, script

    def test_profile_and_runtime_artifacts_match_closed_schemas(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
                environment={"GOFLAGS": "-tags=dev"},
            )
            result, outcome = execute(
                profile, repository, plan, environment={"GOFLAGS": "-tags=dev"},
            )
        self.assertEqual(outcome, "complete")
        self.assertTrue(schema_matches(
            validate_profile(profile),
            json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertTrue(schema_matches(
            plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertEqual(result["artifact_role"], "repository_verification_result")
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["lanes"])
        self.assertTrue(schema_matches(
            result, json.loads(RESULT_SCHEMA.read_text(encoding="utf-8")),
        ))
        invalid_plan = {
            **plan,
            "lanes": [{**plan["lanes"][0], "owner": "bogus"}, *plan["lanes"][1:]],
        }
        self.assertFalse(schema_matches(
            invalid_plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
        ))

    def test_assembly_example_is_a_valid_closed_profile(self):
        profile = validate_profile(json.loads(ASSEMBLY_EXAMPLE.read_text()))
        self.assertEqual(profile["profile_id"], "assembly-go-docker")
        self.assertEqual(
            {lane["tier"] for lane in profile["lanes"]},
            {"doctor", "fast", "focused", "full", "race"},
        )

    def test_candidate_execution_without_external_containment_is_rejected(self):
        profile = profile_document()
        lane = profile["lanes"][1]
        lane.pop("required_environment")
        lane.pop("execution_environment")
        with self.assertRaises(VerificationPlannerError):
            validate_profile(profile)
        for tier, argv in (
            ("doctor", ["git", "-c", "alias.escape=!false", "escape"]),
            ("focused", ["git", "diff", "--check"]),
        ):
            with self.subTest(tier=tier, argv=argv):
                profile = profile_document()
                lane = profile["lanes"][0]
                lane["tier"] = tier
                lane["argv"] = argv
                lane.pop("required_environment")
                lane.pop("execution_environment")
                with self.assertRaises(VerificationPlannerError):
                    validate_profile(profile)

    def test_chunk_selects_changed_package_and_declared_dependents_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "medium",
            )
        lanes = {lane["id"]: lane for lane in plan["lanes"]}
        self.assertEqual(
            lanes["go-focused"]["packages"],
            ["./internal/dependent", "./internal/source"],
        )
        self.assertEqual(lanes["go-focused"]["disposition"], "run")
        self.assertEqual(lanes["go-full"]["disposition"], "not_scheduled")
        self.assertEqual(lanes["go-race"]["disposition"], "not_scheduled")

    def test_documentation_change_does_not_trigger_go_lanes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["docs/readme.md"], "chunk", "low",
            )
        lanes = {lane["id"]: lane for lane in plan["lanes"]}
        self.assertEqual(lanes["doctor"]["disposition"], "run")
        self.assertEqual(lanes["go-focused"]["disposition"], "not_triggered")

    def test_planning_fingerprints_all_selected_pattern_sets_in_one_walk(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            _base, head = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            with patch(
                "workflow_kernel.verification_repository.os.walk", wraps=os.walk,
            ) as walk:
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                    base_commit=git_commit(repository, BASE_REF),
                    head_commit=head,
                    environment=TEST_ENVIRONMENT,
                )
        self.assertEqual(walk.call_count, 1)

    def test_terminal_planning_fingerprints_commit_tree_once(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            with patch(
                "workflow_kernel.verification_repository.subprocess.run",
                wraps=subprocess.run,
            ) as run, patch(
                "workflow_kernel.verification_repository.run_bounded_capture",
                wraps=run_bounded_capture,
            ) as capture:
                plan = kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "merge_candidate", "high",
                    base_commit=base_commit,
                    head_commit=candidate_commit,
                    environment=TEST_ENVIRONMENT,
                )
        tree_scans = [
            call for call in capture.call_args_list
            if "ls-tree" in call.args[0]
            and call.args[0][-1] == candidate_commit
        ]
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(len(tree_scans), 1)
        self.assertFalse(any(
            "cat-file" in call.args[0] for call in run.call_args_list
        ))
        self.assertFalse(any(
            "show" in call.args[0] for call in run.call_args_list
        ))

    def test_tree_enumeration_bounds_unmatched_entries_and_process_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(directory)
            with patch(
                "workflow_kernel.verification_repository.MAX_PATHS", 1,
            ), self.assertRaises(VerificationPlannerError):
                tree_input_digests(
                    repository, git_commit(repository), {("missing/**",)},
                )
            for reason in (
                "command_timeout", "command_output_limit_exceeded",
            ):
                with self.subTest(reason=reason), patch(
                    "workflow_kernel.verification_repository.run_bounded_capture",
                    return_value={
                        "exit_code": None, "reason": reason, "stdout": b"",
                    },
                ), self.assertRaises(VerificationPlannerError):
                    tree_input_digests(
                        repository, git_commit(repository), {("**/*.go",)},
                    )

    def test_go_module_change_expands_focused_lane_to_all_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["go.mod"], "chunk", "high",
            )
        lane = {item["id"]: item for item in plan["lanes"]}["go-focused"]
        self.assertEqual(lane["packages"], ["./..."])

    def test_git_range_includes_deletions_staged_unstaged_and_untracked_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(directory)
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Changed = true\n",
            )
            (repository / "docs/readme.md").write_text("staged\n")
            subprocess.run(
                ["git", "add", "docs/readme.md"], cwd=repository, check=True,
            )
            (repository / "untracked.go").write_text("package untracked\n")
            (repository / "internal/dependent/dependent.go").unlink()
            paths = git_changed_paths(
                repository, "HEAD", include_worktree=True,
            )
        self.assertEqual(paths, [
            "docs/readme.md",
            "internal/dependent/dependent.go",
            "internal/source/source.go",
            "untracked.go",
        ])

    def test_each_boundary_builds_a_fresh_execution_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            level = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "execution_level", "medium",
            )
            _result, outcome = execute(profile, repository, level)
            self.assertEqual(outcome, "complete")
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "merge_candidate", "medium",
            )
        lanes = {lane["id"]: lane for lane in candidate["lanes"]}
        self.assertEqual(lanes["go-full"]["disposition"], "run")
        self.assertEqual(lanes["go-race"]["disposition"], "remote")

    def test_file_mode_change_changes_the_fresh_plan_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            first = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            first_lane = {
                item["id"]: item for item in first["lanes"]
            }["go-focused"]
            _result, outcome = execute(profile, repository, first)
            self.assertEqual(outcome, "complete")
            source = repository / "internal/source/source.go"
            source.chmod(0o744)
            changed = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
        lane = {item["id"]: item for item in changed["lanes"]}["go-focused"]
        self.assertEqual(lane["disposition"], "run")
        self.assertNotEqual(lane["input_digest"], first_lane["input_digest"])

    def test_stale_plan_is_rejected_before_command_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "counter"
            command = [
                sys.executable, "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(counter)!r}).write_text('ran')"
                ),
                "{packages}",
            ]
            repository, profile = self.repository(
                Path(directory) / "repository", profile_document(command),
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Stale = true\n",
            )
            with self.assertRaises(VerificationPlannerError):
                execute(profile, repository, plan)
            self.assertFalse(counter.exists())

    def test_execution_closure_change_changes_plan_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile, script = self.execution_repository(directory)
            profile["lanes"][1]["changed_paths"].append("tools/verify.py")
            profile["lanes"][1]["execution_paths"].append("tools/verify.py")
            (repository / ".dm/verification.json").write_text(
                json.dumps(profile), encoding="utf-8",
            )
            first = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            _result, outcome = execute(profile, repository, first)
            self.assertEqual(outcome, "complete")
            script.write_text("print('changed')\n", encoding="utf-8")
            base_commit = git_commit(repository, BASE_REF)
            head_commit = git_commit(repository)
            changed = kernel_build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go", "tools/verify.py"],
                "chunk", "low",
                base_commit=base_commit, head_commit=head_commit,
                include_worktree=True, environment=TEST_ENVIRONMENT,
            )
        self.assertNotEqual(
            changed["execution_closure_digest"], first["execution_closure_digest"],
        )

    def test_required_environment_change_rejects_plan_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "counter"
            command = [
                sys.executable, "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(counter)!r}).write_text('ran')"
                ),
                "{packages}",
            ]
            document = profile_document(command)
            document["lanes"][0]["required_environment"] = [
                "DM_VERIFICATION_SUBSTRATE", "GOFLAGS",
            ]
            document["lanes"][0]["execution_environment"] = [
                "DM_VERIFICATION_SUBSTRATE",
            ]
            repository, profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
                environment={**TEST_ENVIRONMENT, "GOFLAGS": "planned"},
            )
            with self.assertRaises(VerificationPlannerError):
                execute_plan(
                    profile, repository, plan,
                    environment={**TEST_ENVIRONMENT, "GOFLAGS": "changed"},
                )
            self.assertFalse(counter.exists())

    def test_include_worktree_plans_and_runs_mixed_dirty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            base_commit = git_commit(repository, BASE_REF)
            head_commit = git_commit(repository)
            (repository / "docs/readme.md").write_text("staged\n")
            subprocess.run(
                ["git", "-C", str(repository), "add", "docs/readme.md"],
                check=True,
            )
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Dirty = true\n",
            )
            (repository / "untracked.go").write_text("package untracked\n")
            changed_paths = git_changed_paths(
                repository, base_commit, head_ref=head_commit,
                include_worktree=True,
            )
            plan = kernel_build_plan(
                profile, repository, ".dm/verification.json", changed_paths,
                "chunk", "low", base_commit=base_commit,
                head_commit=head_commit, include_worktree=True,
                environment=TEST_ENVIRONMENT,
            )
            result = execute_plan(
                profile, repository, plan, environment=TEST_ENVIRONMENT,
            )
            outcome = result["status"]
        self.assertEqual(outcome, "complete")
        self.assertEqual(plan["request"]["changed_paths"], [
            "docs/readme.md", "internal/source/source.go", "untracked.go",
        ])
        self.assertTrue(any(
            lane["status"] == "passed" for lane in result["lanes"]
        ))

    def test_shell_strings_unknown_fields_and_symlink_inputs_are_rejected(self):
        document = profile_document()
        document["lanes"][0]["argv"] = "go test ./..."
        with self.assertRaises(VerificationPlannerError):
            validate_profile(document)
        document = profile_document()
        document["lanes"][0]["surprise"] = True
        with self.assertRaises(VerificationPlannerError):
            validate_profile(document)
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            target = repository / "outside.go"
            target.write_text("package outside\n")
            (repository / "internal/source/link.go").symlink_to(target)
            with self.assertRaises(VerificationPlannerError):
                build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                )

    def test_required_unresolved_lane_blocks_without_execution(self):
        document = profile_document()
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "counter"
            document["lanes"][0]["argv"] = [
                sys.executable, "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(counter)!r}).write_text('ran')"
                ),
            ]
            document["lanes"].append({
                "id": "required-harness",
                "tier": "harness",
                "cadences": ["merge_candidate"],
                "owner": "unresolved",
                "argv": [],
                "changed_paths": ["**/*.go"],
                "input_paths": ["**/*.go"],
                "required": True,
            })
            repository, profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "merge_candidate", "high",
            )
            result, outcome = execute(profile, repository, plan)
            self.assertFalse(counter.exists())
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(outcome, "failed")
        self.assertIn("blocked", {
            lane["status"] for lane in result["lanes"]
        })

    def test_required_remote_lane_remains_pending_for_independent_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )
            result, outcome = execute(profile, repository, candidate)
        self.assertEqual(outcome, "pending")
        self.assertIn("remote_pending", {
            lane["status"] for lane in result["lanes"]
        })

    def test_exact_head_and_clean_terminal_checkout_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            base = git_commit(repository, BASE_REF)
            head = git_commit(repository)
            (repository / "untracked.go").write_text("package untracked\n")
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json", [],
                    "merge_candidate", "high", base_commit=base,
                    head_commit=head, environment=TEST_ENVIRONMENT,
                )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["untracked.go"], "merge_candidate", "high",
                    base_commit=base, head_commit=head,
                    include_worktree=True, environment=TEST_ENVIRONMENT,
                )

    def test_execution_closure_changes_invalidate_a_saved_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile, script = self.execution_repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json", [],
                "chunk", "low", environment={"GOFLAGS": "-tags=trusted"},
            )
            script.write_text("print(\"changed\")\n", encoding="utf-8")
            with self.assertRaises(VerificationPlannerError):
                execute(
                    profile, repository, plan,
                    environment={"GOFLAGS": "-tags=trusted"},
                )

    def test_lane_cannot_replace_a_later_verification_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile, script = self.execution_repository(directory)
            marker = repository / "later-lane-ran"
            script.write_text("raise SystemExit(1)\n", encoding="utf-8")
            replacement = (
                "from pathlib import Path; "
                f"Path({str(marker)!r}).touch()\n"
            )
            profile["lanes"][0]["argv"] = [
                sys.executable, "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(script)!r}).write_text({replacement!r})"
                ),
            ]
            profile["lanes"][1]["argv"] = [sys.executable, str(script), "{packages}"]
            profile["lanes"][1]["changed_paths"].append("tools/verify.py")
            profile["lanes"][1]["execution_paths"].append("tools/verify.py")
            profile["lanes"][1]["after"] = ["doctor"]
            (repository / ".dm/verification.json").write_text(
                json.dumps(profile), encoding="utf-8",
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["tools/verify.py"], "chunk", "low",
            )
            result, outcome = execute(profile, repository, plan)
            marker_exists = marker.exists()
        self.assertEqual(outcome, "failed")
        self.assertFalse(marker_exists)
        self.assertEqual(result["lanes"][0]["reason"], "execution_closure_changed")
        self.assertNotIn("go-focused", {
            lane["lane_id"] for lane in result["lanes"]
        })

    def test_terminal_plan_rejects_ignored_input_absent_from_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            (repository / ".gitignore").write_text(
                "internal/source/generated.go\n", encoding="utf-8",
            )
            base_commit, candidate_commit = prepare_candidate(
                repository, [".gitignore"],
            )
            (repository / "internal/source/generated.go").write_text(
                "package source\n", encoding="utf-8",
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    [".gitignore"], "merge_candidate", "high",
                    base_commit=base_commit,
                    head_commit=candidate_commit,
                )

    def test_templ_change_schedules_generated_package_test(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            profile["lanes"][1]["changed_paths"].append("**/*.templ")
            (repository / ".dm/verification.json").write_text(
                json.dumps(profile), encoding="utf-8",
            )
            (repository / "internal/source/view.templ").write_text("package source\n")
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/view.templ"], "chunk", "low",
            )
        focused = {lane["id"]: lane for lane in plan["lanes"]}["go-focused"]
        self.assertEqual(focused["packages"], [
            "./internal/dependent", "./internal/source",
        ])
        self.assertEqual(focused["disposition"], "run")

    def test_declared_mutating_lane_refreshes_later_input_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            generated = repository / "internal/source/generated.go"
            profile["lanes"].insert(1, {
                "id": "generate",
                "tier": "fast",
                "cadences": ["chunk"],
                "owner": "local",
                "argv": [
                    sys.executable, "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({str(generated)!r}).write_text('package source\\n')"
                    ),
                ],
                "changed_paths": ["**/*.templ"],
                "input_paths": ["**/*.templ", ".dm/verification.json"],
                "execution_paths": [".dm/verification.json"],
                "mutates_repository": True,
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
            })
            profile["lanes"][2]["changed_paths"].append("**/*.templ")
            profile["lanes"][2]["input_paths"].append("**/*.templ")
            profile["lanes"][2]["after"] = ["generate"]
            (repository / "internal/source/view.templ").write_text("package source\n")
            (repository / ".dm/verification.json").write_text(json.dumps(profile))
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/view.templ"], "chunk", "low",
            )
            before = {
                lane["id"]: lane for lane in plan["lanes"]
            }["go-focused"]["input_digest"]
            result, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "complete")
        focused_result = [
            lane for lane in result["lanes"]
            if lane["lane_id"] == "go-focused"
        ][0]
        self.assertNotEqual(focused_result["input_digest"], before)

    def test_dependency_order_moves_generator_before_consumer(self):
        document = profile_document()
        generator = {
            "id": "generate",
            "tier": "fast",
            "cadences": ["chunk"],
            "owner": "local",
            "argv": [sys.executable, "-c", "raise SystemExit(0)"],
            "changed_paths": ["**/*.go"],
            "input_paths": [".dm/verification.json"],
            "execution_paths": [".dm/verification.json"],
            "mutates_repository": True,
            "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
            "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
        }
        document["lanes"][1]["after"] = ["generate"]
        document["lanes"].append(generator)
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory, document)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
        ids = [lane["id"] for lane in plan["lanes"]]
        self.assertLess(ids.index("generate"), ids.index("go-focused"))

    def test_invalid_dependency_graphs_are_rejected(self):
        cases = {
            "unknown": [["missing"], []],
            "self": [["doctor"], []],
            "cycle": [["go-focused"], ["doctor"]],
        }
        for label, dependencies in cases.items():
            with self.subTest(label=label):
                document = profile_document()
                document["lanes"][0]["after"] = dependencies[0]
                document["lanes"][1]["after"] = dependencies[1]
                with self.assertRaises(VerificationPlannerError):
                    validate_profile(document)

    def test_failed_dependency_blocks_consumer_without_running_it(self):
        with tempfile.TemporaryDirectory() as directory:
            counter = Path(directory) / "consumer-ran"
            document = profile_document([
                sys.executable, "-c",
                f"from pathlib import Path; Path({str(counter)!r}).touch()",
                "{packages}",
            ])
            document["lanes"].append({
                "id": "generate",
                "tier": "fast",
                "cadences": ["chunk"],
                "owner": "local",
                "argv": [sys.executable, "-c", "raise SystemExit(9)"],
                "changed_paths": ["**/*.go"],
                "input_paths": [".dm/verification.json"],
                "execution_paths": [".dm/verification.json"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "execution_environment": ["DM_VERIFICATION_SUBSTRATE"],
            })
            document["lanes"][1]["after"] = ["generate"]
            repository, profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            result, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        self.assertFalse(counter.exists())
        self.assertIn("dependency_not_passed", {
            lane["reason"] for lane in result["lanes"]
        })

    def test_repository_command_receives_isolated_stdin_home_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "execution-probe.json"
            command = (
                "import json,os,sys; from pathlib import Path; "
                "payload={"
                "'stdin': len(sys.stdin.buffer.read()), "
                "'home': list(Path(os.environ['HOME']).iterdir()), "
                "'goflags': os.environ.get('GOFLAGS'), "
                "'secret': os.environ.get('SECRET_SENTINEL')}; "
                f"Path({str(probe)!r}).write_text("
                "json.dumps(payload, default=str))"
            )
            document = profile_document([
                sys.executable, "-c", command, "{packages}",
            ])
            repository, profile = self.repository(directory, document)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
                environment={
                    "GOFLAGS": "-tags=allowed",
                    "SECRET_SENTINEL": "must-not-cross",
                },
            )
            _result, outcome = execute(
                profile, repository, plan,
                environment={
                    "GOFLAGS": "-tags=allowed",
                    "SECRET_SENTINEL": "must-not-cross",
                },
            )
            observed = json.loads(probe.read_text())
        self.assertEqual(outcome, "complete")
        self.assertEqual(observed, {
            "stdin": 0,
            "home": [],
            "goflags": "-tags=allowed",
            "secret": None,
        })

    def test_sigterm_ignoring_descendants_obey_timeout_and_output_bounds(self):
        for trigger in ("timeout", "output"):
            with self.subTest(trigger=trigger):
                with tempfile.TemporaryDirectory() as directory:
                    pid_path = Path(directory) / "grandchild.pid"
                    grandchild = (
                        "import signal,time; "
                        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                        "time.sleep(30)"
                    )
                    parent_loop = (
                        "while True: print('x' * 1024, flush=True)"
                        if trigger == "output" else "time.sleep(30)"
                    )
                    command = (
                        "import signal,subprocess,sys,time; "
                        "from pathlib import Path; "
                        f"child=subprocess.Popen([sys.executable,'-c',{grandchild!r}]); "
                        f"Path({str(pid_path)!r}).write_text(str(child.pid)); "
                        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                        f"exec({parent_loop!r})"
                    )
                    document = profile_document([
                        sys.executable, "-c", command, "{packages}",
                    ])
                    document["lanes"][1]["timeout_seconds"] = (
                        10 if trigger == "output" else 1
                    )
                    repository, profile = self.repository(
                        Path(directory) / "repository", document,
                    )
                    plan = build_plan(
                        profile, repository, ".dm/verification.json",
                        ["internal/source/source.go"], "chunk", "low",
                    )
                    started = time.monotonic()
                    output_limit = (
                        patch(
                            "workflow_kernel.verification_execution."
                            "MAX_OUTPUT_BYTES",
                            256,
                        )
                        if trigger == "output" else patch(
                            "workflow_kernel.verification_execution."
                            "MAX_OUTPUT_BYTES",
                            16 * 1024 * 1024,
                        )
                    )
                    with output_limit:
                        _result, outcome = execute(
                            profile, repository, plan,
                        )
                    elapsed = time.monotonic() - started
                    descendant_pid = int(pid_path.read_text())
                    gone = False
                    for _attempt in range(40):
                        try:
                            os.kill(descendant_pid, 0)
                        except ProcessLookupError:
                            gone = True
                            break
                        time.sleep(0.05)
                    if not gone:
                        os.kill(descendant_pid, 9)
                self.assertEqual(outcome, "failed")
                self.assertLess(elapsed, 7)
                self.assertTrue(gone)

    def test_successful_parent_cannot_leave_redirected_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_path = Path(directory) / "redirected-child.pid"
            child = "import time; time.sleep(30)"
            command = (
                "import subprocess,sys; from pathlib import Path; "
                f"child=subprocess.Popen([sys.executable,'-c',{child!r}],"
                "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                "stderr=subprocess.DEVNULL); "
                f"Path({str(pid_path)!r}).write_text(str(child.pid))"
            )
            document = profile_document([
                sys.executable, "-c", command, "{packages}",
            ])
            repository, profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            result, outcome = execute(profile, repository, plan)
            descendant_pid = int(pid_path.read_text())
            gone = False
            for _attempt in range(40):
                try:
                    os.kill(descendant_pid, 0)
                except ProcessLookupError:
                    gone = True
                    break
                time.sleep(0.05)
            if not gone:
                os.kill(descendant_pid, 9)
        focused = [
            lane for lane in result["lanes"]
            if lane["lane_id"] == "go-focused"
        ][0]
        self.assertEqual(outcome, "failed")
        self.assertEqual(
            focused["reason"], "command_descendants_terminated",
        )
        self.assertTrue(gone)

    def test_undeclared_input_mutation_fails_final_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            source = repository / "internal/source/source.go"
            document = profile_document([
                sys.executable, "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(source)!r}).write_text('package source\\n"
                    "const Changed = true\\n')"
                ),
                "{packages}",
            ])
            repository, profile = self.repository(repository, document)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            result, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        self.assertIn("undeclared_repository_mutation", {
            lane["reason"] for lane in result["lanes"]
        })

    def test_output_limit_terminates_process_without_unbounded_capture(self):
        document = profile_document([
            sys.executable, "-c", "print('x' * 4096)", "{packages}",
        ])
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory, document)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            with patch(
                "workflow_kernel.verification_execution.MAX_OUTPUT_BYTES", 32,
            ):
                result, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        focused = [
            lane for lane in result["lanes"]
            if lane["lane_id"] == "go-focused"
        ][0]
        self.assertEqual(
            focused["reason"], "command_output_limit_exceeded",
        )
        self.assertLessEqual(focused["stdout_bytes"], 65536)

    def test_trusted_command_can_skip_recycled_post_reap_process_group(self):
        real_killpg = os.killpg

        def recycled_group(group_id, sent_signal):
            if sent_signal == 0:
                return None
            return real_killpg(group_id, sent_signal)

        with tempfile.TemporaryDirectory() as directory, patch(
            "workflow_kernel.verification_execution.os.killpg",
            side_effect=recycled_group,
        ):
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )

        self.assertTrue(plan["lanes"])

    def test_output_limit_falls_back_when_group_signal_is_denied(self):
        real_killpg = os.killpg

        def deny_group_signals(pid, sent_signal):
            if sent_signal in (signal.SIGTERM, signal.SIGKILL):
                raise PermissionError("group signalling denied")
            return real_killpg(pid, sent_signal)

        with tempfile.TemporaryDirectory() as directory:
            pid_path = Path(directory) / "leader.pid"
            command = (
                "import os,time; from pathlib import Path; "
                f"Path({str(pid_path)!r}).write_text(str(os.getpid())); "
                "print('x' * 4096, flush=True); time.sleep(30)"
            )
            document = profile_document([
                sys.executable, "-c", command, "{packages}",
            ])
            repository, profile = self.repository(directory, document)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            with patch(
                "workflow_kernel.verification_execution.MAX_OUTPUT_BYTES", 32,
            ), patch(
                "workflow_kernel.verification_execution.os.killpg",
                side_effect=deny_group_signals,
            ):
                result, outcome = execute(profile, repository, plan)
            leader_pid = int(pid_path.read_text())
            leader_gone = False
            for _attempt in range(40):
                try:
                    os.kill(leader_pid, 0)
                except ProcessLookupError:
                    leader_gone = True
                    break
                time.sleep(0.05)
            if not leader_gone:
                os.kill(leader_pid, signal.SIGKILL)
        self.assertEqual(outcome, "failed")
        focused = [
            lane for lane in result["lanes"]
            if lane["lane_id"] == "go-focused"
        ][0]
        self.assertEqual(
            focused["reason"], "command_output_limit_exceeded",
        )
        self.assertLessEqual(focused["stdout_bytes"], 65536)
        self.assertTrue(leader_gone)

    def test_symlinked_input_directory_and_unbounded_arrays_are_rejected(self):
        document = profile_document()
        document["lanes"][0]["execution_environment"] = [
            f"SAFE_VALUE_{index}" for index in range(257)
        ]
        with self.assertRaises(VerificationPlannerError):
            validate_profile(document)
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(Path(directory) / "repository")
            outside = Path(directory) / "outside"
            outside.mkdir()
            (outside / "source.go").write_text("package outside\n")
            (repository / "linked").symlink_to(outside, target_is_directory=True)
            profile["lanes"][1]["input_paths"].append("linked/**/*.go")
            with self.assertRaises(VerificationPlannerError):
                build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                )

    def test_cli_plans_and_returns_current_invocation_result(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(Path(directory) / "repository")
            plan_path = Path(directory) / "plan.json"
            env = dict(
                os.environ, PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )

            def run_cli(arguments):
                return subprocess.run(
                    [sys.executable, "-m", "workflow_kernel", *arguments],
                    env=env, capture_output=True, check=False,
                )

            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            command = [
                "plan-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "chunk", "--risk", "low",
                "--base-ref", base_commit, "--candidate-ref", candidate_commit,
                "--output", str(plan_path),
            ]
            planned = run_cli(command)
            self.assertEqual(planned.returncode, 0, planned.stderr.decode())
            run = run_cli([
                "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
            ])
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            result = json.loads(run.stdout)
            self.assertEqual(result["artifact_role"], "repository_verification_result")
            self.assertEqual(result["status"], "complete")
            self.assertIn("go-focused", {
                lane["lane_id"] for lane in result["lanes"]
            })

            mismatched = json.loads(plan_path.read_text())
            mismatched["profile_ref"] = "README.md"
            plan_path.write_text(json.dumps(mismatched), encoding="utf-8")
            rejected = run_cli([
                "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
            ])
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(rejected.stdout, b"")

    def test_cli_stdout_is_one_json_result_when_a_lane_prints_output(self):
        document = profile_document([
            sys.executable, "-c", "print('lane-output')", "{packages}",
        ])
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan_path = Path(directory) / "plan.json"
            environment = dict(
                os.environ, PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )
            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            planned = subprocess.run([
                sys.executable, "-m", "workflow_kernel", "plan-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "chunk", "--risk", "low",
                "--base-ref", base_commit, "--candidate-ref", candidate_commit,
                "--output", str(plan_path),
            ], env=environment, capture_output=True, check=False, text=True)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            run = subprocess.run([
                sys.executable, "-m", "workflow_kernel", "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
            ], env=environment, capture_output=True, check=False, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "complete")
        self.assertNotIn("lane-output", run.stdout)
        self.assertIn("lane-output", run.stderr)

    def test_cli_include_worktree_plans_and_runs_mixed_dirty_state(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(Path(directory) / "repository")
            plan_path = Path(directory) / "dirty-plan.json"
            env = dict(
                os.environ, PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )
            base_commit = git_commit(repository, BASE_REF)
            head_commit = git_commit(repository)
            (repository / "docs/readme.md").write_text("staged\n")
            subprocess.run(
                ["git", "-C", str(repository), "add", "docs/readme.md"],
                check=True,
            )
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Dirty = true\n",
            )
            (repository / "untracked.go").write_text("package untracked\n")
            planned = subprocess.run([
                sys.executable, "-m", "workflow_kernel",
                "plan-verification", "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "chunk", "--risk", "low",
                "--base-ref", base_commit, "--candidate-ref", head_commit,
                "--include-worktree", "--output", str(plan_path),
            ], env=env, capture_output=True, check=False, text=True)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            plan = json.loads(plan_path.read_text())
            self.assertEqual(plan["request"]["changed_paths"], [
                "docs/readme.md", "internal/source/source.go", "untracked.go",
            ])
            run = subprocess.run([
                sys.executable, "-m", "workflow_kernel",
                "run-verification", "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
            ], env=env, capture_output=True, check=False, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "complete")

            subprocess.run(
                ["git", "-C", str(repository), "add", "--all"], check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "advance head"],
                check=True, capture_output=True,
            )
            stale = subprocess.run([
                sys.executable, "-m", "workflow_kernel",
                "plan-verification", "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "chunk", "--risk", "low",
                "--base-ref", base_commit, "--candidate-ref", head_commit,
                "--include-worktree", "--output", str(plan_path),
            ], env=env, capture_output=True, check=False, text=True)
            self.assertNotEqual(stale.returncode, 0)

    def test_cli_required_remote_lane_exits_three_and_reports_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(Path(directory) / "repository")
            plan_path = Path(directory) / "remote-plan.json"
            env = dict(
                os.environ, PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )
            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            planned = subprocess.run([
                sys.executable, "-m", "workflow_kernel",
                "plan-verification", "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "merge_candidate", "--risk", "high",
                "--base-ref", base_commit, "--candidate-ref", candidate_commit,
                "--output", str(plan_path),
            ], env=env, capture_output=True, check=False, text=True)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            run = subprocess.run([
                sys.executable, "-m", "workflow_kernel",
                "run-verification", "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
            ], env=env, capture_output=True, check=False, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "pending")
            remote = [
                lane for lane in json.loads(run.stdout)["lanes"]
                if lane["status"] == "remote_pending"
            ]
        self.assertEqual(len(remote), 1)
        self.assertEqual(json.loads(run.stdout)["head_commit"], candidate_commit)

    def test_cli_has_no_broker_commands_or_inputs(self):
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        help_result = subprocess.run(
            [sys.executable, "-m", "workflow_kernel", "--help"],
            env=env, capture_output=True, check=False, text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        combined = help_result.stdout + help_result.stderr
        for removed in (
            "approve-verification-profile", "record-verification-result",
            "authorize-verification-contract-revision",
            "revise-verification-contract", "receipt-key-stdin",
            "provider-attestation", "repository-verification-receipts",
            "--receipts",
        ):
            self.assertNotIn(removed, combined)
        for command in ("plan-verification", "run-verification"):
            help_result = subprocess.run(
                [sys.executable, "-m", "workflow_kernel", command, "--help"],
                env=env, capture_output=True, check=False, text=True,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertNotIn("--receipts", help_result.stdout)
        run_help = subprocess.run(
            [sys.executable, "-m", "workflow_kernel", "run-verification", "--help"],
            env=env, capture_output=True, check=False, text=True,
        )
        self.assertNotIn("--output", run_help.stdout)


if __name__ == "__main__":
    unittest.main()
