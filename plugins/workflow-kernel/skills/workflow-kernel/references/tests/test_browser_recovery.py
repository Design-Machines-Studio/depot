import json
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from tests import schema_matches

from workflow_kernel.adapters.browser import (
    BrowserAttempt, BrowserLaunchEvidence, BrowserLifecycleEvidence,
    BrowserQuitEvidence, BrowserRecovery, BrowserRecoveryReceipt, BrowserRequest,
)


PROFILE_ID = "profile-sha256:" + "a" * 64
ENGINES = ("chromium", "firefox")
TARGET_URL = "https://example.invalid/page"
TARGET_URL_DIGEST = "url-sha256:" + hashlib.sha256(TARGET_URL.encode()).hexdigest()
TARGET_ORIGIN_DIGEST = "origin-sha256:" + hashlib.sha256(b"https://example.invalid").hexdigest()
TARGET_ROUTE_DIGEST = "sha256:" + hashlib.sha256(b"/page").hexdigest()
VIEWPORT = "375x812"


class FakeBrowserAdapter:
    def __init__(self, attempts, *, quit_result=None, launches=()):
        self.attempts = list(attempts)
        self.quit_result = quit_result or BrowserQuitEvidence("chromium", True, "primary-1")
        self.launches = list(launches)
        self.calls = []

    def attempt(self, request, engine):
        self.calls.append(("attempt", engine))
        result = self.attempts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def quit_engine(self, engine):
        self.calls.append(("quit_engine", engine))
        if isinstance(self.quit_result, Exception):
            raise self.quit_result
        return self.quit_result

    def launch_engine(self, engine, fresh_profile=True):
        self.calls.append(("launch_engine", engine, fresh_profile))
        result = self.launches.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def attempt(
    number, engine, result, *, session, reason="browser_tool_failure",
    detail="tool failed", proof_kind="browser", case_id="case-1",
    requested_engine="chromium", substitution=None,
):
    if engine != requested_engine and substitution is None:
        substitution = "alternate_engine_recovery"
    return BrowserAttempt(
        case_id, number, requested_engine, engine, "verify", result,
        reason if result != "passed" else None,
        detail if result != "passed" else None,
        "proof/screenshot.png", "proof/trace.zip", "proof/console.txt",
        session, proof_kind, substitution, PROFILE_ID, ENGINES,
        TARGET_URL_DIGEST, TARGET_ORIGIN_DIGEST, TARGET_ROUTE_DIGEST, VIEWPORT,
    )


class HostileException(Exception):
    def __str__(self):
        raise RuntimeError("str leaked")

    def __repr__(self):
        raise RuntimeError("repr leaked")


class BrowserRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", "firefox",
            PROFILE_ID, ENGINES, TARGET_ORIGIN_DIGEST,
        )

    def test_primary_first_pass_is_clean_without_recovery(self):
        adapter = FakeBrowserAdapter([attempt(1, "chromium", "passed", session="primary-1")])
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "clean")
        self.assertEqual(receipt.case_id, "case-1")
        self.assertEqual(receipt.requested_engine, "chromium")
        self.assertEqual(receipt.actual_engine, "chromium")
        self.assertIsNone(receipt.substitution_provenance)
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
        self.assertEqual(receipt.attempts[-1].session_id, receipt.lifecycle[-1].session_id)
        self.assertIs(receipt.lifecycle[-1].fresh_profile, True)
        self.assertEqual(adapter.calls, [
            ("attempt", "chromium"), ("quit_engine", "chromium"),
            ("launch_engine", "chromium", True), ("attempt", "chromium"),
        ])

    def test_unproved_primary_restart_records_gap_and_uses_different_engine(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "passed", session="secondary-1",
                        substitution="alternate_engine_recovery"),
            ],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "recovered")
        self.assertEqual(receipt.reason_code, "alternate_engine_recovered_degraded")
        self.assertEqual(receipt.requested_engine, "chromium")
        self.assertEqual(receipt.actual_engine, "firefox")
        self.assertEqual(receipt.substitution_provenance, "alternate_engine_recovery")
        self.assertEqual(receipt.verification_profile_id, PROFILE_ID)
        self.assertEqual(receipt.configured_engines, ENGINES)
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
        curl = attempt(1, "chromium", "passed", session="primary-1")
        object.__setattr__(curl, "proof_kind", "curl")
        adapter = FakeBrowserAdapter(
            [curl, attempt(2, "firefox", "failed", session="secondary-1")],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.attempts[0].result, "unavailable")
        self.assertEqual(receipt.attempts[0].failure_reason, "invalid_adapter_evidence")
        with self.assertRaises(ValueError):
            BrowserRequest("case", TARGET_URL, "1440x900", "chromium", "chromium",
                           PROFILE_ID, ENGINES, TARGET_ORIGIN_DIGEST)

    def test_request_rejects_engines_outside_authoritative_profile(self):
        with self.assertRaises(ValueError):
            BrowserRequest("case", TARGET_URL, VIEWPORT, "chromium", "firefox",
                           PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST)

    def test_single_engine_profile_records_secondary_unavailable_and_human_help(self):
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", None,
            PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST,
        )
        primary = replace(
            attempt(1, "chromium", "failed", session="primary-1"),
            configured_engines=("chromium",),
        )
        receipt = BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                [primary],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            ),
        )
        self.assertEqual("blocked", receipt.status)
        self.assertEqual("human_help_required", receipt.reason_code)
        self.assertIn(
            "secondary_engine_unavailable",
            [item.result for item in receipt.lifecycle],
        )

    def test_invalid_primary_launch_is_not_recorded_as_successful(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "passed", session="secondary-1"),
            ],
            launches=[
                BrowserLaunchEvidence("chromium", True, True, "primary-1"),
                BrowserLaunchEvidence("firefox", True, True, "secondary-1"),
            ],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual("alternate_engine_recovered_degraded", receipt.reason_code)
        self.assertIn("session_identity_mismatch", [item.result for item in receipt.lifecycle])
        self.assertFalse(any(
            item.action == "browser_process_launch"
            and item.actual_engine == "chromium"
            and item.result == "launched"
            for item in receipt.lifecycle
        ))

    def test_nonfresh_launch_is_normalized_and_cannot_recover(self):
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", None,
            PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST,
        )
        primary = replace(
            attempt(1, "chromium", "failed", session="primary-1"),
            configured_engines=("chromium",),
        )
        receipt = BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                [primary],
                launches=[BrowserLaunchEvidence("chromium", True, False, "primary-2")],
            ),
        )
        self.assertEqual("blocked", receipt.status)
        self.assertIn("fresh_profile_unavailable", [item.result for item in receipt.lifecycle])
        self.assertFalse(any(item.result == "launched" for item in receipt.lifecycle))

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

    def test_restart_proof_binds_quit_launch_and_retry_to_exact_sessions(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "passed", session="secondary-1",
                        substitution="alternate_engine_recovery"),
            ],
            quit_result=BrowserQuitEvidence("chromium", True, "unrelated-session"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.reason_code, "alternate_engine_recovered_degraded")
        self.assertNotIn(("launch_engine", "chromium", True), adapter.calls)
        self.assertIn("primary_restart_unavailable", [item.result for item in receipt.lifecycle])

        wrong_retry = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "chromium", "passed", session="primary-1"),
                attempt(3, "firefox", "passed", session="secondary-1",
                        substitution="alternate_engine_recovery"),
            ],
            launches=[
                BrowserLaunchEvidence("chromium", True, True, "primary-2"),
                BrowserLaunchEvidence("firefox", True, True, "secondary-1"),
            ],
        )
        receipt = BrowserRecovery().run(self.request, wrong_retry)
        self.assertEqual(receipt.actual_engine, "firefox")
        self.assertEqual(receipt.attempts[1].reason_code, "session_identity_mismatch")

    def test_adapter_exceptions_are_redacted_and_recovery_reaches_human_help(self):
        secret = "https://member:sk-secret@example.invalid/path?token=raw" + "x" * 70_000
        adapter = FakeBrowserAdapter(
            [RuntimeError(secret)],
            quit_result=RuntimeError(secret),
            launches=[RuntimeError(secret)],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        serialized = json.dumps(receipt.to_dict(), sort_keys=True)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.reason_code, "human_help_required")
        self.assertEqual(receipt.missing_case_ids, ("case-1",))
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("example.invalid", serialized)
        self.assertIn("value-sha256:", serialized)
        self.assertLess(len(serialized), 8_000)
        self.assertEqual(adapter.calls, [
            ("attempt", "chromium"), ("quit_engine", "chromium"),
            ("launch_engine", "firefox", True),
        ])

    def test_hostile_exception_rendering_cannot_abort_any_adapter_boundary(self):
        for boundary in ("attempt", "quit", "launch"):
            with self.subTest(boundary=boundary):
                attempts = [HostileException()] if boundary == "attempt" else [
                    attempt(1, "chromium", "failed", session="primary-1")
                ]
                quit_result = HostileException() if boundary == "quit" else BrowserQuitEvidence(
                    "chromium", False, "primary-1"
                )
                launches = [HostileException()]
                adapter = FakeBrowserAdapter(
                    attempts, quit_result=quit_result, launches=launches,
                )
                receipt = BrowserRecovery().run(self.request, adapter)
                self.assertEqual(receipt.status, "blocked")
                self.assertIn(
                    "value-sha256:" + hashlib.sha256(
                        b"unrenderable-adapter-exception"
                    ).hexdigest(),
                    json.dumps(receipt.to_dict()),
                )

    def test_request_rejects_secret_bearing_target_without_persisting_it(self):
        secret_url = "https://member:password@example.invalid/private?token=secret"
        with self.assertRaises(ValueError):
            BrowserRequest(
                "case-1", secret_url, VIEWPORT, "chromium", "firefox",
                PROFILE_ID, ENGINES, TARGET_ORIGIN_DIGEST,
            )

    def test_request_rejects_url_from_wrong_authoritative_origin(self):
        wrong = "https://wrong-environment.invalid/page"
        with self.assertRaises(ValueError):
            BrowserRequest(
                "case-1", wrong, VIEWPORT, "chromium", "firefox",
                PROFILE_ID, ENGINES, TARGET_ORIGIN_DIGEST,
            )

    def test_run_reconstructs_and_rejects_mutated_request_before_adapter_calls(self):
        for field, value in (
            ("url", "https://example.invalid/mutated-route"),
            ("target_origin_digest", "origin-sha256:" + "b" * 64),
        ):
            with self.subTest(field=field):
                request = BrowserRequest(
                    "case-1", TARGET_URL, VIEWPORT, "chromium", "firefox",
                    PROFILE_ID, ENGINES, TARGET_ORIGIN_DIGEST,
                )
                object.__setattr__(request, field, value)
                adapter = FakeBrowserAdapter([
                    attempt(1, "chromium", "passed", session="primary-1"),
                ])
                with self.assertRaises(ValueError):
                    BrowserRecovery().run(request, adapter)
                self.assertEqual([], adapter.calls)

    def test_direct_attempt_and_lifecycle_reason_categories_match_schema(self):
        base = attempt(1, "chromium", "passed", session="primary-1")
        with self.assertRaises(ValueError):
            replace(base, proof_kind="curl")
        with self.assertRaises(ValueError):
            replace(
                base, result="failed", reason_code="fresh_profile_unavailable",
            )
        with self.assertRaises(ValueError):
            BrowserLifecycleEvidence(
                "case-1", "chromium", "chromium", "session_validation",
                "session_identity_mismatch", "primary-1", "primary-1",
            )
        clean = BrowserRecovery().run(
            self.request, FakeBrowserAdapter([base]),
        )
        object.__setattr__(base, "proof_kind", "curl")
        with self.assertRaises(ValueError):
            replace(clean, attempts=(base,))

    def test_single_engine_clean_and_primary_recovered_receipts_match_schema(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", None,
            PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST,
        )
        clean = BrowserRecovery().run(
            request,
            FakeBrowserAdapter([
                replace(
                    attempt(1, "chromium", "passed", session="primary-1"),
                    configured_engines=("chromium",),
                ),
            ]),
        )
        recovered = BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                [
                    replace(
                        attempt(1, "chromium", "failed", session="primary-1"),
                        configured_engines=("chromium",),
                    ),
                    replace(
                        attempt(2, "chromium", "passed", session="primary-2"),
                        configured_engines=("chromium",),
                    ),
                ],
                launches=[BrowserLaunchEvidence("chromium", True, True, "primary-2")],
            ),
        )
        self.assertTrue(schema_matches(clean.to_dict(), schema))
        self.assertTrue(schema_matches(recovered.to_dict(), schema))

    def test_receipt_rejects_successful_launch_without_following_attempt(self):
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", None,
            PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST,
        )
        initial = replace(
            attempt(1, "chromium", "failed", session="primary-1"),
            configured_engines=("chromium",),
        )
        base = BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                [initial],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            ),
        )
        lifecycle = (
            BrowserLifecycleEvidence(
                "case-1", "chromium", "chromium", "browser_process_quit",
                "confirmed", "primary-1", "primary-1",
            ),
            BrowserLifecycleEvidence(
                "case-1", "chromium", "chromium", "browser_process_launch",
                "launched", "primary-2", "primary-1", fresh_profile=True,
            ),
            BrowserLifecycleEvidence(
                "case-1", "chromium", "chromium", "secondary_engine",
                "secondary_engine_unavailable", "primary-1", "primary-1",
                "secondary_engine_unavailable",
            ),
        )
        with self.assertRaises(ValueError):
            replace(base, lifecycle=lifecycle)

    def test_runtime_receipt_rejects_cross_field_and_session_chain_contradictions(self):
        adapter = FakeBrowserAdapter([attempt(1, "chromium", "passed", session="primary-1")])
        clean = BrowserRecovery().run(self.request, adapter)
        invalid_updates = (
            {"schema_version": True},
            {"status": "blocked", "reason_code": "human_help_required"},
            {"reason_code": "human_help_required"},
            {"actual_engine": "firefox"},
            {"missing_case_ids": ("case-1",)},
        )
        for update in invalid_updates:
            with self.subTest(update=update), self.assertRaises(ValueError):
                replace(clean, **update)
        with self.assertRaises(ValueError):
            BrowserLifecycleEvidence(
                "case-1", "chromium", "chromium", "browser_process_quit",
                "launched", "primary-1",
            )
        with self.assertRaises(ValueError):
            replace(clean, attempts=(replace(clean.attempts[0], attempt_number=2),))

        recovered = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [
                    attempt(1, "chromium", "failed", session="primary-1"),
                    attempt(2, "chromium", "passed", session="primary-2"),
                ],
                launches=[BrowserLaunchEvidence("chromium", True, True, "primary-2")],
            ),
        )
        with self.assertRaises(ValueError):
            replace(recovered, lifecycle=recovered.lifecycle[1:])
        wrong_engine_launch = replace(
            recovered.lifecycle[-1], actual_engine="firefox",
            substitution_provenance="alternate_engine_recovery",
        )
        with self.assertRaises(ValueError):
            replace(recovered, lifecycle=(recovered.lifecycle[0], wrong_engine_launch))

    def test_runtime_receipt_matches_strict_schema_and_empty_evidence_does_not(self):
        adapter = FakeBrowserAdapter(
            [attempt(1, "chromium", "passed", session="primary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter).to_dict()
        schema_path = Path(__file__).parents[1] / "browser-recovery-schema.json"
        schema = json.loads(schema_path.read_text())
        self.assertTrue(schema_matches(receipt, schema))
        invalid = dict(receipt, attempts=[{}])
        self.assertFalse(schema_matches(invalid, schema))
        invalid = dict(receipt, lifecycle=[{}])
        self.assertFalse(schema_matches(invalid, schema))
        for update in (
            {"schema_version": True},
            {"status": "blocked", "reason_code": "human_help_required"},
            {"reason_code": "human_help_required"},
            {"actual_engine": "firefox"},
            {"missing_case_ids": ["case-1"]},
        ):
            invalid = dict(receipt, **update)
            self.assertFalse(schema_matches(invalid, schema), update)
        passed_with_failure = dict(receipt)
        passed_with_failure["attempts"] = [
            dict(receipt["attempts"][0], reason_code="browser_tool_failure")
        ]
        self.assertFalse(schema_matches(passed_with_failure, schema))
        wrong_order = dict(receipt)
        wrong_order["attempts"] = [dict(receipt["attempts"][0], attempt_number=2)]
        self.assertFalse(schema_matches(wrong_order, schema))

        recovered = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [
                    attempt(1, "chromium", "failed", session="primary-1"),
                    attempt(2, "chromium", "passed", session="primary-2"),
                ],
                launches=[BrowserLaunchEvidence("chromium", True, True, "primary-2")],
            ),
        ).to_dict()
        recovered["lifecycle"][0]["result"] = "launched"
        self.assertFalse(schema_matches(recovered, schema))


if __name__ == "__main__":
    unittest.main()
