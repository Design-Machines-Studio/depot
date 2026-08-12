"""Behavioral checks for the executable preflights in ned:operate-ned."""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/ned/skills/operate-ned/SKILL.md"


class OperateNEDSkillTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = SKILL.read_text(encoding="utf-8")
        heading = "Operations preflight and system-Docker wrapper:\n\n```bash\n"
        start = text.index(heading) + len(heading)
        cls.block = text[start : text.index("\n```", start)]

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="operate-ned-")
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.log = self.root / "docker.log"
        self.bin.mkdir()
        self._write_stub("hostname", "printf '%s\\n' \"${STUB_HOST:-ned9000}\"\n")
        self._write_stub("id", "printf '%s\\n' \"${STUB_USER:-trav}\"\n")
        self._write_stub("pwd", "printf '%s\\n' \"${STUB_WORKDIR:-/srv/review}\"\n")
        self._write_stub(
            "sudo",
            """if [[ "${1:-}" == "-n" ]]; then shift; fi
if [[ "${1:-}" == "true" ]]; then [[ "${STUB_SUDO_FAIL:-0}" != 1 ]]; exit; fi
exec "$@"
""",
        )
        self._write_stub(
            "docker",
            """for name in DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH EVIL_DOCKER_PLUGIN; do
  if [[ -v "$name" ]]; then printf 'leaked:%s\\n' "$name" >> "$STUB_DOCKER_LOG"; fi
done
printf 'call:%s\\n' "$*" >> "$STUB_DOCKER_LOG"
if [[ "$*" == *" info "* ]]; then
  [[ "${STUB_DOCKER_FAIL:-0}" == "1" ]] && exit 42
  expected='{{printf "%s\\t%s" .DockerRootDir (json .SecurityOptions)}}'
  [[ "$*" == *"--format $expected"* ]] || { printf 'bad format: %s\\n' "$*" >&2; exit 43; }
  printf '%s\\t%s\\n' "${STUB_DOCKER_ROOT:-/var/lib/docker}" "${STUB_DOCKER_SECURITY:-[\"name=seccomp\"]}"
fi
""",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _write_stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def _run(self, command: str, **overrides: str) -> subprocess.CompletedProcess[str]:
        block = self.block
        replacements = {
            "/usr/bin/hostname": self.bin / "hostname",
            "/usr/bin/id": self.bin / "id",
            "/bin/pwd": self.bin / "pwd",
            "/usr/bin/sudo": self.bin / "sudo",
            "/usr/bin/docker": self.bin / "docker",
        }
        for source, target in replacements.items():
            block = block.replace(source, str(target))
        stub_environment = {"STUB_DOCKER_LOG": str(self.log), **overrides}
        assignments = " ".join(
            "{}={}".format(name, shlex.quote(value))
            for name, value in stub_environment.items()
            if name.startswith("STUB_")
        )
        block = block.replace("/usr/bin/env -i", "/usr/bin/env -i " + assignments)
        environment = dict(os.environ)
        environment.update(
            {
                "STUB_DOCKER_LOG": str(self.log),
                "DOCKER_HOST": "tcp://attacker.invalid:2375",
                "DOCKER_CONTEXT": "attacker",
                "DOCKER_TLS_VERIFY": "1",
                "DOCKER_CERT_PATH": "/tmp/attacker-certs",
                "DOCKER_CONFIG": "/tmp/attacker-config",
                "EVIL_DOCKER_PLUGIN": "/tmp/attacker-plugin",
                **overrides,
            }
        )
        return subprocess.run(
            ["bash", "-c", block + "\n" + command],
            cwd=self.root,
            env=environment,
            text=True,
            capture_output=True,
        )

    def test_non_docker_operation_does_not_probe_docker(self):
        completed = self._run("operations_preflight")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertFalse(self.log.exists())

    def test_system_docker_pins_and_reuses_the_verified_socket(self):
        completed = self._run("system_docker ps")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        log = self.log.read_text(encoding="utf-8")
        self.assertNotIn("leaked:", log)
        self.assertEqual(log.count("--host unix:///var/run/docker.sock"), 2)
        self.assertIn(" info ", log)
        self.assertIn("call:--host unix:///var/run/docker.sock ps", log)

    def test_system_docker_rejects_leading_global_options(self):
        for argument in ("--config=/tmp/evil", "--context=evil", "-Htcp://evil", "--tlsverify=false"):
            with self.subTest(argument=argument):
                self.log.unlink(missing_ok=True)
                completed = self._run("system_docker " + argument + " ps")
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("global option refused", completed.stderr)
                self.assertFalse(self.log.exists())

    def test_system_docker_forwards_subcommand_options(self):
        completed = self._run("system_docker run image --config=/app/x")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            "call:--host unix:///var/run/docker.sock run image --config=/app/x",
            self.log.read_text(encoding="utf-8"),
        )

    def test_operations_preflight_rejects_wrong_boundary_before_docker(self):
        for overrides in (
            {"STUB_HOST": "other"},
            {"STUB_USER": "ned"},
            {"STUB_WORKDIR": "/tmp"},
            {"STUB_SUDO_FAIL": "1"},
        ):
            with self.subTest(overrides=overrides):
                self.log.unlink(missing_ok=True)
                completed = self._run("system_docker ps", **overrides)
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_failed_probe_stops_before_the_operation(self):
        completed = self._run("system_docker ps", STUB_DOCKER_FAIL="1")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("system_docker_probe=failed", completed.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").count("call:"), 1)

    def test_wrong_root_stops_before_the_operation(self):
        completed = self._run("system_docker ps", STUB_DOCKER_ROOT="/tmp/rootless")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("docker_root=/tmp/rootless", completed.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").count("call:"), 1)

    def test_rootless_daemon_stops_before_the_operation(self):
        completed = self._run(
            "system_docker ps", STUB_DOCKER_SECURITY='["name=rootless"]'
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("docker_rootless=true", completed.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").count("call:"), 1)

    def test_system_docker_requires_an_explicit_command(self):
        completed = self._run("system_docker")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires an explicit Docker command", completed.stderr)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
