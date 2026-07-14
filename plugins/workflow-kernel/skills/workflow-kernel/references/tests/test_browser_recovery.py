import unittest

from workflow_kernel.adapters.browser import (
    BrowserAttempt, BrowserLaunchEvidence, BrowserQuitEvidence, BrowserRecovery,
    BrowserRequest,
)


class FakeBrowserAdapter:
    def __init__(self, attempts, *, quit_result=None, launches=()):
        self.attempts = list(attempts)
        self.quit_result = quit_result or BrowserQuitEvidence("chromium", True, "primary-1")
        self.launches = list(launches)
        self.calls = []

    def attempt(self, request, engine):
        self.calls.append(("attempt", engine))
        return self.attempts.pop(0)

    def quit_engine(self, engine):
        self.calls.append(("quit_engine", engine))
        return self.quit_result

    def launch_engine(self, engine, fresh_profile=True):
        self.calls.append(("launch_engine", engine, fresh_profile))
        return self.launches.pop(0)


def attempt(number, engine, result, *, session, reason="tool_failure", proof_kind="browser"):
    return BrowserAttempt(
        number, engine, "verify", result, reason if result != "passed" else None,
        "proof/screenshot.png", "proof/trace.zip", "proof/console.txt",
        session, proof_kind,
    )


class BrowserRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.request = BrowserRequest(
            "case-1", "https://example.invalid/page", "375x812",
            "chromium", "firefox",
        )

    def test_primary_first_pass_is_clean_without_recovery(self):
        adapter = FakeBrowserAdapter([attempt(1, "chromium", "passed", session="primary-1")])
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "clean")
        self.assertEqual(adapter.calls, [("attempt", "chromium")])

    def test_failure_is_preserved_then_primary_process_quit_fresh_launch_and_retry(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "chromium", "passed", session="primary-2"),
            ],
            launches=[BrowserLaunchEvidence("chromium", True, True, "primary-2")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "recovered")
        self.assertEqual(receipt.reason_code, "primary_recovered_degraded")
        self.assertEqual([item.result for item in receipt.attempts], ["failed", "passed"])
        self.assertEqual(adapter.calls, [
            ("attempt", "chromium"), ("quit_engine", "chromium"),
            ("launch_engine", "chromium", True), ("attempt", "chromium"),
        ])

    def test_unproved_primary_restart_records_gap_and_uses_different_engine(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "passed", session="secondary-1"),
            ],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "recovered")
        self.assertEqual(receipt.reason_code, "alternate_engine_recovered_degraded")
        self.assertIn("primary_restart_unavailable", [item.result for item in receipt.lifecycle])
        self.assertEqual(adapter.calls[-2:], [("launch_engine", "firefox", True), ("attempt", "firefox")])

    def test_exhausted_secondary_blocks_for_human_with_exact_missing_case(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "chromium", "failed", session="primary-2"),
                attempt(3, "firefox", "failed", session="secondary-1"),
            ],
            launches=[
                BrowserLaunchEvidence("chromium", True, True, "primary-2"),
                BrowserLaunchEvidence("firefox", True, True, "secondary-1"),
            ],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.reason_code, "human_help_required")
        self.assertEqual(receipt.missing_case_ids, ("case-1",))
        self.assertEqual([item.engine for item in receipt.attempts], ["chromium", "chromium", "firefox"])

    def test_curl_and_same_engine_alias_cannot_satisfy_browser_proof(self):
        curl = attempt(1, "chromium", "passed", session="primary-1", proof_kind="curl")
        adapter = FakeBrowserAdapter(
            [curl, attempt(2, "firefox", "failed", session="secondary-1")],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.attempts[0].result, "failed")
        self.assertEqual(receipt.attempts[0].failure_reason, "curl_not_browser_evidence")
        with self.assertRaises(ValueError):
            BrowserRequest("case", "/", "1440x900", "chromium", "chromium")

    def test_app_restart_is_distinct_diagnostic_not_browser_relaunch(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "failed", session="secondary-1"),
            ],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1", action="application_restart"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertIn("application_restart", [item.action for item in receipt.lifecycle])
        self.assertIn("primary_restart_unavailable", [item.result for item in receipt.lifecycle])


if __name__ == "__main__":
    unittest.main()
