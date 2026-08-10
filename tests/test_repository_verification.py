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
from workflow_kernel.verification_authority import issue_profile_approval
from workflow_kernel.verification_errors import VerificationPlannerError
from workflow_kernel.verification_execution import run_bounded_capture
from workflow_kernel.verification_orchestrator import execute_plan
from workflow_kernel.verification_repository import (
    git_changed_paths, tree_input_digests, validate_profile,
)
from workflow_kernel.verification_planning import build_plan as kernel_build_plan
from workflow_kernel.verification_provider import record_provider_result
from workflow_kernel.verification_receipts import (
    merge_receipt_ledgers, seal_provider_attestation, validate_receipt,
)


PROFILE_SCHEMA = KERNEL_REFERENCES / "repository-verification-profile-schema.json"
APPROVAL_SCHEMA = (
    KERNEL_REFERENCES / "repository-verification-approval-schema.json"
)
PLAN_SCHEMA = KERNEL_REFERENCES / "repository-verification-plan-schema.json"
PROVIDER_ATTESTATION_SCHEMA = (
    KERNEL_REFERENCES
    / "repository-verification-provider-attestation-schema.json"
)
RECEIPT_SCHEMA = KERNEL_REFERENCES / "repository-verification-receipts-schema.json"
ASSEMBLY_EXAMPLE = (
    KERNEL_REFERENCES.parents[3]
    / "assembly/references/repository-verification-profile.example.json"
)
RECEIPT_KEY = b"repository-verification-test-key-32-bytes"
APPROVED_AT = "2026-07-30T00:00:00Z"
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


def approval(profile, repository, *, environment=None):
    base_commit = git_commit(repository, BASE_REF)
    candidate_commit = git_commit(repository)
    return issue_profile_approval(
        profile, repository, ".dm/verification.json",
        trusted_base_commit=base_commit, candidate_commit=candidate_commit,
        run_id="verification-test-run",
        authorization_event_id="operator-approved-verification",
        approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
        environment=test_environment(environment),
    )


def build_plan(
    profile, repository, profile_ref, changed_paths, boundary, risk, **kwargs,
):
    _base_commit, head_commit = prepare_candidate(repository, changed_paths)
    environment = test_environment(kwargs.get("environment"))
    kwargs["environment"] = environment
    kwargs.setdefault("receipt_key", RECEIPT_KEY)
    kwargs.setdefault(
        "approval", approval(profile, repository, environment=environment),
    )
    kwargs.setdefault("head_commit", head_commit)
    return kernel_build_plan(
        profile, repository, profile_ref, changed_paths, boundary, risk,
        **kwargs,
    )


def execute(profile, repository, plan, *, receipt_ledger=None, environment=None):
    environment = test_environment(environment)
    return execute_plan(
        profile, repository, plan,
        receipt_ledger=receipt_ledger,
        receipt_key=RECEIPT_KEY,
        approval=approval(profile, repository, environment=environment),
        environment=environment,
    )


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
                "authority_paths": [".dm/verification.json"],
                "cache": "never",
                "cache_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
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
                "authority_paths": [".dm/verification.json"],
                "package_selector": "go_changed",
                "declared_dependents": {
                    "./internal/source": ["./internal/dependent"],
                },
                "cache": "content",
                "cache_environment": [
                    "GOFLAGS", "DM_VERIFICATION_SUBSTRATE",
                ],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
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
                "authority_paths": [".dm/verification.json"],
                "cache": "content",
                "cache_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
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
                "cache": "content",
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

    def authority_repository(self, directory):
        repository, profile = self.repository(directory)
        script = repository / "tools/verify.py"
        script.parent.mkdir()
        script.write_text("print('trusted')\n", encoding="utf-8")
        profile["lanes"][0]["authority_paths"].append("tools/verify.py")
        profile["lanes"][0]["cache_environment"] = [
            "GOFLAGS", "DM_VERIFICATION_SUBSTRATE",
        ]
        profile["lanes"][0]["authority_environment"] = [
            "GOFLAGS", "DM_VERIFICATION_SUBSTRATE",
        ]
        (repository / ".dm/verification.json").write_text(
            json.dumps(profile), encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(repository), "add", "."], check=True,
        )
        subprocess.run(
            ["git", "-C", str(repository), "commit", "-m", "authority"],
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
            receipts, outcome = execute(
                profile, repository, plan, environment={"GOFLAGS": "-tags=dev"},
            )
            approval_document = approval(
                profile, repository, environment={"GOFLAGS": "-tags=dev"},
            )
            provider_attestation = seal_provider_attestation({
                "schema_version": 1,
                "artifact_role": "repository_verification_provider_attestation",
                "provider": "github",
                "provider_run_id": "schema-fixture",
                "head_commit": git_commit(repository),
                "evidence_digest": "sha256:" + "d" * 64,
                "observed_at": "2026-07-30T00:30:00Z",
                "outcome": "passed",
                "exit_code": 0,
            }, RECEIPT_KEY)
        self.assertEqual(outcome, "complete")
        self.assertTrue(schema_matches(
            validate_profile(profile),
            json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertTrue(schema_matches(
            approval_document,
            json.loads(APPROVAL_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertTrue(schema_matches(
            provider_attestation,
            json.loads(PROVIDER_ATTESTATION_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertTrue(schema_matches(
            plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
        ))
        self.assertTrue(schema_matches(
            receipts, json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8")),
        ))
        invalid_receipt = {
            **receipts["receipts"][0], "tier": "bogus",
        }
        self.assertFalse(schema_matches(
            {
                "schema_version": 1,
                "artifact_role": "repository_verification_receipts",
                "receipts": [invalid_receipt],
            },
            json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8")),
        ))
        with self.assertRaises(VerificationPlannerError):
            validate_receipt(invalid_receipt, RECEIPT_KEY)
        invalid_plan = {
            **plan,
            "lanes": [{**plan["lanes"][0], "owner": "bogus"}, *plan["lanes"][1:]],
        }
        self.assertFalse(schema_matches(
            invalid_plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
        ))
        invalid_cache_plan = {
            **plan,
            "lanes": [
                {**plan["lanes"][0], "cache": "bogus"}, *plan["lanes"][1:]
            ],
        }
        self.assertFalse(schema_matches(
            invalid_cache_plan,
            json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
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
        lane["cache_environment"] = ["GOFLAGS"]
        lane.pop("required_environment")
        lane.pop("authority_environment")
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
                lane.pop("cache_environment")
                lane.pop("required_environment")
                lane.pop("authority_environment")
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
            approved = approval(profile, repository)
            with patch(
                "workflow_kernel.verification_repository.os.walk", wraps=os.walk,
            ) as walk:
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                    receipt_key=RECEIPT_KEY, approval=approved,
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
            approved = issue_profile_approval(
                profile, repository, ".dm/verification.json",
                trusted_base_commit=base_commit,
                candidate_commit=candidate_commit,
                run_id="batched-terminal-tree",
                authorization_event_id="approved-exact-head",
                approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
                environment=TEST_ENVIRONMENT,
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
                    receipt_key=RECEIPT_KEY, approval=approved,
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
        self.assertEqual(sum(
            "show" in call.args[0] for call in run.call_args_list
        ), 1)

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

    def test_full_lane_runs_once_and_reuses_at_unchanged_merge_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            level = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "execution_level", "medium",
            )
            receipts, outcome = execute(profile, repository, level)
            self.assertEqual(outcome, "complete")
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "merge_candidate", "medium",
                receipt_ledger=receipts, receipt_key=RECEIPT_KEY,
            )
        lanes = {lane["id"]: lane for lane in candidate["lanes"]}
        self.assertEqual(lanes["go-full"]["disposition"], "reuse")
        self.assertEqual(lanes["go-race"]["disposition"], "remote")

    def test_relevant_source_change_invalidates_receipt_but_docs_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            first = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            receipts, outcome = execute(profile, repository, first)
            self.assertEqual(outcome, "complete")
            unchanged = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
                receipt_ledger=receipts, receipt_key=RECEIPT_KEY,
            )
            unchanged_lane = {
                lane["id"]: lane for lane in unchanged["lanes"]
            }["go-focused"]
            self.assertEqual(unchanged_lane["disposition"], "reuse")
            (repository / "docs/readme.md").write_text("changed docs\n")
            docs_only = build_plan(
                profile, repository, ".dm/verification.json",
                ["docs/readme.md", "internal/source/source.go"], "chunk", "low",
                receipt_ledger=receipts, receipt_key=RECEIPT_KEY,
            )
            docs_lane = {
                lane["id"]: lane for lane in docs_only["lanes"]
            }["go-focused"]
            self.assertEqual(docs_lane["disposition"], "reuse")
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Changed = true\n",
            )
            changed = build_plan(
                profile, repository, ".dm/verification.json",
                ["docs/readme.md", "internal/source/source.go"], "chunk", "low",
                receipt_ledger=receipts, receipt_key=RECEIPT_KEY,
            )
        changed_lane = {
            lane["id"]: lane for lane in changed["lanes"]
        }["go-focused"]
        self.assertEqual(changed_lane["disposition"], "run")

    def test_file_mode_change_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            first = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            receipts, outcome = execute(profile, repository, first)
            self.assertEqual(outcome, "complete")
            source = repository / "internal/source/source.go"
            source.chmod(0o744)
            changed = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
                receipt_ledger=receipts, receipt_key=RECEIPT_KEY,
            )
        lane = {item["id"]: item for item in changed["lanes"]}["go-focused"]
        self.assertEqual(lane["disposition"], "run")

    def test_concurrent_receipt_suffixes_merge_without_lost_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            first_plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            first, first_outcome = execute(profile, repository, first_plan)
            self.assertEqual(first_outcome, "complete")
            (repository / "internal/source/source.go").write_text(
                "package source\nconst Concurrent = true\n",
            )
            second_plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            second, second_outcome = execute(profile, repository, second_plan)
            self.assertEqual(second_outcome, "complete")
            merged = merge_receipt_ledgers(
                first, second, 0, RECEIPT_KEY,
            )
        focused_keys = {
            receipt["cache_key"] for receipt in merged["receipts"]
            if receipt["lane_id"] == "go-focused"
        }
        self.assertEqual(len(focused_keys), 2)

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

    def test_execution_requires_host_authenticated_profile_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            with self.assertRaises(VerificationPlannerError):
                execute_plan(
                    profile, repository, plan, receipt_key=RECEIPT_KEY,
                    approval={
                        **approval(profile, repository),
                        "approval_auth": "hmac-sha256:" + "0" * 64,
                    },
                )

    def test_fabricated_receipt_cannot_suppress_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            focused = {lane["id"]: lane for lane in plan["lanes"]}["go-focused"]
            forged = {
                "schema_version": 1,
                "artifact_role": "repository_verification_receipts",
                "receipts": [{
                    "status": "passed",
                    "cache_key": focused["cache_key"],
                }],
            }
            with self.assertRaises(VerificationPlannerError):
                build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                    receipt_ledger=forged, receipt_key=RECEIPT_KEY,
                )

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
            receipts, outcome = execute(profile, repository, plan)
            self.assertFalse(counter.exists())
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(outcome, "failed")
        self.assertIn("blocked", {
            receipt["status"] for receipt in receipts["receipts"]
        })

    def test_required_remote_lane_is_pending_until_signed_pass_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )
            receipts, outcome = execute(profile, repository, candidate)
        self.assertEqual(outcome, "pending")
        self.assertIn("remote_pending", {
            receipt["status"] for receipt in receipts["receipts"]
        })

    def test_authenticated_provider_result_completes_exact_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            approved = approval(profile, repository)
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )
            pending_receipts, outcome = execute(
                profile, repository, candidate,
            )
            self.assertEqual(outcome, "pending")
            attestation = seal_provider_attestation({
                "schema_version": 1,
                "artifact_role": "repository_verification_provider_attestation",
                "provider": "github",
                "provider_run_id": "github-run-123",
                "head_commit": git_commit(repository),
                "evidence_digest": "sha256:" + "c" * 64,
                "observed_at": "2026-07-30T01:00:00Z",
                "outcome": "passed",
                "exit_code": 0,
            }, RECEIPT_KEY)
            authenticated = record_provider_result(
                profile, repository, candidate, approval=approved,
                receipt_ledger=pending_receipts, receipt_key=RECEIPT_KEY,
                lane_id="go-race", provider_attestation=attestation,
                environment=TEST_ENVIRONMENT,
            )
            completed_plan = kernel_build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
                receipt_ledger=authenticated, receipt_key=RECEIPT_KEY,
                approval=approved, head_commit=git_commit(repository),
                environment=TEST_ENVIRONMENT,
            )
            race = {
                lane["id"]: lane for lane in completed_plan["lanes"]
            }["go-race"]
            self.assertEqual(race["disposition"], "reuse")
            _receipts, outcome = execute(
                profile, repository, completed_plan,
                receipt_ledger=authenticated,
            )
        self.assertEqual(outcome, "complete")

    def test_provider_result_rejects_unsealed_caller_assertions(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            candidate = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )
            pending_receipts, _outcome = execute(
                profile, repository, candidate,
            )
            forged = {
                "schema_version": 1,
                "artifact_role": "repository_verification_provider_attestation",
                "provider": "github",
                "provider_run_id": "made-up-run",
                "head_commit": git_commit(repository),
                "evidence_digest": "sha256:" + "e" * 64,
                "observed_at": "2026-07-30T01:00:00Z",
                "outcome": "passed",
                "exit_code": 0,
                "attestation_auth": "hmac-sha256:" + "0" * 64,
            }
            with self.assertRaises(VerificationPlannerError):
                record_provider_result(
                    profile, repository, candidate,
                    approval=approval(profile, repository),
                    receipt_ledger=pending_receipts,
                    receipt_key=RECEIPT_KEY, lane_id="go-race",
                    provider_attestation=forged,
                    environment=TEST_ENVIRONMENT,
                )

    def test_remote_receipt_is_not_reused_for_another_exact_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            first = build_plan(
                profile, repository, ".dm/verification.json",
                [], "merge_candidate", "high",
            )
            pending, _outcome = execute(profile, repository, first)
            first_approval = approval(profile, repository)
            attestation = seal_provider_attestation({
                "schema_version": 1,
                "artifact_role": "repository_verification_provider_attestation",
                "provider": "github",
                "provider_run_id": "first-run",
                "head_commit": git_commit(repository),
                "evidence_digest": "sha256:" + "f" * 64,
                "observed_at": "2026-07-30T01:00:00Z",
                "outcome": "passed",
                "exit_code": 0,
            }, RECEIPT_KEY)
            authenticated = record_provider_result(
                profile, repository, first, approval=first_approval,
                receipt_ledger=pending, receipt_key=RECEIPT_KEY,
                lane_id="go-race", provider_attestation=attestation,
                environment=TEST_ENVIRONMENT,
            )
            source = repository / "internal/source/source.go"
            source.write_text(
                source.read_text(encoding="utf-8") + "\n// second candidate\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", str(source)], check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "second candidate"],
                check=True, capture_output=True,
            )
            second_approval = approval(profile, repository)
            second = kernel_build_plan(
                profile, repository, ".dm/verification.json",
                git_changed_paths(
                    repository, git_commit(repository, BASE_REF),
                    head_ref=git_commit(repository),
                ),
                "merge_candidate", "high", receipt_ledger=authenticated,
                receipt_key=RECEIPT_KEY, approval=second_approval,
                head_commit=git_commit(repository),
                environment=TEST_ENVIRONMENT,
            )
        race = {lane["id"]: lane for lane in second["lanes"]}["go-race"]
        self.assertEqual(race["disposition"], "remote")

    def test_profile_approval_rejects_changed_execution_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            approved = approval(profile, repository)
            (repository / ".dm/verification.json").write_text(
                json.dumps({**profile, "profile_id": "changed-on-disk"}),
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["internal/source/source.go"], "chunk", "low",
                    receipt_key=RECEIPT_KEY, approval=approved,
                    head_commit=git_commit(repository),
                )

    def test_profile_approval_rejects_nonexistent_full_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            with self.assertRaises(VerificationPlannerError):
                issue_profile_approval(
                    profile, repository, ".dm/verification.json",
                    trusted_base_commit="a" * 40,
                    candidate_commit=git_commit(repository),
                    run_id="invalid-base", authorization_event_id="invalid",
                    approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
                )

    def test_approval_binds_authority_file_mode_environment_and_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, profile, script = self.authority_repository(directory)
            approved = approval(
                profile, repository, environment={"GOFLAGS": "-tags=trusted"},
            )
            script.write_text("print('candidate')\n", encoding="utf-8")
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json", [],
                    "chunk", "low", receipt_key=RECEIPT_KEY,
                    approval=approved, head_commit=git_commit(repository),
                    environment={"GOFLAGS": "-tags=trusted"},
                )

    def test_approval_rejects_post_seal_checkout_and_head_drift(self):
        for include_worktree in (False, True):
            for state in ("untracked", "staged"):
                with self.subTest(
                    state=state, include_worktree=include_worktree,
                ):
                    with tempfile.TemporaryDirectory() as directory:
                        repository, profile = self.repository(directory)
                        approved = issue_profile_approval(
                            profile, repository, ".dm/verification.json",
                            trusted_base_commit=git_commit(repository, BASE_REF),
                            candidate_commit=git_commit(repository),
                            include_worktree=include_worktree,
                            run_id="checkout-drift",
                            authorization_event_id="approved-clean-checkout",
                            approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
                        )
                        added = repository / "internal/source/late.go"
                        added.write_text("package source\n", encoding="utf-8")
                        if state == "staged":
                            subprocess.run(
                                ["git", "-C", str(repository), "add", str(added)],
                                check=True,
                            )
                        with self.assertRaises(VerificationPlannerError):
                            kernel_build_plan(
                                profile, repository, ".dm/verification.json", [],
                                "chunk", "low", receipt_key=RECEIPT_KEY,
                                approval=approved,
                                head_commit=git_commit(repository),
                            )

        with tempfile.TemporaryDirectory() as directory:
            repository, profile = self.repository(directory)
            approved = approval(profile, repository)
            (repository / "docs/readme.md").write_text(
                "moved head\n", encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "docs/readme.md"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "move head"],
                check=True, capture_output=True,
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["docs/readme.md"], "chunk", "low",
                    receipt_key=RECEIPT_KEY, approval=approved,
                    head_commit=git_commit(repository),
                )

        with tempfile.TemporaryDirectory() as directory:
            repository, profile, script = self.authority_repository(directory)
            approved = approval(
                profile, repository, environment={"GOFLAGS": "-tags=trusted"},
            )
            script.chmod(0o755)
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json", [],
                    "chunk", "low", receipt_key=RECEIPT_KEY,
                    approval=approved, head_commit=git_commit(repository),
                    environment={"GOFLAGS": "-tags=trusted"},
                )

        with tempfile.TemporaryDirectory() as directory:
            repository, profile, _script = self.authority_repository(directory)
            approved = approval(
                profile, repository, environment={"GOFLAGS": "-tags=trusted"},
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json", [],
                    "chunk", "low", receipt_key=RECEIPT_KEY,
                    approval=approved, head_commit=git_commit(repository),
                    environment={"GOFLAGS": "-tags=changed"},
                )

        with tempfile.TemporaryDirectory() as directory:
            repository, profile, _script = self.authority_repository(directory)
            approved = approval(
                profile, repository, environment={"GOFLAGS": "-tags=trusted"},
            )
            (repository / "docs/readme.md").write_text(
                "second candidate\n", encoding="utf-8",
            )
            subprocess.run(
                ["git", "-C", str(repository), "add", "docs/readme.md"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repository), "commit", "-m", "candidate b"],
                check=True, capture_output=True,
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    ["docs/readme.md"], "chunk", "low",
                    receipt_key=RECEIPT_KEY, approval=approved,
                    head_commit=git_commit(repository),
                    environment={"GOFLAGS": "-tags=trusted"},
                )

    def test_approval_rejects_same_path_content_drift(self):
        for include_worktree in (False, True):
            with self.subTest(include_worktree=include_worktree):
                with tempfile.TemporaryDirectory() as directory:
                    repository, profile = self.repository(directory)
                    base_commit, candidate_commit = prepare_candidate(
                        repository, ["internal/source/source.go"],
                    )
                    source = repository / "internal/source/source.go"
                    if include_worktree:
                        source.write_text(
                            "package source\n// approved dirty state\n",
                            encoding="utf-8",
                        )
                    approved = issue_profile_approval(
                        profile, repository, ".dm/verification.json",
                        trusted_base_commit=base_commit,
                        candidate_commit=candidate_commit,
                        include_worktree=include_worktree,
                        run_id="same-path-drift",
                        authorization_event_id="approved-candidate-snapshot",
                        approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
                    )
                    source.write_text(
                        "package source\n// later unapproved state\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(VerificationPlannerError):
                        kernel_build_plan(
                            profile, repository, ".dm/verification.json",
                            ["internal/source/source.go"], "chunk", "low",
                            receipt_key=RECEIPT_KEY, approval=approved,
                            head_commit=candidate_commit,
                        )

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
            approved = issue_profile_approval(
                profile, repository, ".dm/verification.json",
                trusted_base_commit=base_commit,
                candidate_commit=candidate_commit,
                run_id="ignored-input",
                authorization_event_id="approved-exact-head",
                approved_at=APPROVED_AT, receipt_key=RECEIPT_KEY,
            )
            with self.assertRaises(VerificationPlannerError):
                kernel_build_plan(
                    profile, repository, ".dm/verification.json",
                    [".gitignore"], "merge_candidate", "high",
                    receipt_key=RECEIPT_KEY, approval=approved,
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
                "authority_paths": [".dm/verification.json"],
                "cache": "never",
                "mutates_repository": True,
                "cache_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
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
            receipts, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "complete")
        focused_receipt = [
            receipt for receipt in receipts["receipts"]
            if receipt["lane_id"] == "go-focused"
        ][0]
        self.assertNotEqual(focused_receipt["input_digest"], before)

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
            "authority_paths": [".dm/verification.json"],
            "cache": "never",
            "mutates_repository": True,
            "cache_environment": ["DM_VERIFICATION_SUBSTRATE"],
            "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
            "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
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
                "authority_paths": [".dm/verification.json"],
                "cache": "never",
                "cache_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "required_environment": ["DM_VERIFICATION_SUBSTRATE"],
                "authority_environment": ["DM_VERIFICATION_SUBSTRATE"],
            })
            document["lanes"][1]["after"] = ["generate"]
            repository, profile = self.repository(
                Path(directory) / "repository", document,
            )
            plan = build_plan(
                profile, repository, ".dm/verification.json",
                ["internal/source/source.go"], "chunk", "low",
            )
            receipts, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        self.assertFalse(counter.exists())
        self.assertIn("dependency_not_passed", {
            receipt["reason"] for receipt in receipts["receipts"]
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
            _receipts, outcome = execute(
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
                        _receipts, outcome = execute(
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
            receipts, outcome = execute(profile, repository, plan)
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
            receipt for receipt in receipts["receipts"]
            if receipt["lane_id"] == "go-focused"
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
            receipts, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        self.assertIn("undeclared_repository_mutation", {
            receipt["reason"] for receipt in receipts["receipts"]
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
                receipts, outcome = execute(profile, repository, plan)
        self.assertEqual(outcome, "failed")
        focused = [
            receipt for receipt in receipts["receipts"]
            if receipt["lane_id"] == "go-focused"
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
                receipts, outcome = execute(profile, repository, plan)
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
            receipt for receipt in receipts["receipts"]
            if receipt["lane_id"] == "go-focused"
        ][0]
        self.assertEqual(
            focused["reason"], "command_output_limit_exceeded",
        )
        self.assertLessEqual(focused["stdout_bytes"], 65536)
        self.assertTrue(leader_gone)

    def test_symlinked_input_directory_and_unbounded_arrays_are_rejected(self):
        document = profile_document()
        document["lanes"][0]["cache_environment"] = [
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

    def test_cli_plans_runs_and_reuses_exact_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(Path(directory) / "repository")
            plan_path = Path(directory) / "plan.json"
            receipts_path = Path(directory) / "receipts.json"
            approval_path = Path(directory) / "approval.json"
            env = dict(
                os.environ,
                PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )
            def run_cli(arguments):
                return subprocess.run(
                    [sys.executable, "-m", "workflow_kernel", *arguments],
                    env=env, input=RECEIPT_KEY, capture_output=True, check=False,
                )
            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            approved = run_cli([
                "approve-verification-profile",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--trusted-base-commit", base_commit,
                "--candidate-commit", candidate_commit,
                "--run-id", "cli-verification-run",
                "--authorization-event-id", "operator-approved-cli-run",
                "--approved-at", APPROVED_AT,
                "--receipt-key-stdin", "--output", str(approval_path),
            ])
            self.assertEqual(approved.returncode, 0, approved.stderr.decode())
            command = [
                "plan-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "chunk", "--risk", "low",
                "--approval", str(approval_path),
                "--receipt-key-stdin",
                "--output", str(plan_path),
            ]
            planned = run_cli(command)
            self.assertEqual(planned.returncode, 0, planned.stderr.decode())
            run = run_cli([
                "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path), "--output", str(receipts_path),
                "--approval", str(approval_path), "--receipt-key-stdin",
            ])
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            planned_again = run_cli([
                *command[:-2],
                "--receipts", str(receipts_path),
                "--output", str(plan_path),
            ])
            self.assertEqual(
                planned_again.returncode, 0, planned_again.stderr.decode(),
            )
            focused = {
                lane["id"]: lane
                for lane in json.loads(plan_path.read_text())["lanes"]
            }["go-focused"]
            self.assertEqual(focused["disposition"], "reuse")

    def test_cli_required_remote_pending_exits_unsafe_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, _profile = self.repository(Path(directory) / "repository")
            plan_path = Path(directory) / "candidate-plan.json"
            receipts_path = Path(directory) / "candidate-receipts.json"
            approval_path = Path(directory) / "candidate-approval.json"
            env = dict(
                os.environ, PYTHONPATH=str(KERNEL_REFERENCES),
                DM_VERIFICATION_SUBSTRATE="test-host-containment",
            )
            def run_cli(arguments):
                return subprocess.run(
                    [sys.executable, "-m", "workflow_kernel", *arguments],
                    env=env, input=RECEIPT_KEY, capture_output=True, check=False,
                )
            base_commit, candidate_commit = prepare_candidate(
                repository, ["internal/source/source.go"],
            )
            approved = run_cli([
                "approve-verification-profile",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--trusted-base-commit", base_commit,
                "--candidate-commit", candidate_commit,
                "--run-id", "cli-candidate-run",
                "--authorization-event-id", "operator-approved-candidate",
                "--approved-at", APPROVED_AT,
                "--receipt-key-stdin", "--output", str(approval_path),
            ])
            self.assertEqual(approved.returncode, 0, approved.stderr.decode())
            planned = run_cli([
                "plan-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "merge_candidate", "--risk", "high",
                "--approval", str(approval_path),
                "--receipt-key-stdin",
                "--output", str(plan_path),
            ])
            self.assertEqual(planned.returncode, 0, planned.stderr.decode())
            run = run_cli([
                "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
                "--approval", str(approval_path),
                "--receipt-key-stdin",
                "--output", str(receipts_path),
            ])
            self.assertEqual(run.returncode, 3, run.stderr.decode())
            self.assertEqual(
                json.loads(run.stdout.decode())["status"], "pending",
            )
            attestation_path = Path(directory) / "provider-attestation.json"
            failed_attestation = seal_provider_attestation({
                "schema_version": 1,
                "artifact_role": "repository_verification_provider_attestation",
                "provider": "github",
                "provider_run_id": "failed-provider-run",
                "head_commit": candidate_commit,
                "evidence_digest": "sha256:" + "1" * 64,
                "observed_at": "2026-07-30T02:00:00Z",
                "outcome": "failed",
                "exit_code": 1,
            }, RECEIPT_KEY)
            attestation_path.write_text(json.dumps(failed_attestation))
            record_command = [
                "record-verification-result",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
                "--approval", str(approval_path),
                "--receipts", str(receipts_path),
                "--lane-id", "go-race",
                "--provider-attestation", str(attestation_path),
                "--receipt-key-stdin",
                "--output", str(receipts_path),
            ]
            recorded_failure = run_cli(record_command)
            self.assertEqual(
                recorded_failure.returncode, 3,
                recorded_failure.stderr.decode(),
            )
            self.assertEqual(
                json.loads(receipts_path.read_text())["receipts"][-1]["status"],
                "failed",
            )
            replan_command = [
                "plan-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--boundary", "merge_candidate", "--risk", "high",
                "--approval", str(approval_path),
                "--receipts", str(receipts_path),
                "--receipt-key-stdin", "--output", str(plan_path),
            ]
            self.assertEqual(
                run_cli(replan_command).returncode, 0,
            )
            race = {
                lane["id"]: lane
                for lane in json.loads(plan_path.read_text())["lanes"]
            }["go-race"]
            self.assertEqual(race["disposition"], "remote")
            passed_attestation = seal_provider_attestation({
                **failed_attestation,
                "provider_run_id": "passed-provider-run",
                "evidence_digest": "sha256:" + "2" * 64,
                "observed_at": "2026-07-30T02:05:00Z",
                "outcome": "passed",
                "exit_code": 0,
            }, RECEIPT_KEY)
            attestation_path.write_text(json.dumps(passed_attestation))
            recorded_pass = run_cli(record_command)
            self.assertEqual(
                recorded_pass.returncode, 0, recorded_pass.stderr.decode(),
            )
            self.assertEqual(run_cli(replan_command).returncode, 0)
            race = {
                lane["id"]: lane
                for lane in json.loads(plan_path.read_text())["lanes"]
            }["go-race"]
            self.assertEqual(race["disposition"], "reuse")
            completed = run_cli([
                "run-verification",
                "--repository-root", str(repository),
                "--profile", str(repository / ".dm/verification.json"),
                "--plan", str(plan_path),
                "--approval", str(approval_path),
                "--receipts", str(receipts_path),
                "--receipt-key-stdin", "--output", str(receipts_path),
            ])
            self.assertEqual(completed.returncode, 0, completed.stderr.decode())


if __name__ == "__main__":
    unittest.main()
