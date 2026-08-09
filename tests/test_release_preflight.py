"""Behavioral tests for tools/check-release-preflight.sh."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_SOURCE = ROOT / "tools/check-release-preflight.sh"
SYSTEM_GIT = "/usr/bin/git"


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="release-preflight-")
        self.temp = Path(self.temporary.name)
        self.repo = self.temp / "repo"
        self.bin = self.temp / "bin"
        self.origin = self.temp / "origin.git"
        self.marketplace_root = self.temp / "marketplace"
        self.codex_json = self.temp / "codex.json"
        self.git_log = self.temp / "git.log"
        self.repo.mkdir()
        self.bin.mkdir()
        self.marketplace_root.mkdir()
        (self.repo / "tools").mkdir()

        script = SCRIPT_SOURCE.read_text(encoding="utf-8")
        fixed_path = f'PATH="{self.bin}:/usr/bin:/bin:/usr/sbin:/sbin"'
        script = script.replace(
            'PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"',
            fixed_path,
        )
        self.script = self.repo / "tools/check-release-preflight.sh"
        self.script.write_text(script, encoding="utf-8")
        self.script.chmod(0o755)
        for generator in (
            "generate-codex-manifests.py", "generate-codex-command-skills.py",
        ):
            (self.repo / "tools" / generator).write_text(
                "raise SystemExit(0)\n", encoding="utf-8",
            )

        self._write_git_wrapper()
        self._git("init", "-q")
        self._git("config", "user.name", "Release Test")
        self._git("config", "user.email", "release-test@example.invalid")
        self._git("checkout", "-q", "-b", "feature")
        self._write_versions({"alpha": "1.0.0", "beta": "1.0.0"})
        self._git("add", ".")
        self._git("commit", "-q", "-m", "base")
        self.base = self._git("rev-parse", "HEAD").stdout.strip()
        self._git("tag", "alpha-v1.0.0")
        self._git("tag", "beta-v1.0.0")
        subprocess.run(
            [SYSTEM_GIT, "init", "-q", "--bare", str(self.origin)],
            check=True,
        )
        self._git("remote", "add", "origin", str(self.origin))

    def tearDown(self):
        self.temporary.cleanup()

    def _git(self, *args, cwd=None):
        return subprocess.run(
            [SYSTEM_GIT, *args], cwd=cwd or self.repo, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def _write_versions(self, versions):
        self._write_versions_at(self.repo, versions)

    def _write_versions_at(self, root, versions):
        marketplace = root / ".claude-plugin/marketplace.json"
        marketplace.parent.mkdir(parents=True, exist_ok=True)
        marketplace.write_text(json.dumps({
            "plugins": [
                {"name": name, "version": version}
                for name, version in sorted(versions.items())
            ],
        }), encoding="utf-8")
        for name, version in versions.items():
            manifest = root / f"plugins/{name}/.claude-plugin/plugin.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps({
                "name": name, "version": version,
            }), encoding="utf-8")

    def _write_git_wrapper(self):
        wrapper = self.bin / "git"
        wrapper.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = fetch ]; then printf '%s|%s\\n' "
            "\"${GIT_OBJECT_DIRECTORY:-}\" \"$*\" >> \"$PREFLIGHT_GIT_LOG\"; fi\n"
            "if [ \"${PREFLIGHT_GIT_FAIL:-}\" = fetch ] && "
            "[ \"$1\" = fetch ]; then exit 42; fi\n"
            "if [ \"${PREFLIGHT_GIT_FAIL:-}\" = merge-base ] && "
            "[ \"$1\" = merge-base ]; then exit 128; fi\n"
            "if [ \"${PREFLIGHT_GIT_FAIL:-}\" = diff ] && "
            "[ \"$1\" = diff ] && [ \"${2:-}\" = --quiet ]; then exit 128; fi\n"
            "if [ \"$1\" = ls-remote ] && [ \"${2:-}\" = --exit-code ]; then\n"
            "  case \"${PREFLIGHT_GIT_MUTATE:-}\" in\n"
            "    head) /usr/bin/git commit -q --allow-empty -m concurrent-head ;;\n"
            "    branch) /usr/bin/git checkout -q -b concurrent-branch ;;\n"
            "    worktree) printf '\\n' >> plugins/alpha/.claude-plugin/plugin.json ;;\n"
            "  esac\n"
            "fi\n"
            "exec /usr/bin/git \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

    def _write_codex(self):
        codex = self.bin / "codex"
        codex.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = plugin ] && [ \"$2\" = marketplace ] && "
            "[ \"$3\" = list ]; then\n"
            "  printf 'Name Path\\n'; printf 'depot %s\\n' \"$PREFLIGHT_MARKETPLACE_ROOT\"\n"
            "elif [ \"$1\" = plugin ] && [ \"$2\" = list ]; then\n"
            "  cat \"$PREFLIGHT_CODEX_JSON\"\n"
            "else\n"
            "  exit 2\n"
            "fi\n",
            encoding="utf-8",
        )
        codex.chmod(0o755)

    def _installed_rows(self, override=None):
        versions = {
            row["name"]: row["version"]
            for row in json.loads(
                (self.repo / ".claude-plugin/marketplace.json").read_text()
            )["plugins"]
        }
        if override:
            versions.update(override)
        return {
            "installed": [
                {"name": name, "version": version, "installed": True}
                for name, version in sorted(versions.items())
            ],
        }

    def _run_preflight(
        self, *, no_net=False, codex="fresh", git_fail=None, git_mutate=None,
    ):
        codex_path = self.bin / "codex"
        if codex == "unavailable":
            codex_path.unlink(missing_ok=True)
        else:
            self._write_codex()
            if codex == "fresh":
                payload = json.dumps(self._installed_rows())
            elif codex == "stale":
                payload = json.dumps(self._installed_rows({"alpha": "0.9.0"}))
            elif codex == "malformed":
                payload = "{not-json"
            elif codex == "wrong-shape":
                payload = "[]"
            else:
                raise AssertionError(f"unknown Codex fixture: {codex}")
            self.codex_json.write_text(payload, encoding="utf-8")
        self.git_log.unlink(missing_ok=True)
        env = os.environ.copy()
        env.update({
            "PREFLIGHT_CODEX_JSON": str(self.codex_json),
            "PREFLIGHT_MARKETPLACE_ROOT": str(self.marketplace_root),
            "PREFLIGHT_GIT_LOG": str(self.git_log),
        })
        if git_fail:
            env["PREFLIGHT_GIT_FAIL"] = git_fail
        if git_mutate:
            env["PREFLIGHT_GIT_MUTATE"] = git_mutate
        argv = [str(self.script)]
        if no_net:
            argv.append("--no-net")
        return subprocess.run(
            argv, cwd=self.repo, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def _commit_plugin_change(self, plugins, version, message):
        versions = {"alpha": "1.0.0", "beta": "1.0.0"}
        for name in plugins:
            versions[name] = version
        self._write_versions(versions)
        for name in plugins:
            content = self.repo / f"plugins/{name}/content.txt"
            content.write_text(message + "\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def _make_divergence(
        self, *, local_plugins=("alpha",), remote_plugins=("alpha",),
        remote_version="1.1.0", remote_branch="candidate",
    ):
        self._git("checkout", "-q", "-B", "remote-build", self.base)
        remote_sha = self._commit_plugin_change(
            remote_plugins, remote_version, "remote change",
        )
        self._git(
            "push", "-q", "--force", "origin",
            f"{remote_sha}:refs/heads/{remote_branch}",
        )
        self._git(
            "--git-dir", str(self.origin), "symbolic-ref",
            "HEAD", f"refs/heads/{remote_branch}",
        )
        self._git("checkout", "-q", "-B", "feature", self.base)
        local_sha = self._commit_plugin_change(
            local_plugins, "1.1.0", "local change",
        )
        return local_sha, remote_sha

    def _make_remote_only_divergence(self):
        self._git("push", "-q", "--force", "origin", f"{self.base}:refs/heads/base")
        remote_work = self.temp / "remote-work"
        subprocess.run(
            [SYSTEM_GIT, "clone", "-q", "--no-checkout", str(self.origin),
             str(remote_work)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._git("config", "user.name", "Remote Release Test", cwd=remote_work)
        self._git(
            "config", "user.email", "remote-release-test@example.invalid",
            cwd=remote_work,
        )
        self._git("checkout", "-q", "-b", "candidate", self.base, cwd=remote_work)
        self._write_versions_at(remote_work, {"alpha": "1.1.0", "beta": "1.0.0"})
        remote_content = remote_work / "plugins/alpha/content.txt"
        remote_content.write_text("remote-only change\n", encoding="utf-8")
        self._git("add", ".", cwd=remote_work)
        self._git("commit", "-q", "-m", "remote-only change", cwd=remote_work)
        remote_sha = self._git("rev-parse", "HEAD", cwd=remote_work).stdout.strip()
        self._git(
            "push", "-q", "--force", "origin", "HEAD:refs/heads/candidate",
            cwd=remote_work,
        )
        self._git("checkout", "-q", "-B", "feature", self.base)
        self._commit_plugin_change(("alpha",), "1.1.0", "local change")
        missing = subprocess.run(
            [SYSTEM_GIT, "cat-file", "-e", remote_sha], cwd=self.repo,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(missing.returncode, 0)

    def _repository_git_state(self):
        refs = self._git("for-each-ref", "--format=%(refname) %(objectname)").stdout
        fetch_head = self.repo / ".git/FETCH_HEAD"
        fetch_head_bytes = fetch_head.read_bytes() if fetch_head.exists() else None
        objects = {
            path.relative_to(self.repo / ".git/objects").as_posix(): path.read_bytes()
            for path in (self.repo / ".git/objects").rglob("*")
            if path.is_file()
        }
        return refs, fetch_head_bytes, objects

    def test_fresh_codex_cache_passes(self):
        result = self._run_preflight(no_net=True, codex="fresh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("2 installed Codex plugin(s) checked", result.stdout)

    def test_stale_codex_cache_fails_with_repair(self):
        result = self._run_preflight(no_net=True, codex="stale")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Codex cache=0.9.0, canonical marketplace=1.0.0", result.stdout)
        self.assertIn("codex plugin marketplace upgrade interactively", result.stdout)

    def test_malformed_codex_json_skips_with_reason(self):
        result = self._run_preflight(no_net=True, codex="malformed")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Codex cache data unreadable", result.stdout)

    def test_wrong_shape_codex_json_skips_without_false_pass(self):
        result = self._run_preflight(no_net=True, codex="wrong-shape")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("unexpected top-level JSON shape", result.stdout)
        self.assertNotIn("Codex plugins match", result.stdout)

    def test_unavailable_codex_skips_with_reason(self):
        result = self._run_preflight(no_net=True, codex="unavailable")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("codex CLI not installed", result.stdout)

    def test_no_net_skips_remote_probe_without_fetching(self):
        result = self._run_preflight(no_net=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("remote equal-bump probe skipped (--no-net)", result.stdout)
        self.assertFalse(self.git_log.exists())

    def test_equal_bump_fails(self):
        self._make_divergence(remote_version="1.1.0")
        result = self._run_preflight()
        self.assertEqual(result.returncode, 1)
        self.assertIn("both declare 1.1.0", result.stdout)

    def test_strictly_greater_remote_bump_passes(self):
        self._make_divergence(remote_version="1.2.0")
        result = self._run_preflight()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 remote changed-plugin manifest(s) checked", result.stdout)

    def test_concurrent_head_change_blocks_terminal_ready_receipt(self):
        self._make_divergence(remote_version="1.2.0")
        start_sha = self._git("rev-parse", "HEAD").stdout.strip()
        result = self._run_preflight(git_mutate="head")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("repository snapshot changed during preflight", result.stdout)
        self.assertIn(f"Commit:      {start_sha[:7]}", result.stdout)
        self.assertNotIn("READY:", result.stdout)

    def test_concurrent_worktree_change_blocks_terminal_ready_receipt(self):
        self._make_divergence(remote_version="1.2.0")
        result = self._run_preflight(git_mutate="worktree")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("repository snapshot changed during preflight", result.stdout)
        self.assertNotIn("READY:", result.stdout)

    def test_concurrent_branch_change_blocks_terminal_ready_receipt(self):
        self._make_divergence(remote_version="1.2.0")
        result = self._run_preflight(git_mutate="branch")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("repository snapshot changed during preflight", result.stdout)
        self.assertIn("Branch:      feature", result.stdout)
        self.assertNotIn("READY:", result.stdout)

    def test_same_name_divergent_branch_is_checked(self):
        self._make_divergence(remote_branch="feature")
        result = self._run_preflight()
        self.assertEqual(result.returncode, 1)
        self.assertIn("local feature and origin/feature both declare 1.1.0", result.stdout)

    def test_same_name_contained_branch_is_shared_history(self):
        local_sha, _ = self._make_divergence(remote_branch="feature")
        self._git(
            "push", "-q", "--force", "origin",
            f"{local_sha}:refs/heads/feature",
        )
        result = self._run_preflight()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 remote changed-plugin manifest(s) checked", result.stdout)

    def test_merge_base_predicate_failure_blocks(self):
        self._make_divergence()
        result = self._run_preflight(git_fail="merge-base")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot classify origin/candidate", result.stdout)

    def test_diff_predicate_failure_blocks(self):
        self._make_divergence()
        result = self._run_preflight(git_fail="diff")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot compare local plugin files", result.stdout)

    def test_remote_probe_preserves_fetch_head(self):
        self._make_divergence()
        fetch_head = self.repo / ".git/FETCH_HEAD"
        fetch_head.write_bytes(b"sentinel-fetch-head\n")
        result = self._run_preflight()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(fetch_head.read_bytes(), b"sentinel-fetch-head\n")

    def test_remote_only_probe_preserves_refs_fetch_head_and_object_store(self):
        self._make_remote_only_divergence()
        fetch_head = self.repo / ".git/FETCH_HEAD"
        fetch_head.write_bytes(b"sentinel-fetch-head\n")
        before = self._repository_git_state()
        result = self._run_preflight()
        self.assertEqual(result.returncode, 1)
        self.assertIn("both declare 1.1.0", result.stdout)
        self.assertEqual(self._repository_git_state(), before)

    def test_remote_probe_object_quarantine_is_removed_after_fetch_failure(self):
        self._make_remote_only_divergence()
        before = set(Path("/tmp").glob("release-preflight-objects.*"))
        result = self._run_preflight(git_fail="fetch")
        self.assertEqual(result.returncode, 1)
        fetch_record = self.git_log.read_text(encoding="utf-8").splitlines()[0]
        object_directory = Path(fetch_record.split("|", 1)[0])
        self.assertNotEqual(str(object_directory), ".")
        self.assertFalse(object_directory.exists())
        self.assertEqual(
            set(Path("/tmp").glob("release-preflight-objects.*")), before,
        )

    def test_each_remote_sha_is_fetched_once_across_changed_plugins(self):
        self._make_divergence(
            local_plugins=("alpha", "beta"), remote_plugins=("alpha", "beta"),
        )
        result = self._run_preflight()
        self.assertEqual(result.returncode, 1)
        fetches = self.git_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(fetches, [fetches[0]])

    def test_cached_fetch_failure_blocks_each_affected_plugin(self):
        self._make_divergence(
            local_plugins=("alpha", "beta"), remote_plugins=("alpha", "beta"),
        )
        result = self._run_preflight(git_fail="fetch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("alpha: cannot inspect origin/candidate", result.stdout)
        self.assertIn("beta: cannot inspect origin/candidate", result.stdout)
        fetches = self.git_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(fetches, [fetches[0]])


if __name__ == "__main__":
    unittest.main()
