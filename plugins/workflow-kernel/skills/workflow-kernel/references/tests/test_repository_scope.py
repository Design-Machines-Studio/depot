import json
import tempfile
import unittest
from pathlib import Path

from workflow_kernel.repository_scope import repository_scope


class RepositoryScopeTests(unittest.TestCase):
    def repo(self, root, name="repo"):
        repo = Path(root) / name
        (repo / ".git").mkdir(parents=True)
        state = repo / "plans" / "feature"
        state.mkdir(parents=True)
        return repo, state

    def test_scope_is_random_immutable_and_bound_to_repo_and_lease_inode(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            first = repository_scope(state, create=True)
            second = repository_scope(state)
            self.assertEqual(first, second)
            self.assertRegex(first.scope_id, r"^[0-9a-f]{64}$")
            document = json.loads((repo / ".workflow-kernel" / "repository-scope.json").read_text())
            self.assertEqual(document["repo_root"]["inode"], repo.stat().st_ino)
            self.assertEqual(document["lease_root"]["inode"], first.lease_root.stat().st_ino)

    def test_scope_supports_worktree_gitdir_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gitdir = root / "common" / "worktrees" / "one"
            gitdir.mkdir(parents=True)
            repo = root / "worktree"
            repo.mkdir()
            (repo / ".git").write_text("gitdir: ../common/worktrees/one\n")
            state = repo / "plans" / "feature"
            state.mkdir(parents=True)
            self.assertEqual(repository_scope(state, create=True).repo_root, repo.resolve())

    def test_symlinked_and_cross_repo_state_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_a, state_a = self.repo(directory, "a")
            _repo_b, state_b = self.repo(directory, "b")
            link = repo_a / "plans" / "foreign"
            link.symlink_to(state_b, target_is_directory=True)
            with self.assertRaises(ValueError):
                repository_scope(link, create=True)
            repository_scope(state_a, create=True)

    def test_scope_metadata_path_or_inode_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            path = scope.lease_root / "repository-scope.json"
            document = json.loads(path.read_text())
            document["lease_root"]["inode"] += 1
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                repository_scope(state)


if __name__ == "__main__":
    unittest.main()
