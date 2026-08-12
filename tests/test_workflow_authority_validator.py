"""Focused portability tests for tools/validate-workflow-authority.sh."""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "tools" / "validate-workflow-authority.sh"
FIDO_SOURCE = (
    REPO_ROOT
    / "native"
    / "workflow-authority"
    / "internal"
    / "authority"
    / "fido_libfido2.go"
)
GO_MODULE = REPO_ROOT / "native" / "workflow-authority"


class WorkflowAuthorityValidatorTest(unittest.TestCase):
    def make_executable(self, path, source):
        path.write_text(source, encoding="utf-8")
        path.chmod(0o755)

    def run_validator(self, libfido2_version, go_version="go1.26.5"):
        with tempfile.TemporaryDirectory(prefix="wa-validator-") as directory:
            root = Path(directory)
            fake_bin = root / "distro-bin"
            fake_goroot = root / "selected-toolchain"
            fake_bin.mkdir()
            (fake_goroot / "bin").mkdir(parents=True)

            self.make_executable(
                fake_bin / "go",
                """#!/usr/bin/env bash
if [[ "$(umask)" != "0022" ]]; then
  printf 'unsafe validator umask: %s\\n' "$(umask)" >&2
  exit 90
fi
if [[ "$*" == "env GOVERSION" ]]; then
  printf '%s\\n' "${FAKE_GO_VERSION}"
elif [[ "$*" == "env GOROOT" ]]; then
  printf '%s\\n' "${FAKE_GO_ROOT}"
elif [[ "$1" == "list" && "$*" == *"-tags fixture"* ]]; then
  printf '%s\\n' 'designmachines.dev/workflow-authority/cmd/workflow-authority-fixture'
elif [[ "$1" == "list" ]]; then
  printf '%s\\n' 'designmachines.dev/workflow-authority/internal/authority'
fi
""",
            )
            self.make_executable(fake_goroot / "bin" / "gofmt", "#!/usr/bin/env bash\n")

            if libfido2_version.startswith("1.15."):
                minimum_result = 1
                next_major_result = 1
            elif libfido2_version.startswith("1.16."):
                minimum_result = 0
                next_major_result = 1
            else:
                minimum_result = 0
                next_major_result = 0
            self.make_executable(
                fake_bin / "pkg-config",
                """#!/usr/bin/env bash
case "$1" in
  --modversion) printf '%s\\n' "${FAKE_LIBFIDO2_VERSION}" ;;
  --atleast-version=1.16.0) exit ${FAKE_MINIMUM_RESULT} ;;
  --atleast-version=2) exit ${FAKE_NEXT_MAJOR_RESULT} ;;
  *) exit 1 ;;
esac
""",
            )
            self.make_executable(
                fake_bin / "python3",
                """#!/usr/bin/env bash
if [[ "$1" == "-I" ]]; then
  exit 0
fi
printf '%s\\n' \\
  'test_accept (tests.test_workflow_authority_integration.WorkflowAuthorityIntegrationTest.test_accept) ... ok' \\
  'test_deny (tests.test_workflow_authority_integration.DenyMatrixTest.test_deny) ... ok' \\
  'test_hostility (tests.test_workflow_authority_integration.ProcessHostilityTest.test_hostility) ... ok' \\
  'test_gaps (tests.test_workflow_authority_integration.UnrunLaneLedgerTest.test_gaps) ... ok' \\
  'Ran 4 tests in 0.001s' \\
  'OK' \\
  '  GAP  fixture: fake harness does not exercise broker behavior'
""",
            )

            environment = dict(os.environ)
            environment.update(
                {
                    "PATH": "{}:{}".format(fake_bin, environment["PATH"]),
                    "FAKE_GO_VERSION": go_version,
                    "FAKE_GO_ROOT": str(fake_goroot),
                    "FAKE_LIBFIDO2_VERSION": libfido2_version,
                    "FAKE_MINIMUM_RESULT": str(minimum_result),
                    "FAKE_NEXT_MAJOR_RESULT": str(next_major_result),
                    "WORKFLOW_AUTHORITY_REQUIRE_PRODUCTION_BUILD": "1",
                }
            )
            completed = subprocess.run(
                ["bash", str(VALIDATOR)],
                cwd=REPO_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return completed, fake_bin / "go", fake_goroot

    def test_non_usr_local_launcher_selects_go_1_26_5_and_accepts_libfido2_1_16(self):
        completed, go_launcher, go_root = self.run_validator("1.16.7")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(go_launcher.is_absolute())
        self.assertFalse(str(go_launcher).startswith("/usr/local/"))
        self.assertIn("launcher={}".format(go_launcher), completed.stdout)
        self.assertIn("GOVERSION=go1.26.5", completed.stdout)
        self.assertIn("GOROOT={}".format(go_root), completed.stdout)
        self.assertIn("libfido2 1.16.7 (required >=1.16.0,<2)", completed.stdout)

    def test_libfido2_1_15_and_2_x_are_rejected(self):
        for version in ("1.15.9", "2.0.0"):
            with self.subTest(version=version):
                completed, _, _ = self.run_validator(version)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("requires Linux, pkg-config, and libfido2 >=1.16.0,<2", completed.stderr)
                self.assertIn("libfido2={}".format(version), completed.stderr)

    def test_shell_and_c_guards_express_the_same_range(self):
        shell = VALIDATOR.read_text(encoding="utf-8")
        c_source = FIDO_SOURCE.read_text(encoding="utf-8")
        minimum = re.search(r'LIBFIDO2_MIN_VERSION="(\d+)\.(\d+)\.(\d+)"', shell)
        next_major = re.search(r'LIBFIDO2_NEXT_MAJOR="(\d+)"', shell)
        c_guard = re.search(
            r"WORKFLOW_AUTHORITY_LIBFIDO2_MAJOR != (\d+) \|\| "
            r"WORKFLOW_AUTHORITY_LIBFIDO2_MINOR < (\d+)",
            c_source,
        )
        self.assertIsNotNone(minimum)
        self.assertIsNotNone(next_major)
        self.assertIsNotNone(c_guard)
        self.assertEqual(
            (minimum.group(1), minimum.group(2), next_major.group(1)),
            (c_guard.group(1), c_guard.group(2), str(int(c_guard.group(1)) + 1)),
        )
        self.assertIn('pkg-config --atleast-version="$LIBFIDO2_MIN_VERSION" libfido2', shell)
        self.assertIn('! pkg-config --atleast-version="$LIBFIDO2_NEXT_MAJOR" libfido2', shell)
        for component in ("MAJOR", "MINOR", "PATCH"):
            self.assertIn("WORKFLOW_AUTHORITY_LIBFIDO2_{}".format(component), shell)
            self.assertIn("WORKFLOW_AUTHORITY_LIBFIDO2_{}".format(component), c_source)

    def test_wrong_selected_go_toolchain_fails_clearly(self):
        completed, go_launcher, _ = self.run_validator("1.16.7", go_version="go1.26.4")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires selected Go toolchain go1.26.5", completed.stderr)
        self.assertIn(str(go_launcher), completed.stderr)

    def test_installed_compatible_libfido2_compiles_production_adapter(self):
        go_bin = shutil.which("go")
        pkg_config = shutil.which("pkg-config")
        if not go_bin or not pkg_config or os.uname().sysname != "Linux":
            self.skipTest("real Linux Go and pkg-config toolchain unavailable")
        minimum = subprocess.run(
            [pkg_config, "--atleast-version=1.16.0", "libfido2"], check=False
        )
        next_major = subprocess.run(
            [pkg_config, "--atleast-version=2", "libfido2"], check=False
        )
        if minimum.returncode != 0 or next_major.returncode == 0:
            self.skipTest("installed libfido2 is outside the supported production range")
        version = subprocess.run(
            [pkg_config, "--modversion", "libfido2"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
        self.assertIsNotNone(match, "pkg-config returned a non-numeric libfido2 version")

        with tempfile.TemporaryDirectory(prefix="wa-real-cgo-cache-") as go_cache:
            environment = dict(os.environ)
            environment.update(
                {
                    "CGO_CPPFLAGS": (
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_MAJOR={} "
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_MINOR={} "
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_PATCH={}"
                    ).format(*match.groups()),
                    "GOCACHE": go_cache,
                    "GOTOOLCHAIN": "auto",
                }
            )
            completed = subprocess.run(
                [go_bin, "test", "-tags", "libfido2", "./internal/authority"],
                cwd=GO_MODULE,
                env=environment,
                capture_output=True,
                text=True,
                timeout=120,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
