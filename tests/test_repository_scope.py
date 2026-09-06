import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workflow_kernel.adapters.docker import DockerAdapter
from workflow_kernel.repository_scope import repository_scope
from workflow_kernel.resources import CommandResult


class RepositoryScopeTests(unittest.TestCase):
    def repo(self, root, name="repo"):
        repo = Path(root) / name
        (repo / ".git").mkdir(parents=True)
        state = repo / "plans" / "feature"
        state.mkdir(parents=True)
        return repo, state

    def swap_on_descriptor_read(self, target, mutation):
        identity = (target.stat().st_dev, target.stat().st_ino)
        original = os.read
        triggered = {"value": False}

        def read_then_swap(descriptor, count):
            value = original(descriptor, count)
            opened = os.fstat(descriptor)
            if not triggered["value"] and (opened.st_dev, opened.st_ino) == identity:
                triggered["value"] = True
                mutation()
            return value

        return mock.patch(
            "workflow_kernel.repository_scope.os.read",
            side_effect=read_then_swap,
        ), triggered

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

    def test_scope_survives_device_renumbering_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            first = repository_scope(state, create=True)
            path = first.lease_root / "repository-scope.json"
            document = json.loads(path.read_text())
            document["repo_root"]["device"] += 1000
            document["lease_root"]["device"] += 1000
            path.write_text(json.dumps(document, sort_keys=True))
            before = path.read_bytes()

            current = repository_scope(state)

            self.assertEqual(current.scope_id, first.scope_id)
            self.assertEqual(current.repo_root, first.repo_root)
            self.assertEqual(current.lease_root, first.lease_root)
            self.assertEqual(current.repo_inode, first.repo_inode)
            self.assertEqual(current.lease_inode, first.lease_inode)
            self.assertEqual(current.repo_device, repo.stat().st_dev)
            self.assertEqual(current.lease_device, first.lease_root.stat().st_dev)
            self.assertEqual(path.read_bytes(), before)

    def test_device_renumbering_preserves_scope_filtered_docker_inventory(self):
        class Runner:
            def __init__(self):
                self.calls = []

            def run(self, argv):
                argv = tuple(argv)
                self.calls.append(argv)
                return CommandResult(argv, 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            _repo, state = self.repo(directory)
            first = repository_scope(state, create=True)
            path = first.lease_root / "repository-scope.json"
            document = json.loads(path.read_text())
            document["repo_root"]["device"] += 1000
            document["lease_root"]["device"] += 1000
            path.write_text(json.dumps(document))

            current = repository_scope(state)
            runner = Runner()
            DockerAdapter(
                runner, repository_scope_id=current.scope_id,
            ).inventory()

            scope_filter = (
                "label=com.designmachines.depot.repository-scope-id="
                + first.scope_id
            )
            self.assertEqual(len(runner.calls), 3)
            self.assertTrue(all(scope_filter in argv for argv in runner.calls))

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
            first = repository_scope(state, create=True)
            self.assertEqual(first.repo_root, repo.resolve())
            path = first.lease_root / "repository-scope.json"
            document = json.loads(path.read_text())
            document["repo_root"]["device"] += 1000
            document["lease_root"]["device"] += 1000
            path.write_text(json.dumps(document))
            self.assertEqual(repository_scope(state).scope_id, first.scope_id)

    def test_symlinked_and_cross_repo_state_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo_a, state_a = self.repo(directory, "a")
            _repo_b, state_b = self.repo(directory, "b")
            link = repo_a / "plans" / "foreign"
            link.symlink_to(state_b, target_is_directory=True)
            with self.assertRaises(ValueError):
                repository_scope(link, create=True)
            repository_scope(state_a, create=True)

    def test_scope_metadata_substitution_and_malformed_documents_fail_closed(self):
        mutations = {
            "repository path": lambda value: value["repo_root"].__setitem__("path", "/different"),
            "lease path": lambda value: value["lease_root"].__setitem__("path", "/different"),
            "repository inode": lambda value: value["repo_root"].__setitem__(
                "inode", value["repo_root"]["inode"] + 1,
            ),
            "lease inode": lambda value: value["lease_root"].__setitem__(
                "inode", value["lease_root"]["inode"] + 1,
            ),
            "malformed scope id": lambda value: value.__setitem__("scope_id", "not-a-scope-id"),
            "unexpected top-level key": lambda value: value.__setitem__("unexpected", True),
            "unexpected identity key": lambda value: value["repo_root"].__setitem__(
                "unexpected", True,
            ),
            "boolean schema version": lambda value: value.__setitem__("schema_version", True),
            "string device": lambda value: value["repo_root"].__setitem__("device", "32"),
            "boolean inode": lambda value: value["lease_root"].__setitem__("inode", True),
            "non-string path": lambda value: value["repo_root"].__setitem__("path", 1),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                _repo, state = self.repo(directory)
                scope = repository_scope(state, create=True)
                path = scope.lease_root / "repository-scope.json"
                document = json.loads(path.read_text())
                mutate(document)
                path.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    repository_scope(state)

    def test_symlinked_scope_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            path = scope.lease_root / "repository-scope.json"
            source = repo / "scope-copy.json"
            source.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(source)
            with self.assertRaises(ValueError):
                repository_scope(state)

    def test_replaced_repository_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo, state = self.repo(root)
            scope = repository_scope(state, create=True)
            document = (scope.lease_root / "repository-scope.json").read_bytes()
            repo.rename(root / "displaced-repo")
            repo, state = self.repo(root)
            (repo / ".workflow-kernel").mkdir()
            (repo / ".workflow-kernel" / "repository-scope.json").write_bytes(document)
            with self.assertRaises(ValueError):
                repository_scope(state)

    def test_replaced_lease_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            document = (scope.lease_root / "repository-scope.json").read_bytes()
            scope.lease_root.rename(repo / ".workflow-kernel-displaced")
            scope.lease_root.mkdir()
            (scope.lease_root / "repository-scope.json").write_bytes(document)
            with self.assertRaises(ValueError):
                repository_scope(state)

    def test_symlinked_git_boundary_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            git_directory = repo / ".git"
            git_directory.rename(repo / "git-directory")
            git_directory.symlink_to(repo / "git-directory", target_is_directory=True)
            with self.assertRaises(ValueError):
                repository_scope(state, create=True)

    def test_scope_file_name_swap_during_descriptor_read_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            path = scope.lease_root / "repository-scope.json"
            replacement = scope.lease_root / "replacement.json"
            replacement.write_bytes(path.read_bytes())

            def swap():
                path.unlink()
                replacement.rename(path)

            patch, triggered = self.swap_on_descriptor_read(path, swap)
            with patch, self.assertRaises(ValueError):
                repository_scope(state)
            self.assertTrue(triggered["value"])

    def test_lease_directory_swap_during_scope_read_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            path = scope.lease_root / "repository-scope.json"
            displaced = repo / ".workflow-kernel-displaced"

            def swap():
                scope.lease_root.rename(displaced)
                scope.lease_root.mkdir()

            patch, triggered = self.swap_on_descriptor_read(path, swap)
            with patch, self.assertRaises(ValueError):
                repository_scope(state)
            self.assertTrue(triggered["value"])

    def test_scope_file_hardlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            repo, state = self.repo(directory)
            scope = repository_scope(state, create=True)
            path = scope.lease_root / "repository-scope.json"
            source = repo / "scope-copy.json"
            source.write_bytes(path.read_bytes())
            path.unlink()
            os.link(source, path)
            with self.assertRaises(ValueError):
                repository_scope(state)

    def test_worktree_git_file_swap_during_descriptor_read_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gitdir = root / "common" / "worktrees" / "one"
            gitdir.mkdir(parents=True)
            repo = root / "worktree"
            repo.mkdir()
            marker = repo / ".git"
            marker.write_text("gitdir: ../common/worktrees/one\n")
            state = repo / "plans" / "feature"
            state.mkdir(parents=True)
            replacement = repo / "git-replacement"
            replacement.write_bytes(marker.read_bytes())

            def swap():
                marker.unlink()
                replacement.rename(marker)

            patch, triggered = self.swap_on_descriptor_read(marker, swap)
            with patch, self.assertRaises(ValueError):
                repository_scope(state, create=True)
            self.assertTrue(triggered["value"])


if __name__ == "__main__":
    unittest.main()
