"""Loopback regressions for configured-key OpenRouter development paths."""

from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest


REPO = Path(__file__).resolve().parents[1]
OPENROUTER = REPO / "plugins/openrouter"
PIPELINE_EXEC = REPO / "plugins/pipeline/references/openrouter-exec.sh"
BOUNDARY = OPENROUTER / "skills/openrouter-delegate/references/delegation-boundary.sh"
POLICY = OPENROUTER / "skills/openrouter-delegate/references/delegation-security-policy.json"
WRAPPER = OPENROUTER / "skills/openrouter-delegate/references/openrouter-wrapper.sh"


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    contacts = 0
    requests: list[dict] = []
    response_text = "fixture response"

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).contacts += 1
        type(self).requests.append(payload)
        model = payload.get("model") or payload.get("models", ["z-ai/glm-5.2"])[0]
        events = [
            {"id": "gen-fixture", "model": model, "provider": "fixture/provider",
             "choices": [{"delta": {"content": type(self).response_text}}]},
            {"id": "gen-fixture", "model": model, "provider": "fixture/provider",
             "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
             "choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_args: object) -> None:
        return


class OpenRouterNonInteractiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/api/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self) -> None:
        FixtureHandler.contacts = 0
        FixtureHandler.requests = []
        FixtureHandler.response_text = "fixture response"
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        installed = self.home / ".codex/plugins/cache/depot/openrouter/1.14.0"
        installed.parent.mkdir(parents=True)
        shutil.copytree(OPENROUTER, installed)
        self.installed = installed
        self.kernel = self.root / "workflow-kernel"
        self.kernel.write_text(
            "#!/usr/bin/env bash\n"
            "case \"${1:-}\" in\n"
            "  resolve-plugin-bundle) printf '%s\\n' "
            "'{\"selected_root\":\"~/.codex/plugins/cache/depot/openrouter/1.14.0\"}' ;;\n"
            "  *) exit 4 ;;\n"
            "esac\n"
        )
        self.kernel.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "OPENROUTER_API_KEY": "test",
                    "OPENROUTER_BASE": self.base, "WORKFLOW_KERNEL": str(self.kernel)})
        env.pop("OPENROUTER_API_KEY_FILE", None)
        return env

    def direct(self, prompt: str, bundle: Path | None = None) -> subprocess.CompletedProcess[str]:
        bundle = bundle or OPENROUTER
        boundary = bundle / "skills/openrouter-delegate/references/delegation-boundary.sh"
        policy = bundle / "skills/openrouter-delegate/references/delegation-security-policy.json"
        wrapper = bundle / "skills/openrouter-delegate/references/openrouter-wrapper.sh"
        system = self.root / "system"
        user = self.root / "user"
        receipt = self.root / "receipt.json"
        system.write_text("You are a fixture assistant.")
        user.write_text(prompt)
        script = f'''set -e
"{boundary}" --mode artifact-delegation --policy "{policy}" --content-file "{system}" --content-file "{user}" >/dev/null
env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="{system}" OPENROUTER_WORKLOAD=direct OPENROUTER_RECEIPT_FILE="{receipt}" bash "{wrapper}" openai/gpt-5.6-terra - 10 moonshotai/kimi-k3 < "{user}"
'''
        result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=self.env())
        result.receipt_path = receipt  # type: ignore[attr-defined]
        return result

    def test_direct_is_one_pass_and_receipt_is_content_free(self) -> None:
        result = self.direct("Review harmless public configuration.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertNotRegex(result.stdout + result.stderr, r"approval_required|APPROVAL REQUIRED|exit 78|batch|broker")
        receipt = json.loads(result.receipt_path.read_text())  # type: ignore[attr-defined]
        self.assertRegex(receipt["authorization"]["requestEnvelopeSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(receipt["usage"]["total_tokens"], 18)
        serialized = json.dumps(receipt).lower()
        for forbidden in ("review harmless", "fixture response", "api_key", "secret"):
            self.assertNotIn(forbidden, serialized)

    def configure_fake_authority(self, state: str) -> None:
        fake = self.root / "workflow-authority"
        if state == "absent":
            fake.unlink(missing_ok=True)
        elif state == "ready":
            fake.write_text('#!/bin/sh\nprintf \'%s\\n\' \'{"status":"ready"}\'\n')
            fake.chmod(0o755)
        else:
            fake.write_text("#!/bin/sh\nexit 1\n")
            fake.chmod(0o755)

    def test_sensitive_payload_declines_before_contact(self) -> None:
        result = self.direct("OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(FixtureHandler.contacts, 0)

        repo = self.init_repo()
        result = self.run_pipeline(
            repo,
            "unused",
            prompt="DATABASE_URL=postgres://admin:secret@private.example/db",
        )
        self.assertEqual(result.returncode, 77)
        self.assertEqual(FixtureHandler.contacts, 0)

    def test_anthropic_slug_rejected_before_contact(self) -> None:
        result = subprocess.run([str(WRAPPER), "anthropic/claude-opus", "safe", "10"],
                                text=True, capture_output=True, env=self.env())
        self.assertEqual(result.returncode, 2)
        self.assertEqual(FixtureHandler.contacts, 0)

    def test_key_file_validation_remains_strict(self) -> None:
        key = self.root / "key"
        key.write_text("test\n")
        key.chmod(stat.S_IRUSR | stat.S_IWUSR)
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        ok = subprocess.run([str(WRAPPER), "z-ai/glm-5.2", "safe", "10"], env=env,
                            text=True, capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        contacts = FixtureHandler.contacts
        link = self.root / "key-link"
        link.symlink_to(key)
        env["OPENROUTER_API_KEY_FILE"] = str(link)
        bad = subprocess.run([str(WRAPPER), "z-ai/glm-5.2", "safe", "10"], env=env,
                             text=True, capture_output=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(FixtureHandler.contacts, contacts)

    def init_repo(self, name: str = "repo") -> Path:
        repo = self.root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
        (repo / "allowed.txt").write_text("before\n")
        (repo / "blocked.txt").write_text("blocked\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture base"], check=True)
        return repo

    def run_pipeline(self, repo: Path, diff: str, env: dict[str, str] | None = None,
                     prompt: str = "Implement the bounded harmless fixture.") -> subprocess.CompletedProcess[str]:
        FixtureHandler.response_text = diff
        run_env = env or self.env()
        run_env["OPENROUTER_EXEC_ALLOWED_PATHS"] = "allowed.txt"
        return subprocess.run([str(PIPELINE_EXEC), "--model", "z-ai/glm-5.2", "--timeout", "10"],
                              cwd=repo, input=prompt, text=True,
                              capture_output=True, env=run_env)

    def test_pipeline_accepts_allowed_diff_and_emits_wrapper_evidence(self) -> None:
        repo = self.init_repo()
        diff = "diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after"
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(), "after\n")
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["implementedBy"], "openrouter")
        self.assertEqual(receipt["actualModel"], "z-ai/glm-5.2")
        self.assertEqual(receipt["usage"]["total_tokens"], 18)
        self.assertRegex(receipt["requestEnvelopeSha256"], r"^[0-9a-f]{64}$")
        serialized = json.dumps(receipt).lower()
        for forbidden in ("broker", "implement the bounded", "api_key", "secret", diff.lower()):
            self.assertNotIn(forbidden, serialized)

    def test_pipeline_rejects_disallowed_path_before_application(self) -> None:
        repo = self.init_repo()
        diff = "diff --git a/blocked.txt b/blocked.txt\n--- a/blocked.txt\n+++ b/blocked.txt\n@@ -1 +1 @@\n-blocked\n+changed"
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 77)
        self.assertEqual((repo / "blocked.txt").read_text(), "blocked\n")
        self.assertEqual(subprocess.check_output(["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True).strip(), "1")

    def test_pipeline_rejects_pre_staged_paths_before_provider_contact(self) -> None:
        repo = self.init_repo()
        (repo / "blocked.txt").write_text("pre-staged\n")
        subprocess.run(["git", "-C", str(repo), "add", "blocked.txt"], check=True)
        contacts = FixtureHandler.contacts
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 77)
        self.assertEqual(FixtureHandler.contacts, contacts)
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_pipeline_rejects_unstaged_edit_in_approved_file(self) -> None:
        repo = self.init_repo()
        (repo / "allowed.txt").write_text("one\ntwo\nthree\n")
        subprocess.run(["git", "-C", str(repo), "add", "allowed.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "--amend", "--no-edit", "-q"], check=True)
        (repo / "allowed.txt").write_text("one\ntwo\nlocal unrelated\n")
        contacts = FixtureHandler.contacts
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1,2 +1,2 @@\n-one\n+model\n two")
        result = self.run_pipeline(repo, diff)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(FixtureHandler.contacts, contacts + 1)
        self.assertEqual((repo / "allowed.txt").read_text(), "one\ntwo\nlocal unrelated\n")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_pipeline_accepts_strict_key_file_without_env_key(self) -> None:
        repo = self.init_repo()
        key = self.root / "pipeline-key"
        key.write_text("test\n")
        key.chmod(0o600)
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(), "after\n")

    def test_pipeline_rolls_back_when_commit_creation_fails(self) -> None:
        repo = self.init_repo()
        env = self.env()
        env["GIT_AUTHOR_NAME"] = ""
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff, env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((repo / "allowed.txt").read_text(), "before\n")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True,
        ), "")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_missing_or_invalid_key_falls_back_without_prompt(self) -> None:
        repo = self.init_repo()
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        missing = self.run_pipeline(repo, "unused", env)
        self.assertEqual(missing.returncode, 77)
        self.assertNotRegex(missing.stderr, r"approval|digest|batch|broker")
        key = self.root / "bad-key"
        key.write_text("test\n")
        key.chmod(0o644)
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        invalid = self.run_pipeline(repo, "unused", env)
        self.assertEqual(invalid.returncode, 77)
        self.assertNotRegex(invalid.stderr, r"approve|question")

    def test_active_surfaces_ignore_workflow_authority(self) -> None:
        active = [
            REPO / "plugins/openrouter/commands/openrouter.md",
            REPO / "plugins/openrouter/agents/workflow/openrouter-agent-runner.md",
            REPO / "plugins/dm-review/skills/review/SKILL.md",
            REPO / "plugins/pipeline/references/openrouter-exec.sh",
            REPO / "plugins/pipeline/references/cascade-dispatch.sh",
        ]
        shell_active = "\n".join(path.read_text() for path in active[-2:])
        self.assertNotIn("/usr/local/bin/workflow-authority", shell_active)
        combined = "\n".join(path.read_text() for path in active)
        self.assertNotIn("exit 78", combined)
        self.assertNotIn("status\":\"approval_required", combined)
        self.assertNotIn("interim-operator-batch", combined)
        self.assertNotIn("exact-digest", combined)
        self.assertFalse((OPENROUTER / "skills/openrouter-delegate/references/runner-batch-authorization.sh").exists())
        self.assertFalse((OPENROUTER / "skills/openrouter-delegate/references/payload-authorization.sh").exists())
        review = active[2].read_text()
        self.assertIn('OPENROUTER_API_KEY_FILE', review)
        self.assertIn('OPENROUTER_AVAILABLE=true', review)
        self.assertIn('OPENROUTER_BOUNDARY_PATH', review)
        orchestrator = (REPO / "plugins/pipeline/agents/workflow/execution-orchestrator.md").read_text()
        self.assertIn('[ -n "${OPENROUTER_API_KEY_FILE:-}" ]', orchestrator)
        self.assertIn("export WORKFLOW_KERNEL", orchestrator)

        for state in ("absent", "ready", "broken"):
            with self.subTest(authority_state=state):
                self.configure_fake_authority(state)
                direct = self.direct("Review harmless public configuration.", self.installed)
                self.assertEqual(direct.returncode, 0, direct.stderr)
                repo = self.init_repo(f"repo-{state}")
                diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                        "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
                pipeline = self.run_pipeline(repo, diff)
                self.assertEqual(pipeline.returncode, 0, pipeline.stderr)


if __name__ == "__main__":
    unittest.main()
