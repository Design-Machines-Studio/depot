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

    def run_validator(self, libfido2_version, go_version="go1.26.5", hostile_env=None, artifact_case=None):
        with tempfile.TemporaryDirectory(prefix="wa-validator-") as directory:
            root = Path(directory)
            fixture_repo = root / "repo"
            fixture_tools = fixture_repo / "tools"
            fake_bin = root / "distro-bin"
            fake_goroot = root / "selected-toolchain"
            fixture_tools.mkdir(parents=True)
            fake_bin.mkdir()
            (fake_goroot / "bin").mkdir(parents=True)

            validator_source = VALIDATOR.read_text(encoding="utf-8")
            path_line = 'PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/usr/local/go/bin:/opt/homebrew/bin"'
            self.assertEqual(validator_source.count(path_line), 1)
            validator_source = validator_source.replace(
                path_line, 'PATH="{}:/usr/bin:/bin:/usr/sbin:/sbin"'.format(fake_bin)
            )
            for trusted_line, replacement in (
                ('GO_BIN="$(trusted_executable "$GO_BIN")" || { printf \'FAIL  Go launcher is not root-owned and non-writable\\n\' >&2; exit 1; }', 'GO_BIN="$(readlink -f "$GO_BIN")"'),
                ('PKG_CONFIG_BIN="$(trusted_executable "$PKG_CONFIG_BIN")" || { printf \'FAIL  pkg-config is not root-owned and non-writable\\n\' >&2; exit 1; }', 'PKG_CONFIG_BIN="$(readlink -f "$PKG_CONFIG_BIN")"'),
                ('CC="$(trusted_executable "$CC_BIN")" || { printf \'FAIL  C compiler is not root-owned and non-writable\\n\' >&2; exit 1; }', 'CC="$(readlink -f "$CC_BIN")"'),
                ('PYTHON="$(trusted_executable "$(type -P "$CANDIDATE")")" || continue', 'PYTHON="$(readlink -f "$(type -P "$CANDIDATE")")"'),
            ):
                self.assertEqual(validator_source.count(trusted_line), 1)
                validator_source = validator_source.replace(trusted_line, replacement)
            validator_source = validator_source.replace(
                'case "$(readlink -f "$GO_ROOT")" in\n  "$GO_MODULE_CACHE"/*) ;;',
                'case "$(readlink -f "$GO_ROOT")" in\n  "$FAKE_GO_ROOT"/*|"$FAKE_GO_ROOT") ;;',
            )
            fixture_validator = fixture_tools / VALIDATOR.name
            fixture_validator.write_text(validator_source, encoding="utf-8")
            fixture_validator.chmod(0o755)
            (fixture_repo / "native").mkdir()
            shutil.copytree(
                REPO_ROOT / "native/workflow-authority",
                fixture_repo / "native/workflow-authority",
            )
            (fixture_repo / "plugins").symlink_to(
                REPO_ROOT / "plugins", target_is_directory=True
            )
            (fixture_repo / "tests").mkdir()
            (fixture_repo / "tests/test_workflow_authority_integration.py").symlink_to(
                REPO_ROOT / "tests/test_workflow_authority_integration.py"
            )
            subprocess.run(["git", "init", "-q"], cwd=fixture_repo, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=fixture_repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=fixture_repo, check=True)
            subprocess.run(["git", "add", "."], cwd=fixture_repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=fixture_repo, check=True)
            fixture_commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=fixture_repo, check=True,
                capture_output=True, text=True,
            ).stdout.strip()

            self.make_executable(
                fake_bin / "go",
                """#!/usr/bin/env bash
printf '%s|cpp=%s|goenv=%s|cc=%s|pkg=%s\\n' "$*" "${CGO_CPPFLAGS:-}" "${GOENV:-}" "${CC:-}" "${PKG_CONFIG:-}" >> "$FAKE_GO_LOG"
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
if [[ "$*" == *"-tags libfido2"* && "${CGO_CPPFLAGS:-}" != "${FAKE_EXPECTED_CPPFLAGS}" ]]; then
  printf 'missing expected production CGO_CPPFLAGS\\n' >&2
  exit 91
fi
previous=""
for argument in "$@"; do
  if [[ "$previous" == "-o" ]]; then printf 'fixture-binary\\n' > "$argument"; chmod 0755 "$argument"; fi
  previous="$argument"
done
""",
            )
            self.make_executable(fake_goroot / "bin" / "gofmt", "#!/usr/bin/env bash\n")

            version_tuple = tuple(map(int, libfido2_version.split(".")))
            minimum_result = int(version_tuple < (1, 16, 0))
            next_major_result = int(version_tuple < (2, 0, 0))
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
                    "FAKE_EXPECTED_CPPFLAGS": (
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_MAJOR={} "
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_MINOR={} "
                        "-DWORKFLOW_AUTHORITY_LIBFIDO2_PATCH={}"
                    ).format(*version_tuple),
                    "WORKFLOW_AUTHORITY_REQUIRE_PRODUCTION_BUILD": "1",
                    "FAKE_GO_LOG": str(root / "go.log"),
                }
            )
            if hostile_env:
                environment.update(hostile_env)
            artifact_dir = root / "artifacts"
            if artifact_case:
                environment["WORKFLOW_AUTHORITY_ARTIFACT_DIR"] = str(artifact_dir)
                environment["WORKFLOW_AUTHORITY_REVIEWED_COMMIT"] = fixture_commit
                if artifact_case == "mismatch":
                    environment["WORKFLOW_AUTHORITY_REVIEWED_COMMIT"] = "0" * 40
                elif artifact_case == "dirty":
                    (fixture_repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
                elif artifact_case == "nonempty":
                    artifact_dir.mkdir()
                    (artifact_dir / "existing").write_text("occupied\n", encoding="utf-8")
                elif artifact_case == "missing-commit":
                    environment.pop("WORKFLOW_AUTHORITY_REVIEWED_COMMIT")
                elif artifact_case == "ignored":
                    exclude = fixture_repo / ".git/info/exclude"
                    exclude.write_text("native/workflow-authority/ignored.go\n", encoding="utf-8")
                    ignored = fixture_repo / "native/workflow-authority/ignored.go"
                    ignored.write_text("package ignored\n", encoding="utf-8")
            completed = subprocess.run(
                ["bash", str(fixture_validator)],
                cwd=fixture_repo,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            ledger = (root / "go.log").read_text(encoding="utf-8") if (root / "go.log").exists() else ""
            artifact_snapshot = {
                path.name: (path.read_bytes(), path.stat().st_mode & 0o777)
                for path in artifact_dir.glob("*") if path.is_file()
            }
            return completed, fake_bin / "go", fake_goroot, ledger, artifact_snapshot

    def test_non_usr_local_launcher_selects_go_1_26_5_and_accepts_libfido2_1_16(self):
        completed, go_launcher, go_root, ledger, _ = self.run_validator("1.16.7")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(go_launcher.is_absolute())
        self.assertFalse(str(go_launcher).startswith("/usr/local/"))
        self.assertIn("launcher={}".format(go_launcher), completed.stdout)
        self.assertIn("GOVERSION=go1.26.5", completed.stdout)
        self.assertIn("GOROOT={}".format(go_root), completed.stdout)
        self.assertIn("libfido2 1.16.7 (required >=1.16.0,<2)", completed.stdout)
        tagged = [line.split("|", 1)[0] for line in ledger.splitlines() if "-tags libfido2" in line]
        self.assertEqual(tagged, [
            "test -tags libfido2 ./...",
            "test -race -tags libfido2 ./...",
            "vet -tags libfido2 ./...",
            "build -tags libfido2 ./cmd/workflow-authority ./cmd/workflow-authorityd",
        ])
        for line in ledger.splitlines():
            self.assertIn("|goenv=off|", line)

    def test_libfido2_1_15_and_2_x_are_rejected(self):
        for version in ("1.15.9", "2.0.0"):
            with self.subTest(version=version):
                completed, _, _, _, _ = self.run_validator(version)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn("requires Linux, pkg-config, and libfido2 >=1.16.0,<2", completed.stderr)
                self.assertIn("libfido2={}".format(version), completed.stderr)

    def test_later_libfido2_1_x_versions_are_accepted(self):
        for version in ("1.17.0", "1.99.4"):
            with self.subTest(version=version):
                completed, _, _, _, _ = self.run_validator(version)
                self.assertEqual(
                    completed.returncode, 0, completed.stdout + completed.stderr
                )
                self.assertIn("libfido2 {}".format(version), completed.stdout)

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
        self.assertIn('"$PKG_CONFIG_BIN" --atleast-version="$LIBFIDO2_MIN_VERSION" libfido2', shell)
        self.assertIn('! "$PKG_CONFIG_BIN" --atleast-version="$LIBFIDO2_NEXT_MAJOR" libfido2', shell)
        for component in ("MAJOR", "MINOR", "PATCH"):
            self.assertIn("WORKFLOW_AUTHORITY_LIBFIDO2_{}".format(component), shell)
            self.assertIn("WORKFLOW_AUTHORITY_LIBFIDO2_{}".format(component), c_source)

    def test_wrong_selected_go_toolchain_fails_clearly(self):
        completed, go_launcher, _, _, _ = self.run_validator("1.16.7", go_version="go1.26.4")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires selected Go toolchain go1.26.5", completed.stderr)
        self.assertIn(str(go_launcher), completed.stderr)

    def test_caller_build_environment_and_exported_functions_are_ignored(self):
        completed, go_launcher, _, ledger, _ = self.run_validator(
            "1.16.7",
            hostile_env={
                "GOENV": "/tmp/evil-go-env",
                "GOFLAGS": "-overlay=/tmp/evil-overlay.json",
                "CC": "/tmp/evil-cc",
                "PKG_CONFIG": "/tmp/evil-pkg-config",
                "BASH_FUNC_go%%": "() { exit 88; }",
                "BASH_FUNC_pkg-config%%": "() { printf '9.9.9\\n'; }",
            },
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("launcher={}".format(go_launcher), completed.stdout)
        self.assertNotIn("evil", ledger)
        self.assertTrue(all("|goenv=off|" in line for line in ledger.splitlines()))

    def test_artifact_build_requires_exact_clean_commit_and_empty_staging(self):
        for case, expected in (
            ("mismatch", "does not match reviewed artifact commit"),
            ("dirty", "requires a clean checkout"),
            ("nonempty", "must be absent or empty"),
            ("missing-commit", "require both"),
            ("ignored", "ignored build inputs"),
        ):
            with self.subTest(case=case):
                completed, _, _, _, _ = self.run_validator("1.16.7", artifact_case=case)
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(expected, completed.stderr)

    def test_artifact_build_emits_equal_clients_and_verifiable_receipt(self):
        completed, _, _, _, artifacts = self.run_validator("1.16.7", artifact_case="valid")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        expected = {"workflow-authority", "workflow-authority-admin", "workflow-authorityd", "BUILD-RECEIPT.txt"}
        self.assertEqual(set(artifacts), expected)
        self.assertEqual(artifacts["workflow-authority"][0], artifacts["workflow-authority-admin"][0])
        for binary in expected - {"BUILD-RECEIPT.txt"}:
            self.assertEqual(artifacts[binary][1], 0o755)
        receipt = artifacts["BUILD-RECEIPT.txt"][0].decode()
        self.assertIn("commit=", receipt)
        self.assertIn("go_version=go1.26.5", receipt)
        self.assertIn("libfido2=1.16.7", receipt)
        self.assertEqual(receipt.count("  workflow-authority\n"), 1)
        self.assertEqual(receipt.count("  workflow-authority-admin\n"), 1)
        self.assertEqual(receipt.count("  workflow-authorityd\n"), 1)

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
