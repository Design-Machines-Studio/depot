import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workflow_kernel.adapters.git import GitAdapter, GitProof
from workflow_kernel.resources import (
    CleanupDisposition, CleanupScope, CommandResult, ResourceKind, ResourceRecord,
    ResourceRegistry, reseal_cleanup_action,
)
from workflow_kernel.schema import InvalidSchemaError


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)
NAMESPACE = "pipeline/run-1"
ROOT = "/repo/.worktrees/pipeline/run-1"
WORKTREE = ROOT + "/node-1"
BRANCH = NAMESPACE + "/node-1"


def owned_record(kind, resource_id, *, ref_role=None):
    return ResourceRecord(
        resource_id, kind, "run-1", "node-1", "chunk", "retain", NOW,
        labels={
            "ownership-namespace": NAMESPACE,
            "base-ref": "feature/kernel",
            "merge-target": "feature/kernel",
            "ref-role": ref_role or ("chunk-worktree" if kind is ResourceKind.WORKTREE else "chunk-branch"),
        },
    )


def proof(**changes):
    values = dict(
        worktree_path=WORKTREE,
        branch=BRANCH,
        readable=True,
        dirty=False,
        branch_is_feature=False,
        ancestor_of_merge_target=True,
        unique_commit_count=0,
        base_ref="feature/kernel",
        merge_target="feature/kernel",
        ownership_namespace=NAMESPACE,
        captured_at=NOW,
        worktree_head_oid="1" * 40,
        branch_oid="1" * 40,
        base_oid="2" * 40,
        merge_target_oid="3" * 40,
        worktree_prunable=False,
    )
    values.update(changes)
    return GitProof(**values)


class GitCleanupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(Path(self.directory.name) / "resources.jsonl")
        self.registry.register(owned_record(ResourceKind.WORKTREE, WORKTREE))
        self.registry.register(owned_record(ResourceKind.BRANCH, BRANCH))
        self.adapter = GitAdapter(NAMESPACE, ROOT, now=lambda: NOW, max_proof_age=timedelta(seconds=5))
        self.scope = CleanupScope("run-1", "node-1")

    def tearDown(self):
        self.directory.cleanup()

    def test_cleanup_is_pure_plan_from_registry_owned_candidates(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        self.assertEqual(("git", "worktree", "remove", "--", WORKTREE), plan.actions[0].argv)
        self.assertEqual(("git", "branch", "-d", "--", BRANCH), plan.actions[1].argv)
        self.assertEqual(0, plan.actions[1].requires_success_of)

    def test_adapter_rejects_unbounded_or_unsafe_worktree_roots(self):
        for candidate in (
            "/", "relative/root", ROOT + "/..", ROOT + "//nested",
        ):
            with self.subTest(candidate=candidate), self.assertRaises(InvalidSchemaError):
                GitAdapter(NAMESPACE, candidate, now=lambda: NOW)

        normalized = GitAdapter(NAMESPACE, ROOT + "/", now=lambda: NOW)
        self.assertEqual(ROOT, normalized.worktree_root)

    def test_proof_commands_carry_explicit_base_and_merge_target(self):
        commands = self.adapter.proof_argv(WORKTREE, BRANCH, "release/base", "feature/kernel")
        self.assertEqual(("git", "worktree", "list", "--porcelain", "-z"), commands[0])
        self.assertEqual(("git", "-C", WORKTREE, "status", "--porcelain=v1", "-z"), commands[1])
        self.assertEqual(("git", "merge-base", "--is-ancestor", "--", BRANCH, "feature/kernel"), commands[2])
        self.assertEqual(("git", "rev-list", "--count", "--", "release/base.." + BRANCH), commands[3])
        self.assertFalse(any("origin/main" in part for command in commands for part in command))

    def test_foreign_namespace_or_unregistered_ref_never_plans_deletion(self):
        for candidate in (
            proof(ownership_namespace="foreign"),
            proof(worktree_path=ROOT + "/unregistered"),
        ):
            plan = self.adapter.cleanup_owned(self.registry, self.scope, candidate)
            self.assertEqual((), plan.actions)
            self.assertTrue(all(item.disposition is CleanupDisposition.FOREIGN for item in plan.dispositions))

    def test_stale_unreadable_or_dirty_proof_fails_closed(self):
        cases = (
            proof(captured_at=NOW - timedelta(seconds=6)),
            proof(readable=False),
            proof(dirty=True),
        )
        for candidate in cases:
            plan = self.adapter.cleanup_owned(self.registry, self.scope, candidate)
            self.assertEqual((), plan.actions)
            self.assertEqual(CleanupDisposition.BLOCKED, plan.dispositions[0].disposition)

    def test_registered_feature_branch_is_retained_even_when_proof_lies(self):
        feature_registry = ResourceRegistry(Path(self.directory.name) / "feature.jsonl")
        feature_registry.register(owned_record(ResourceKind.WORKTREE, WORKTREE))
        feature_registry.register(owned_record(ResourceKind.BRANCH, BRANCH, ref_role="feature-branch"))
        plan = self.adapter.cleanup_owned(feature_registry, self.scope, proof(branch_is_feature=False))
        self.assertEqual(1, len(plan.actions))
        self.assertEqual(ResourceKind.WORKTREE, plan.actions[0].kind)
        branch = next(item for item in plan.dispositions if item.kind is ResourceKind.BRANCH)
        self.assertEqual(CleanupDisposition.RETAINED_FOR_DEPENDENCY, branch.disposition)

    def test_zero_unique_chunk_branch_uses_force_only_after_fresh_proof(self):
        plan = self.adapter.cleanup_owned(
            self.registry, self.scope, proof(ancestor_of_merge_target=False, unique_commit_count=0)
        )
        self.assertEqual(("git", "branch", "-D", "--", BRANCH), plan.actions[1].argv)

    def test_extra_registered_git_resources_fail_closed_with_complete_dispositions(self):
        extra_worktree = ROOT + "/node-1-extra"
        self.registry.register(owned_record(ResourceKind.WORKTREE, extra_worktree))
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        self.assertEqual((), plan.actions)
        self.assertEqual(
            {WORKTREE, extra_worktree, BRANCH},
            {item.resource_id for item in plan.dispositions},
        )
        self.assertTrue(all(item.disposition is CleanupDisposition.BLOCKED for item in plan.dispositions))

    def test_git_proof_rejects_truthy_bools_counts_and_noncanonical_fields(self):
        invalid = (
            {"readable": 1},
            {"dirty": 0},
            {"branch_is_feature": 1},
            {"ancestor_of_merge_target": 1},
            {"unique_commit_count": True},
            {"unique_commit_count": -1},
            {"worktree_path": ROOT + "/../foreign"},
            {"branch": NAMESPACE + "//node-1"},
            {"base_ref": " feature/kernel"},
            {"merge_target": "feature/kernel "},
            {"ownership_namespace": NAMESPACE + "/"},
            {"base_ref": "a" * 257},
            {"worktree_path": "/" + "a" * 4097},
            {"captured_at": NOW.replace(tzinfo=None)},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(InvalidSchemaError):
                proof(**changes)

    def test_cleanup_requires_exact_git_proof_type(self):
        class DerivedGitProof(GitProof):
            pass

        derived = object.__new__(DerivedGitProof)
        for name, value in proof().__dict__.items():
            object.__setattr__(derived, name, value)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.cleanup_owned(self.registry, self.scope, derived)

        mutated = proof()
        object.__setattr__(mutated, "unique_commit_count", True)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.cleanup_owned(self.registry, self.scope, mutated)

    def test_action_revalidation_rejects_changed_unique_commit_count(self):
        initial = proof(ancestor_of_merge_target=False, unique_commit_count=0)
        plan = self.adapter.cleanup_owned(self.registry, self.scope, initial)
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                plan.actions[1], proof(ancestor_of_merge_target=False, unique_commit_count=1),
            )

    def test_prunable_registered_worktree_is_preserved_as_blocked_decision(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof(worktree_prunable=True))
        self.assertEqual((), plan.actions)
        self.assertEqual("registered_worktree_prunable", plan.dispositions[0].reason)

    def test_option_looking_refs_are_rejected(self):
        with self.assertRaises(InvalidSchemaError):
            proof(branch="--delete")

    def test_revalidation_rejects_forged_argv_even_with_original_digest(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        forged = replace(plan.actions[0], argv=("git", "worktree", "remove", "--", ROOT + "/foreign"))
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(forged, proof())

    def test_branch_stage_revalidates_after_worktree_removal(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        predecessor = CommandResult(plan.actions[0].argv, 0, "", "")
        after_removal = proof(worktree_present=False)
        self.adapter.revalidate_action(plan.actions[1], after_removal, predecessor)

    def test_revalidation_rejects_plan_from_another_adapter_scope(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        foreign = GitAdapter(
            "pipeline/other-run", "/repo/.worktrees/pipeline/other-run",
            now=lambda: NOW, max_proof_age=timedelta(seconds=5),
        )
        with self.assertRaises(InvalidSchemaError):
            foreign.revalidate_action(plan.actions[0], proof())

    def test_branch_revalidation_requires_canonical_worktree_predecessor_index(self):
        plan = self.adapter.cleanup_owned(self.registry, self.scope, proof())
        forged = reseal_cleanup_action(plan.actions[1], requires_success_of=None)
        predecessor = CommandResult(plan.actions[0].argv, 0, "", "")
        with self.assertRaises(InvalidSchemaError):
            self.adapter.revalidate_action(
                forged, proof(worktree_present=False), predecessor,
            )


if __name__ == "__main__":
    unittest.main()
