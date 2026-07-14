import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workflow_kernel.adapters.git import GitAdapter, GitProof
from workflow_kernel.resources import CleanupDisposition, CleanupScope, ResourceKind, ResourceRecord, ResourceRegistry


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
        self.assertEqual(("git", "worktree", "remove", WORKTREE), plan.actions[0].argv)
        self.assertEqual(("git", "branch", "-d", BRANCH), plan.actions[1].argv)
        self.assertEqual(0, plan.actions[1].requires_success_of)

    def test_proof_commands_carry_explicit_base_and_merge_target(self):
        commands = self.adapter.proof_argv(WORKTREE, BRANCH, "release/base", "feature/kernel")
        self.assertEqual(("git", "-C", WORKTREE, "status", "--porcelain=v1", "-z"), commands[0])
        self.assertEqual(("git", "merge-base", "--is-ancestor", BRANCH, "feature/kernel"), commands[1])
        self.assertEqual(("git", "rev-list", "--count", "release/base.." + BRANCH), commands[2])
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
        self.assertEqual(("git", "branch", "-D", BRANCH), plan.actions[1].argv)


if __name__ == "__main__":
    unittest.main()
