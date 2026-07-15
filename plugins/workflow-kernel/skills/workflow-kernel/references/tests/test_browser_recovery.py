import json
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from tests import schema_matches

from workflow_kernel.adapters.browser import (
    BrowserAttempt, BrowserLaunchEvidence, BrowserLifecycleEvidence,
    BrowserQuitEvidence, BrowserReadinessEvidence, BrowserRecovery,
    BrowserRecoveryReceipt, BrowserRequest,
    snapshot_browser_recovery_receipt, snapshot_browser_request,
)


PROFILE_ID = "profile-sha256:" + "a" * 64
ENGINES = ("chromium", "firefox")
ALTERNATE_ENGINE_PAIRS = (
    ("chromium", "firefox"),
    ("chromium", "webkit"),
    ("firefox", "chromium"),
    ("firefox", "webkit"),
    ("webkit", "chromium"),
    ("webkit", "firefox"),
)
PRIMARY_RECOVERY_PATHS = (
    "quit_unconfirmed",
    "quit_unavailable",
    "application_restart_confirmed",
    "application_restart_unconfirmed",
    "primary_launch_unavailable",
    "primary_launch_unfresh",
    "primary_launch_session_validation",
    "restart_proved",
)
ALTERNATE_TERMINAL_PATHS = (
    "launched",
    "launch_unavailable",
    "launch_unfresh",
    "session_validation",
)
TARGET_URL = "https://example.invalid/page"
TARGET_URL_DIGEST = "url-sha256:" + hashlib.sha256(TARGET_URL.encode()).hexdigest()
TARGET_ORIGIN_DIGEST = "origin-sha256:" + hashlib.sha256(b"https://example.invalid").hexdigest()
TARGET_ROUTE_DIGEST = "sha256:" + hashlib.sha256(b"/page").hexdigest()
VIEWPORT = "375x812"


class FakeBrowserAdapter:
    def __init__(self, attempts, *, quit_result=None, launches=(), readiness=None):
        self.attempts = list(attempts)
        self.quit_result = quit_result or BrowserQuitEvidence("chromium", True, "primary-1")
        self.launches = list(launches)
        self.readiness = readiness
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

    def recheck_readiness(self, request, previous_session_id):
        self.calls.append(("recheck_readiness", previous_session_id))
        if isinstance(self.readiness, Exception):
            raise self.readiness
        if self.readiness is not None:
            return self.readiness
        return BrowserReadinessEvidence(
            request.case_id, previous_session_id, request.target_url_digest,
            request.target_origin_digest, True, True, True,
        )


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

    def blocked_with_unavailable_readiness(self):
        unavailable = BrowserReadinessEvidence(
            "case-1", "primary-1", TARGET_URL_DIGEST, TARGET_ORIGIN_DIGEST,
            False, True, True, "dev_server_unavailable",
        )
        return BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [attempt(1, "chromium", "failed", session="primary-1")],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
                launches=[RuntimeError("alternate unavailable")],
                readiness=unavailable,
            ),
        )

    def recovered_on_alternate(self, primary, alternate):
        return self.paired_receipt(
            primary, alternate, "quit_unconfirmed", "launched", "passed",
        )

    def profiled_attempt(
        self, number, primary, engines, actual, result, session,
        reason="browser_tool_failure",
    ):
        return BrowserAttempt(
            "case-1", number, primary, actual, "verify", result,
            None if result == "passed" else reason,
            None if result == "passed" else "tool failed",
            "proof/screenshot.png", "proof/trace.zip", "proof/console.txt",
            session, "browser",
            "alternate_engine_recovery" if actual != primary else None,
            PROFILE_ID, engines, TARGET_URL_DIGEST, TARGET_ORIGIN_DIGEST,
            TARGET_ROUTE_DIGEST, VIEWPORT,
        )

    def paired_attempt(
        self, number, primary, alternate, actual, result, session,
        reason="browser_tool_failure",
    ):
        return self.profiled_attempt(
            number, primary, (primary, alternate), actual, result, session, reason,
        )

    def paired_receipt(
        self, primary, alternate, primary_path, alternate_path,
        alternate_result=None, readiness="confirmed", *,
        initial_reason="browser_tool_failure",
        primary_retry_reason="browser_tool_failure",
        alternate_reason="browser_tool_failure",
    ):
        engines = (primary, alternate)
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, primary, alternate,
            PROFILE_ID, engines, TARGET_ORIGIN_DIGEST,
        )
        attempts = [
            self.paired_attempt(
                1, primary, alternate, primary, "failed", "primary-1",
                initial_reason,
            )
        ]
        launches = []
        current_primary_session = "primary-1"
        if primary_path == "quit_unconfirmed":
            quit_result = BrowserQuitEvidence(primary, False, "primary-1")
        elif primary_path == "quit_unavailable":
            quit_result = RuntimeError("quit unavailable")
        elif primary_path.startswith("application_restart_"):
            quit_result = BrowserQuitEvidence(
                primary, primary_path == "application_restart_confirmed", "primary-1",
                action="application_restart",
            )
        else:
            quit_result = BrowserQuitEvidence(primary, True, "primary-1")
            if primary_path == "restart_proved":
                current_primary_session = "primary-2"
                launches.append(BrowserLaunchEvidence(
                    primary, True, True, current_primary_session,
                ))
                attempts.append(self.paired_attempt(
                    2, primary, alternate, primary, "failed",
                    current_primary_session, primary_retry_reason,
                ))
            elif primary_path == "primary_launch_unavailable":
                launches.append(BrowserLaunchEvidence(
                    primary, False, True, "unavailable-primary",
                ))
            elif primary_path == "primary_launch_unfresh":
                launches.append(BrowserLaunchEvidence(
                    primary, True, False, "unfresh-primary",
                ))
            else:
                launches.append(BrowserLaunchEvidence(
                    primary, True, True, "primary-1",
                ))

        if alternate_path == "launched":
            launches.append(BrowserLaunchEvidence(
                alternate, True, True, "secondary-1",
            ))
            attempts.append(self.paired_attempt(
                len(attempts) + 1, primary, alternate, alternate,
                alternate_result, "secondary-1", alternate_reason,
            ))
        elif alternate_path == "launch_unavailable":
            launches.append(BrowserLaunchEvidence(
                alternate, False, True, "unavailable-secondary",
            ))
        elif alternate_path == "launch_unfresh":
            launches.append(BrowserLaunchEvidence(
                alternate, True, False, "unfresh-secondary",
            ))
        else:
            launches.append(BrowserLaunchEvidence(
                alternate, True, True, current_primary_session,
            ))

        readiness_evidence = None
        if readiness == "unavailable":
            readiness_evidence = BrowserReadinessEvidence(
                "case-1", current_primary_session, TARGET_URL_DIGEST,
                TARGET_ORIGIN_DIGEST, False, True, True,
                "dev_server_unavailable",
            )
        return BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                attempts, quit_result=quit_result, launches=launches,
                readiness=readiness_evidence,
            ),
        )

    def single_engine_receipt(
        self, primary, primary_path, *,
        initial_reason="browser_tool_failure",
        primary_retry_reason="browser_tool_failure",
    ):
        engines = (primary,)
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, primary, None,
            PROFILE_ID, engines, TARGET_ORIGIN_DIGEST,
        )
        attempts = [self.profiled_attempt(
            1, primary, engines, primary, "failed", "primary-1", initial_reason,
        )]
        launches = []
        if primary_path == "quit_unconfirmed":
            quit_result = BrowserQuitEvidence(primary, False, "primary-1")
        elif primary_path == "quit_unavailable":
            quit_result = RuntimeError("quit unavailable")
        elif primary_path.startswith("application_restart_"):
            quit_result = BrowserQuitEvidence(
                primary, primary_path == "application_restart_confirmed", "primary-1",
                action="application_restart",
            )
        else:
            quit_result = BrowserQuitEvidence(primary, True, "primary-1")
            if primary_path == "restart_proved":
                launches.append(BrowserLaunchEvidence(
                    primary, True, True, "primary-2",
                ))
                attempts.append(self.profiled_attempt(
                    2, primary, engines, primary, "failed", "primary-2",
                    primary_retry_reason,
                ))
            elif primary_path == "primary_launch_unavailable":
                launches.append(BrowserLaunchEvidence(
                    primary, False, True, "unavailable-primary",
                ))
            elif primary_path == "primary_launch_unfresh":
                launches.append(BrowserLaunchEvidence(
                    primary, True, False, "unfresh-primary",
                ))
            else:
                launches.append(BrowserLaunchEvidence(
                    primary, True, True, "primary-1",
                ))
        return BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                attempts, quit_result=quit_result, launches=launches,
            ),
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

    def test_application_failure_is_terminal_and_never_recovered(self):
        adapter = FakeBrowserAdapter([
            attempt(1, "chromium", "failed", session="primary-1",
                    reason="application_failure"),
        ])
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.reason_code, "application_failure")
        self.assertEqual(receipt.missing_case_ids, ("case-1",))
        self.assertEqual(adapter.calls, [("attempt", "chromium")])

    def test_unavailable_readiness_is_diagnostic_and_alternate_still_runs(self):
        unavailable = BrowserReadinessEvidence(
            "case-1", "primary-1", TARGET_URL_DIGEST, TARGET_ORIGIN_DIGEST,
            True, False, True, "target_url_unavailable",
        )
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "failed", session="secondary-1"),
            ],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
            readiness=unavailable,
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.reason_code, "human_help_required")
        readiness = next(
            item for item in receipt.lifecycle
            if item.action == "readiness_recheck"
        )
        self.assertEqual(readiness.result, "unavailable")
        self.assertEqual(
            readiness.readiness_checks,
            ("confirmed", "unavailable", "confirmed"),
        )
        self.assertEqual(receipt.attempts[-1].actual_engine, "firefox")
        self.assertEqual(adapter.calls[-2:], [
            ("launch_engine", "firefox", True), ("attempt", "firefox"),
        ])

    def test_unavailable_readiness_still_records_alternate_launch_unavailable(self):
        receipt = self.blocked_with_unavailable_readiness()
        self.assertEqual(receipt.reason_code, "human_help_required")
        self.assertEqual(receipt.lifecycle[-2].action, "readiness_recheck")
        self.assertEqual(receipt.lifecycle[-1].action, "browser_process_launch")
        self.assertEqual(receipt.lifecycle[-1].result, "unavailable")
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        self.assertTrue(schema_matches(receipt.to_dict(), schema))
        truncated = receipt.to_dict()
        truncated["lifecycle"] = truncated["lifecycle"][:-1]
        self.assertFalse(schema_matches(truncated, schema))

    def test_schema_rejects_multi_engine_human_help_without_readiness(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        payload = self.blocked_with_unavailable_readiness().to_dict()
        payload["lifecycle"] = [
            item for item in payload["lifecycle"]
            if item["action"] != "readiness_recheck"
        ]
        self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_same_engine_alternate_evidence(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        payload = self.blocked_with_unavailable_readiness().to_dict()
        payload["lifecycle"][-1]["actual_engine"] = payload["requested_engine"]
        self.assertFalse(schema_matches(payload, schema))

    def test_schema_accepts_runtime_alternate_recovery_for_each_primary(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(primary=primary, alternate=alternate):
                receipt = self.recovered_on_alternate(primary, alternate)
                self.assertEqual(
                    receipt.reason_code, "alternate_engine_recovered_degraded",
                )
                self.assertTrue(schema_matches(receipt.to_dict(), schema))

    def test_schema_rejects_recovered_receipt_without_readiness(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(primary=primary, alternate=alternate):
                payload = self.recovered_on_alternate(primary, alternate).to_dict()
                payload["lifecycle"] = [
                    item for item in payload["lifecycle"]
                    if item["action"] != "readiness_recheck"
                ]
                self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_recovered_same_engine_alternate_evidence(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(primary=primary, alternate=alternate):
                payload = self.recovered_on_alternate(primary, alternate).to_dict()
                payload["lifecycle"][-1]["actual_engine"] = primary
                self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_recovered_same_engine_passing_attempt(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(primary=primary, alternate=alternate):
                payload = self.recovered_on_alternate(primary, alternate).to_dict()
                payload["attempts"][-1]["actual_engine"] = primary
                self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_recovered_same_engine_receipt(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(primary=primary, alternate=alternate):
                payload = self.recovered_on_alternate(primary, alternate).to_dict()
                payload["actual_engine"] = primary
                self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_mismatched_recovered_engine_pair(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            mismatched = next(
                engine for engine in ("chromium", "firefox", "webkit")
                if engine not in (primary, alternate)
            )
            for component in ("lifecycle", "attempt", "receipt"):
                with self.subTest(
                    primary=primary, alternate=alternate, component=component,
                ):
                    payload = self.recovered_on_alternate(
                        primary, alternate,
                    ).to_dict()
                    if component == "lifecycle":
                        payload["lifecycle"][-1]["actual_engine"] = mismatched
                    elif component == "attempt":
                        payload["attempts"][-1]["actual_engine"] = mismatched
                    else:
                        payload["actual_engine"] = mismatched
                    self.assertFalse(schema_matches(payload, schema))

    def test_schema_accepts_every_runtime_recovered_alternate_shape(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            for primary_path in PRIMARY_RECOVERY_PATHS:
                for readiness in ("confirmed", "unavailable"):
                    with self.subTest(
                        primary=primary, alternate=alternate,
                        primary_path=primary_path, readiness=readiness,
                    ):
                        receipt = self.paired_receipt(
                            primary, alternate, primary_path, "launched", "passed",
                            readiness,
                        )
                        self.assertEqual(
                            "alternate_engine_recovered_degraded",
                            receipt.reason_code,
                        )
                        self.assertTrue(schema_matches(receipt.to_dict(), schema))

    def test_schema_accepts_every_runtime_blocked_multi_engine_shape(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            for primary_path in PRIMARY_RECOVERY_PATHS:
                for alternate_path in ALTERNATE_TERMINAL_PATHS:
                    for readiness in ("confirmed", "unavailable"):
                        with self.subTest(
                            primary=primary, alternate=alternate,
                            primary_path=primary_path,
                            alternate_path=alternate_path,
                            readiness=readiness,
                        ):
                            receipt = self.paired_receipt(
                                primary, alternate, primary_path, alternate_path,
                                "failed" if alternate_path == "launched" else None,
                                readiness,
                            )
                            self.assertEqual("human_help_required", receipt.reason_code)
                            self.assertTrue(schema_matches(receipt.to_dict(), schema))

    def test_schema_rejects_recovered_alternate_lifecycle_grammar_forgeries(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            for primary_path in PRIMARY_RECOVERY_PATHS:
                receipt = self.paired_receipt(
                    primary, alternate, primary_path, "launched", "passed",
                )
                for mutation in (
                    "duplicate", "decoy", "reordered", "extra", "unconfigured",
                ):
                    with self.subTest(
                        primary=primary, alternate=alternate,
                        primary_path=primary_path, mutation=mutation,
                    ):
                        payload = receipt.to_dict()
                        if mutation == "duplicate":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                        elif mutation == "decoy":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                            payload["lifecycle"][-1]["actual_engine"] = primary
                            payload["lifecycle"][-1]["substitution_provenance"] = None
                        elif mutation == "reordered":
                            payload["lifecycle"][-2:] = reversed(payload["lifecycle"][-2:])
                        elif mutation == "extra":
                            payload["lifecycle"].append(dict(payload["lifecycle"][0]))
                        else:
                            third = next(
                                engine for engine in ("chromium", "firefox", "webkit")
                                if engine not in (primary, alternate)
                            )
                            payload["configured_engines"] = [primary, third]
                            for attempt_payload in payload["attempts"]:
                                attempt_payload["configured_engines"] = [primary, third]
                        self.assertFalse(schema_matches(payload, schema))

    def test_schema_rejects_blocked_multi_engine_pair_and_grammar_forgeries(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            third = next(
                engine for engine in ("chromium", "firefox", "webkit")
                if engine not in (primary, alternate)
            )
            for primary_path in PRIMARY_RECOVERY_PATHS:
                receipt = self.paired_receipt(
                    primary, alternate, primary_path, "launched", "failed",
                )
                for mutation in (
                    "missing", "same_primary", "unconfigured_third",
                    "mismatched_pair", "configured_pair", "duplicate", "decoy",
                    "reordered", "extra",
                ):
                    with self.subTest(
                        primary=primary, alternate=alternate,
                        primary_path=primary_path, mutation=mutation,
                    ):
                        payload = receipt.to_dict()
                        if mutation == "missing":
                            del payload["lifecycle"][-2]
                        elif mutation == "same_primary":
                            payload["lifecycle"][-1]["actual_engine"] = primary
                            payload["lifecycle"][-1]["substitution_provenance"] = None
                        elif mutation == "unconfigured_third":
                            payload["lifecycle"][-1]["actual_engine"] = third
                        elif mutation == "mismatched_pair":
                            payload["lifecycle"][-1]["actual_engine"] = third
                            payload["attempts"][-1]["actual_engine"] = third
                            payload["actual_engine"] = third
                        elif mutation == "configured_pair":
                            payload["configured_engines"] = [primary, third]
                            for attempt_payload in payload["attempts"]:
                                attempt_payload["configured_engines"] = [primary, third]
                        elif mutation == "duplicate":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                        elif mutation == "decoy":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                            payload["lifecycle"][-1]["actual_engine"] = third
                        elif mutation == "reordered":
                            payload["lifecycle"][-2:] = reversed(payload["lifecycle"][-2:])
                        else:
                            payload["lifecycle"].append(dict(payload["lifecycle"][0]))
                        self.assertFalse(schema_matches(payload, schema))

    def test_schema_accepts_every_runtime_single_engine_human_help_shape(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary in ("chromium", "firefox", "webkit"):
            for primary_path in PRIMARY_RECOVERY_PATHS:
                with self.subTest(primary=primary, primary_path=primary_path):
                    receipt = self.single_engine_receipt(primary, primary_path)
                    self.assertEqual("human_help_required", receipt.reason_code)
                    self.assertTrue(schema_matches(receipt.to_dict(), schema))

    def test_schema_rejects_single_engine_lifecycle_grammar_forgeries(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary in ("chromium", "firefox", "webkit"):
            for primary_path in PRIMARY_RECOVERY_PATHS:
                receipt = self.single_engine_receipt(primary, primary_path)
                for mutation in ("duplicate", "decoy", "reordered", "extra"):
                    with self.subTest(
                        primary=primary, primary_path=primary_path,
                        mutation=mutation,
                    ):
                        payload = receipt.to_dict()
                        if mutation == "duplicate":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                        elif mutation == "decoy":
                            payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                            payload["lifecycle"][-1] = dict(payload["lifecycle"][0])
                        elif mutation == "reordered":
                            payload["lifecycle"][-2:] = reversed(payload["lifecycle"][-2:])
                        else:
                            payload["lifecycle"].append(dict(payload["lifecycle"][0]))
                        self.assertFalse(schema_matches(payload, schema))

    def test_schema_accepts_every_runtime_application_failure_terminal(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary in ("chromium", "firefox", "webkit"):
            with self.subTest(branch="initial-single", primary=primary):
                receipt = self.single_engine_receipt(
                    primary, "quit_unconfirmed", initial_reason="application_failure",
                )
                self.assertEqual("application_failure", receipt.reason_code)
                self.assertTrue(schema_matches(receipt.to_dict(), schema))
            with self.subTest(branch="primary-single", primary=primary):
                receipt = self.single_engine_receipt(
                    primary, "restart_proved",
                    primary_retry_reason="application_failure",
                )
                self.assertEqual("application_failure", receipt.reason_code)
                self.assertTrue(schema_matches(receipt.to_dict(), schema))
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            with self.subTest(branch="initial-pair", primary=primary, alternate=alternate):
                receipt = self.paired_receipt(
                    primary, alternate, "quit_unconfirmed", "launched", "failed",
                    initial_reason="application_failure",
                )
                self.assertEqual("application_failure", receipt.reason_code)
                self.assertTrue(schema_matches(receipt.to_dict(), schema))
            with self.subTest(branch="primary-pair", primary=primary, alternate=alternate):
                receipt = self.paired_receipt(
                    primary, alternate, "restart_proved", "launched", "failed",
                    primary_retry_reason="application_failure",
                )
                self.assertEqual("application_failure", receipt.reason_code)
                self.assertTrue(schema_matches(receipt.to_dict(), schema))
            for primary_path in PRIMARY_RECOVERY_PATHS:
                for readiness in ("confirmed", "unavailable"):
                    with self.subTest(
                        branch="alternate", primary=primary, alternate=alternate,
                        primary_path=primary_path, readiness=readiness,
                    ):
                        receipt = self.paired_receipt(
                            primary, alternate, primary_path, "launched", "failed",
                            readiness, alternate_reason="application_failure",
                        )
                        self.assertEqual("application_failure", receipt.reason_code)
                        self.assertTrue(schema_matches(receipt.to_dict(), schema))

    def test_schema_rejects_application_failure_terminal_forgeries(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "browser-recovery-schema.json").read_text()
        )
        for primary, alternate in ALTERNATE_ENGINE_PAIRS:
            third = next(
                engine for engine in ("chromium", "firefox", "webkit")
                if engine not in (primary, alternate)
            )
            initial = self.paired_receipt(
                primary, alternate, "quit_unconfirmed", "launched", "failed",
                initial_reason="application_failure",
            )
            donor = self.paired_receipt(
                primary, alternate, "quit_unconfirmed", "launched", "failed",
                alternate_reason="application_failure",
            )
            for mutation in ("appended_lifecycle", "duplicate_attempt", "mismatched_receipt"):
                with self.subTest(
                    branch="initial", primary=primary, alternate=alternate,
                    mutation=mutation,
                ):
                    payload = initial.to_dict()
                    if mutation == "appended_lifecycle":
                        payload["lifecycle"].append(dict(donor.to_dict()["lifecycle"][0]))
                    elif mutation == "duplicate_attempt":
                        duplicate = dict(payload["attempts"][0])
                        duplicate["attempt_number"] = 2
                        payload["attempts"].append(duplicate)
                    else:
                        payload["actual_engine"] = alternate
                    self.assertFalse(schema_matches(payload, schema))

            primary_terminal = self.paired_receipt(
                primary, alternate, "restart_proved", "launched", "failed",
                primary_retry_reason="application_failure",
            )
            for mutation in (
                "appended", "duplicate", "reordered",
                "mismatched_attempt", "mismatched_receipt",
            ):
                with self.subTest(
                    branch="primary", primary=primary, alternate=alternate,
                    mutation=mutation,
                ):
                    payload = primary_terminal.to_dict()
                    if mutation == "appended":
                        payload["lifecycle"].append(dict(payload["lifecycle"][0]))
                    elif mutation == "duplicate":
                        payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                    elif mutation == "reordered":
                        payload["lifecycle"] = list(reversed(payload["lifecycle"]))
                    elif mutation == "mismatched_attempt":
                        payload["attempts"][-1]["actual_engine"] = alternate
                        payload["attempts"][-1]["substitution_provenance"] = (
                            "alternate_engine_recovery"
                        )
                    else:
                        payload["actual_engine"] = alternate
                    self.assertFalse(schema_matches(payload, schema))

            alternate_terminal = donor
            for mutation in (
                "appended", "duplicate", "reordered", "mismatched_lifecycle",
                "mismatched_attempt", "mismatched_receipt", "configured_pair",
            ):
                with self.subTest(
                    branch="alternate", primary=primary, alternate=alternate,
                    mutation=mutation,
                ):
                    payload = alternate_terminal.to_dict()
                    if mutation == "appended":
                        payload["lifecycle"].append(dict(payload["lifecycle"][0]))
                    elif mutation == "duplicate":
                        payload["lifecycle"].insert(-1, dict(payload["lifecycle"][-1]))
                    elif mutation == "reordered":
                        payload["lifecycle"][-2:] = reversed(payload["lifecycle"][-2:])
                    elif mutation == "mismatched_lifecycle":
                        payload["lifecycle"][-1]["actual_engine"] = third
                    elif mutation == "mismatched_attempt":
                        payload["attempts"][-1]["actual_engine"] = third
                    elif mutation == "mismatched_receipt":
                        payload["actual_engine"] = third
                    else:
                        payload["configured_engines"] = [primary, third]
                        for attempt_payload in payload["attempts"]:
                            attempt_payload["configured_engines"] = [primary, third]
                    self.assertFalse(schema_matches(payload, schema))

    def test_recovered_receipt_recomputes_readiness_digest(self):
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "passed", session="secondary-1"),
            ],
            quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )
        receipt = BrowserRecovery().run(self.request, adapter)
        readiness_index = next(
            index for index, item in enumerate(receipt.lifecycle)
            if item.action == "readiness_recheck"
        )
        forged = replace(
            receipt.lifecycle[readiness_index],
            readiness_evidence_digest="sha256:" + "0" * 64,
        )
        lifecycle = list(receipt.lifecycle); lifecycle[readiness_index] = forged
        with self.assertRaisesRegex(ValueError, "readiness evidence digest"):
            replace(receipt, lifecycle=tuple(lifecycle))

    def test_browser_request_rejects_lone_surrogate_stably(self):
        with self.assertRaisesRegex(ValueError, "invalid browser target"):
            BrowserRequest(
                "case-1", "https://example.invalid/\ud800", VIEWPORT,
                "chromium", "firefox", PROFILE_ID, ENGINES,
                TARGET_ORIGIN_DIGEST,
            )

    def test_request_snapshot_ignores_instance_controlled_dataclass_fields(self):
        forged = {
            "forged_case": "forged-case",
            "forged_url": "https://attacker.invalid/forged",
            "forged_viewport": VIEWPORT,
            "forged_primary": "firefox",
            "forged_secondary": "chromium",
            "forged_profile": PROFILE_ID,
            "forged_engines": ("firefox", "chromium"),
            "forged_origin": "origin-sha256:" + hashlib.sha256(
                b"https://attacker.invalid"
            ).hexdigest(),
        }
        for name, value in forged.items():
            object.__setattr__(self.request, name, value)
        object.__setattr__(
            self.request, "__dataclass_fields__", dict.fromkeys(forged),
        )

        snapshot = snapshot_browser_request(self.request)

        self.assertEqual(snapshot.case_id, self.request.case_id)
        self.assertEqual(snapshot.url, self.request.url)
        self.assertEqual(snapshot.primary_engine, self.request.primary_engine)

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

    def test_blocked_multi_engine_receipt_requires_alternate_and_restart_gap_evidence(self):
        receipt = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [attempt(1, "chromium", "failed", session="primary-1")],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
                launches=[RuntimeError("alternate unavailable")],
            ),
        )
        self.assertEqual(receipt.status, "blocked")
        self.assertIn(
            "primary_restart_unavailable",
            [item.result for item in receipt.lifecycle],
        )
        with self.assertRaises(ValueError):
            replace(receipt, lifecycle=receipt.lifecycle[:2])
        with self.assertRaises(ValueError):
            replace(receipt, lifecycle=(receipt.lifecycle[0], receipt.lifecycle[-1]))

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

    def test_quit_reconstruction_ignores_instance_controlled_dataclass_fields(self):
        quit_result = BrowserQuitEvidence(
            "chromium", False, "primary-1", action="application_restart",
        )
        object.__setattr__(
            quit_result, "__dataclass_fields__",
            dict.fromkeys(("engine", "confirmed", "session_id")),
        )
        adapter = FakeBrowserAdapter(
            [
                attempt(1, "chromium", "failed", session="primary-1"),
                attempt(2, "firefox", "failed", session="secondary-1"),
            ],
            quit_result=quit_result,
            launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
        )

        receipt = BrowserRecovery().run(self.request, adapter)

        self.assertIn("application_restart", [item.action for item in receipt.lifecycle])
        self.assertIn("primary_restart_unavailable", [item.result for item in receipt.lifecycle])
        self.assertNotIn(("launch_engine", "chromium", True), adapter.calls)

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
            ("recheck_readiness", "unavailable-1-chromium"),
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

    def test_origin_seals_reject_attempt_lifecycle_and_receipt_promotion(self):
        mutated = attempt(1, "chromium", "failed", session="primary-1")
        request = BrowserRequest(
            "case-1", TARGET_URL, VIEWPORT, "chromium", None,
            PROFILE_ID, ("chromium",), TARGET_ORIGIN_DIGEST,
        )
        mutated = replace(mutated, configured_engines=("chromium",))
        object.__setattr__(mutated, "result", "passed")
        object.__setattr__(mutated, "reason_code", None)
        object.__setattr__(mutated, "failure_detail", None)
        receipt = BrowserRecovery().run(
            request,
            FakeBrowserAdapter(
                [mutated],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
            ),
        )
        self.assertEqual(receipt.status, "blocked")
        self.assertEqual(receipt.attempts[0].reason_code, "invalid_adapter_evidence")

        clean = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter([
                attempt(1, "chromium", "passed", session="primary-1"),
            ]),
        )
        object.__setattr__(clean.attempts[0], "result", "failed")
        object.__setattr__(clean.attempts[0], "reason_code", "browser_tool_failure")
        with self.assertRaises(ValueError):
            snapshot_browser_recovery_receipt(clean)

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
        object.__setattr__(recovered.lifecycle[-1], "fresh_profile", False)
        with self.assertRaises(ValueError):
            snapshot_browser_recovery_receipt(recovered)

        blocked = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [attempt(1, "chromium", "failed", session="primary-1")],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
                launches=[RuntimeError("alternate unavailable")],
            ),
        )
        object.__setattr__(blocked, "status", "clean")
        object.__setattr__(blocked, "reason_code", "browser_verified_first_pass")
        object.__setattr__(blocked, "lifecycle", ())
        object.__setattr__(blocked, "missing_case_ids", ())
        object.__setattr__(blocked.attempts[0], "result", "passed")
        object.__setattr__(blocked.attempts[0], "reason_code", None)
        object.__setattr__(blocked.attempts[0], "failure_detail", None)
        with self.assertRaises(ValueError):
            snapshot_browser_recovery_receipt(blocked)

    def test_transition_grammar_rejects_impossible_restart_and_branch_order(self):
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
        impossible_gap = BrowserLifecycleEvidence(
            "case-1", "chromium", "chromium", "primary_restart",
            "primary_restart_unavailable", "primary-1", "primary-1",
        )
        with self.assertRaises(ValueError):
            replace(recovered, lifecycle=recovered.lifecycle + (impossible_gap,))

        alternate = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [
                    attempt(1, "chromium", "failed", session="primary-1"),
                    attempt(2, "firefox", "passed", session="secondary-1"),
                ],
                quit_result=BrowserQuitEvidence("chromium", False, "primary-1"),
                launches=[BrowserLaunchEvidence("firefox", True, True, "secondary-1")],
            ),
        )
        forged_quit = BrowserLifecycleEvidence(
            "case-1", "chromium", "chromium", "browser_process_quit",
            "confirmed", "primary-1", "primary-1",
        )
        with self.assertRaises(ValueError):
            replace(alternate, lifecycle=(forged_quit,) + alternate.lifecycle[1:])
        with self.assertRaises(ValueError):
            replace(alternate, lifecycle=alternate.lifecycle + (impossible_gap,))

    def test_alternate_launch_cannot_reuse_any_prior_attempt_or_launch_session(self):
        recovered = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [
                    attempt(1, "chromium", "failed", session="primary-1"),
                    attempt(2, "chromium", "failed", session="primary-2"),
                    attempt(3, "firefox", "passed", session="secondary-1"),
                ],
                launches=[
                    BrowserLaunchEvidence("chromium", True, True, "primary-2"),
                    BrowserLaunchEvidence("firefox", True, True, "secondary-1"),
                ],
            ),
        )
        reused_lifecycle = recovered.lifecycle[:-1] + (
            replace(recovered.lifecycle[-1], session_id="primary-2"),
        )
        reused_attempts = recovered.attempts[:-1] + (
            replace(recovered.attempts[-1], session_id="primary-2"),
        )
        with self.assertRaises(ValueError):
            replace(
                recovered, lifecycle=reused_lifecycle, attempts=reused_attempts,
            )

    def test_alternate_launch_rejects_every_prior_launch_outcome_session(self):
        launch_cases = (
            (
                BrowserLaunchEvidence("chromium", False, True, "prior-launch"),
                "prior-launch",
            ),
            (
                BrowserLaunchEvidence("chromium", True, False, "prior-nonfresh"),
                "prior-nonfresh",
            ),
            (RuntimeError("launch unavailable"), "unavailable-launch-chromium"),
        )
        for primary_launch, reused_session in launch_cases:
            with self.subTest(reused_session=reused_session):
                receipt = BrowserRecovery().run(
                    self.request,
                    FakeBrowserAdapter(
                        [
                            attempt(1, "chromium", "failed", session="primary-1"),
                            attempt(2, "firefox", "passed", session=reused_session),
                        ],
                        launches=[
                            primary_launch,
                            BrowserLaunchEvidence(
                                "firefox", True, True, reused_session,
                            ),
                        ],
                    ),
                )
                self.assertEqual(receipt.status, "blocked")
                self.assertEqual(receipt.reason_code, "human_help_required")
                self.assertEqual(
                    receipt.lifecycle[-1].result, "session_identity_mismatch",
                )
                self.assertEqual(len(receipt.attempts), 1)

    def test_receipt_rejects_alternate_reusing_prior_validation_session(self):
        recovered = BrowserRecovery().run(
            self.request,
            FakeBrowserAdapter(
                [
                    attempt(1, "chromium", "failed", session="primary-1"),
                    attempt(2, "firefox", "passed", session="secondary-1"),
                ],
                launches=[
                    BrowserLaunchEvidence(
                        "chromium", True, False, "primary-nonfresh",
                    ),
                    BrowserLaunchEvidence(
                        "firefox", True, True, "secondary-1",
                    ),
                ],
            ),
        )
        prior_validation = BrowserLifecycleEvidence(
            "case-1", "chromium", "chromium", "session_validation",
            "session_identity_mismatch", "prior-validation", "primary-1",
            "session_identity_mismatch",
        )
        reused_lifecycle = (
            recovered.lifecycle[0], prior_validation, recovered.lifecycle[2],
            replace(recovered.lifecycle[3], session_id="prior-validation"),
        )
        reused_attempts = recovered.attempts[:-1] + (
            replace(recovered.attempts[-1], session_id="prior-validation"),
        )
        with self.assertRaises(ValueError):
            replace(
                recovered, lifecycle=reused_lifecycle, attempts=reused_attempts,
            )

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
