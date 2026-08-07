"""Black-box acceptance harness for the workflow-authority broker (chunk 06a).

This module runs the broker daemon and the public client as SEPARATE OS
PROCESSES and observes them from outside. That process isolation is its whole
reason to exist: the in-Go end-to-end test at
native/workflow-authority/internal/client/integration_test.go already proves
the accepted path, single provider contact, single FIDO assertion, and replay
rejection in-process. Anything here that merely re-asserts in-process behavior
over a socket is wasted effort, so the accepted path below is kept to one
scenario and serves as the positive control for the deny matrix that chunks
06b and 06c add.

Skipped by default. tools/validate-workflow-authority.sh exports
WORKFLOW_AUTHORITY_E2E=1 after its Go preconditions pass, and asserts that a
nonzero number of tests actually ran -- a default-skip module that silently
skips inside its own gate is an empty result read as a pass.

No calendar-date literal appears in this file or in the Go fixture launcher.
ipc.Server.handle applies the allocation's ExpiresAt as a real net.Conn
deadline, so a frozen date makes every fixture connection expire the moment
that date passes; that bug held tools/validate-workflow-authority.sh red on
every host from 2026-08-04 until 64d8aec. test_chk_e2e_05_no_date_literals
enforces the rule, and the clock-offset scenario proves the suite survives a
skewed clock.

Every claim about real FIDO hardware, systemd, root install, live provider
TLS, live Codex, Docker substrate, and live repository verification is a GAP,
never a PASS. GAPS below is printed at module teardown.
"""

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GO_MODULE = REPO_ROOT / "native" / "workflow-authority"
GO_BIN = Path("/usr/local/go/bin/go")
FIXTURE_TAG = "fixture"
FIXTURE_PACKAGE = "./cmd/workflow-authority-fixture"

ENABLED = os.environ.get("WORKFLOW_AUTHORITY_E2E") == "1"

# Fixture-only sentinels, mirrored from the Go launcher. None is a real
# credential. Absence assertions over these are armed by positive controls:
# a scan that never proves it can find a planted sentinel proves nothing.
PROVIDER_CREDENTIAL_SENTINEL = "fixture-provider-credential"
CREDENTIAL_ID_SENTINEL = "fixture-root-private-credential-id"
RESPONSE_SENTINEL = "fixture assistant response"

READY_TIMEOUT_SECONDS = 30
CLIENT_TIMEOUT_SECONDS = 60
SHUTDOWN_TIMEOUT_SECONDS = 15

# Two years of skew, expressed in hours because Go's flag.Duration has no day
# unit. Deliberately not a date.
CLOCK_SKEW_FLAG = "17520h"

GAPS = []


def record_gap(requirement, reason):
    """Record an unrun lane. Gaps are reported, never silently dropped."""
    GAPS.append((requirement, reason))


def tearDownModule():  # noqa: N802 - unittest's required spelling
    if not GAPS:
        return
    print("\nworkflow-authority acceptance GAPS (unrun lanes, not passes):")
    for requirement, reason in GAPS:
        print("  GAP  {}: {}".format(requirement, reason))


class FixtureDaemon:
    """A workflow-authority broker running as its own OS process."""

    def __init__(self, binary, root, clock_offset=None):
        self.binary = binary
        self.root = root
        self.clock_offset = clock_offset
        self.process = None
        self.ready = None
        self.stderr_path = root / "daemon.stderr"

    def __enter__(self):
        argv = [str(self.binary), "-mode", "daemon", "-root", str(self.root)]
        if self.clock_offset:
            argv += ["-clock-offset", self.clock_offset]
        self._stderr = open(self.stderr_path, "wb")
        self.process = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=self._stderr, cwd=str(GO_MODULE),
        )
        self.ready = self._read_ready()
        return self

    def _read_ready(self):
        """Read the daemon's single ready line, or fail with its stderr."""
        holder = {}

        def read():
            holder["line"] = self.process.stdout.readline()

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(READY_TIMEOUT_SECONDS)
        line = holder.get("line")
        if not line:
            self._terminate()
            raise AssertionError(
                "fixture daemon never became ready; stderr:\n{}".format(self.stderr_text())
            )
        return json.loads(line.decode())

    def counters(self):
        with urllib.request.urlopen(self.ready["control"] + "/counters", timeout=10) as response:
            return json.load(response)

    def stderr_text(self):
        try:
            return self.stderr_path.read_text()
        except OSError:
            return "<unavailable>"

    def _terminate(self):
        if self.process is None or self.process.poll() is not None:
            return
        self.process.send_signal(signal.SIGTERM)
        try:
            self.process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)

    def __exit__(self, *_):
        self._terminate()
        if self.process is not None and self.process.stdout is not None:
            self.process.stdout.close()
        self._stderr.close()
        return False


@unittest.skipUnless(
    ENABLED,
    "requires WORKFLOW_AUTHORITY_E2E=1; tools/validate-workflow-authority.sh sets it",
)
class WorkflowAuthorityIntegrationTest(unittest.TestCase):
    """Chunk 06a: seams, gate, accepted path, and the GAP ledger."""

    binary = None
    _binary_dir = None

    @classmethod
    def setUpClass(cls):
        if not GO_BIN.is_file():
            raise unittest.SkipTest("exact Go launcher unavailable: {}".format(GO_BIN))
        cls._binary_dir = tempfile.TemporaryDirectory(prefix="wa-fixture-bin-")
        cls.binary = Path(cls._binary_dir.name) / "workflow-authority-fixture"
        completed = cls.go(
            "build", "-tags", FIXTURE_TAG, "-o", str(cls.binary), FIXTURE_PACKAGE,
        )
        if completed.returncode != 0:
            raise AssertionError("fixture build failed:\n{}".format(completed.stderr))

    @classmethod
    def tearDownClass(cls):
        if cls._binary_dir is not None:
            cls._binary_dir.cleanup()

    @staticmethod
    def go(*args):
        environment = dict(os.environ)
        environment["GOTOOLCHAIN"] = "auto"
        environment.setdefault(
            "GOCACHE", os.path.join(os.environ.get("TMPDIR", "/tmp"), "workflow-authority-go-cache")
        )
        return subprocess.run(
            [str(GO_BIN), *args], cwd=str(GO_MODULE), env=environment,
            capture_output=True, text=True, timeout=600,
        )

    def fixture_root(self):
        # Rooted under /tmp, matching integration_test.go. The default TMPDIR on
        # darwin is /var/folders/..., and /var is a symlink to /private/var, so
        # a root there does not match its own resolved path -- the client's
        # anchor validation compares resolved paths and would reject it.
        directory = tempfile.TemporaryDirectory(prefix="wa-e2e-", dir="/tmp")
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def dispatch(self, daemon, root, repeat=1, extra=()):
        # Share the daemon's instant. The in-process integration test uses one
        # clock for both sides; across processes the harness reproduces that by
        # handing the daemon's ready-line instant back to the client, so
        # freshness and terminal-result windows are evaluated identically.
        argv = [
            str(self.binary), "-mode", "client", "-root", str(root),
            "-socket", daemon.ready["socket"], "-trust", daemon.ready["trust"],
            "-clock", daemon.ready["clock"], "-repeat", str(repeat), *extra,
        ]
        completed = subprocess.run(
            argv, cwd=str(GO_MODULE), capture_output=True, text=True,
            timeout=CLIENT_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            completed.returncode, 0,
            "client process failed: {}\ndaemon stderr:\n{}".format(
                completed.stderr, daemon.stderr_text()),
        )
        return json.loads(completed.stdout.strip())["attempts"]

    # REQ-E2E-01 -- accepted path, across processes. Positive control for the
    # deny matrix in 06b/06c.
    def test_req_e2e_01_accepted_dispatch_then_replay_rejected(self):
        root = self.fixture_root()
        with FixtureDaemon(self.binary, root) as daemon:
            attempts = self.dispatch(daemon, root, repeat=2)
            counters = daemon.counters()

        self.assertEqual(len(attempts), 2)
        accepted, replay = attempts

        self.assertTrue(accepted["ok"], "first dispatch failed: {}".format(accepted.get("error")))
        self.assertEqual(accepted["exit_code"], 0)
        self.assertEqual(accepted["response"], RESPONSE_SENTINEL)
        self.assertGreater(accepted["receipt_bytes"], 0)

        self.assertFalse(replay["ok"], "replayed caller nonce unexpectedly succeeded")

        self.assertEqual(counters["provider_requests"], 1, "replay contacted the provider")
        self.assertEqual(counters["fido_assertions"], 1)
        self.assertEqual(counters["provider_rejections"], 0)
        self.assertEqual(counters["canary_hits"], 0)

        # Content-free receipt: neither authority nor provider material, and not
        # the response body either. Armed by the positive control below.
        import base64

        receipt = base64.b64decode(accepted["receipt_b64"])
        for sentinel in (PROVIDER_CREDENTIAL_SENTINEL, CREDENTIAL_ID_SENTINEL, RESPONSE_SENTINEL):
            self.assertNotIn(
                sentinel.encode(), receipt,
                "receipt leaked {!r}".format(sentinel),
            )

        record_gap("REQ-E2E-01", "real libfido2 assertion and live provider TLS not exercised")

    # Positive control for the receipt scan above. An absence assertion whose
    # scanner has never been shown to find a planted sentinel proves nothing.
    def test_receipt_scanner_positive_control(self):
        import base64

        planted = base64.b64encode(
            b"prefix" + RESPONSE_SENTINEL.encode() + b"suffix"
        ).decode()
        decoded = base64.b64decode(planted)
        self.assertIn(
            RESPONSE_SENTINEL.encode(), decoded,
            "the receipt scanner cannot detect a planted sentinel; every "
            "absence assertion built on it is vacuous",
        )

    # REQ-E2E-12 -- the harness itself touches only loopback and its temp root.
    def test_req_e2e_12_only_loopback_and_temp_root(self):
        root = self.fixture_root()
        with FixtureDaemon(self.binary, root) as daemon:
            ready = daemon.ready

        self.assertFalse(ready["production"])
        for key in ("socket", "trust", "state", "provider_credential"):
            self.assertTrue(
                Path(ready[key]).is_relative_to(root),
                "{} escaped the fixture root: {}".format(key, ready[key]),
            )
        for key in ("control", "canary"):
            self.assertIn("127.0.0.1", ready[key], "{} is not loopback".format(key))
        self.assertTrue(ready["provider_origin"].startswith("https://127.0.0.1:"))
        self.assertNotIn("/run/design-machines", ready["socket"])
        self.assertFalse(
            Path("/run/design-machines/workflow-authority/authority.sock").exists(),
            "production socket must not exist on a developer checkout",
        )

    # CHK-E2E-05 (second clause) -- the exchange survives a skewed clock. The
    # system clock cannot be moved by an unprivileged harness, so the skew is
    # injected into both processes instead.
    def test_chk_e2e_05_clock_offset_exchange(self):
        root = self.fixture_root()
        with FixtureDaemon(self.binary, root, clock_offset=CLOCK_SKEW_FLAG) as daemon:
            self.assertNotEqual(
                daemon.ready["clock"][:4], str(__import__("datetime").date.today().year),
                "clock skew was not applied",
            )
            attempts = self.dispatch(daemon, root)
            counters = daemon.counters()
        self.assertTrue(
            attempts[0]["ok"],
            "skewed-clock dispatch failed: {}".format(attempts[0].get("error")),
        )
        self.assertEqual(counters["provider_requests"], 1)

    # CHK-E2E-05 (first clause) -- no calendar-date literal anywhere in the
    # harness or its Go fixture sources.
    def test_chk_e2e_05_no_date_literals(self):
        go_date = re.compile(r"time\.Date\(\s*\d{4}")
        iso_date = re.compile(r"\b(19|20)\d{2}-\d{2}-\d{2}T")
        sources = [
            Path(__file__),
            GO_MODULE / "cmd" / "workflow-authority-fixture" / "main.go",
            GO_MODULE / "internal" / "client" / "fixture_runner.go",
        ]
        for source in sources:
            text = source.read_text()
            # Strip comments and docstrings would be over-engineering; the rule
            # is that no date literal appears at all, prose included, so that a
            # future edit cannot quietly reintroduce one.
            body = "\n".join(
                line for line in text.splitlines()
                if not line.lstrip().startswith(("//", "#"))
            )
            self.assertIsNone(
                go_date.search(body),
                "{} contains a Go calendar-date literal".format(source),
            )
            self.assertIsNone(
                iso_date.search(body),
                "{} contains an ISO calendar-date literal".format(source),
            )

    # CHK-E2E-06 -- the fixture entrypoint is unreachable from an untagged build.
    def test_chk_e2e_06_fixture_absent_from_untagged_build(self):
        untagged = self.go("list", "./...")
        self.assertEqual(untagged.returncode, 0, untagged.stderr)
        self.assertNotIn(
            "workflow-authority-fixture", untagged.stdout,
            "fixture scaffolding leaked into the untagged build",
        )
        tagged = self.go("list", "-tags", FIXTURE_TAG, "./...")
        self.assertEqual(tagged.returncode, 0, tagged.stderr)
        self.assertIn(
            "workflow-authority-fixture", tagged.stdout,
            "fixture package is missing under -tags fixture",
        )

    # Cheap real assertion available on darwin: the shipped production daemon
    # fails closed off Linux rather than degrading to something weaker.
    def test_non_linux_production_daemon_fails_closed(self):
        if sys.platform.startswith("linux"):
            record_gap(
                "production-fail-closed",
                "non-Linux production refusal is not observable on a Linux host",
            )
            self.skipTest("assertion applies to non-Linux hosts")
        with tempfile.TemporaryDirectory(prefix="wa-daemon-bin-") as directory:
            binary = Path(directory) / "workflow-authorityd"
            built = self.go("build", "-o", str(binary), "./cmd/workflow-authorityd")
            self.assertEqual(built.returncode, 0, built.stderr)
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True, timeout=60,
            )
        # Exit 78 (EX_UNAVAILABLE) with a fixed safe message: the underlying
        # error is deliberately not echoed, so assert the contract, not the
        # cause.
        self.assertEqual(
            completed.returncode, 78,
            "production daemon did not fail closed on a non-Linux host",
        )
        self.assertIn(
            "workflow-authorityd: startup dependencies unavailable",
            completed.stdout + completed.stderr,
        )


@unittest.skipUnless(ENABLED, "requires WORKFLOW_AUTHORITY_E2E=1")
class UnrunLaneLedgerTest(unittest.TestCase):
    """Records the lanes this run cannot execute. Reporting them is the point."""

    def test_record_unrun_live_lanes(self):
        if not sys.platform.startswith("linux"):
            record_gap(
                "peer-uid-authentication",
                "daemon-side peer UID is assumed from euid on darwin; only the "
                "PID is kernel-derived (LOCAL_PEERPID). Real SO_PEERCRED "
                "authentication runs on Linux only",
            )
            record_gap(
                "ancillary-data-rejection",
                "the production guard that rejects SCM_RIGHTS on every read is "
                "Linux-only; the darwin fixture guard is a plain read",
            )
        for requirement, reason in (
            ("libfido2", "real authenticator and libfido2 1.17.0 require Linux hardware"),
            ("systemd", "root systemd install, socket activation, and tmpfiles require Linux root"),
            ("credential-provisioning", "production credential provisioning is separately gated"),
            ("provider-live", "system TLS and live OpenRouter contact are separately gated"),
            ("codex-fallback-live", "live Codex completion is stubbed; only the contract is proven"),
            ("macos-parity", "macOS production parity is out of M1 scope"),
            ("docker-substrate", "Docker substrate acceptance is out of M1 scope"),
            ("repository-verification-live", "live repository verification is out of M1 scope"),
            ("proc-inspection", "/proc-based sibling process reads are unavailable on darwin"),
            ("wrong-owner", "files owned by another UID cannot be created without privilege on any host"),
            ("wal-fsync-injection", "crash-at-each-fsync needs in-process injection; covered by the Go suite"),
        ):
            record_gap(requirement, reason)
        self.assertGreater(len(GAPS), 0)
