import copy
import json
import unittest
from dataclasses import replace

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.browser_bundle import (
    BrowserBundleEvidence, BrowserEvidenceBundle, BrowserStepResult, bind_browser_evidence_bundle,
    match_browser_evidence_bundle, snapshot_browser_evidence_bundle,
)
from workflow_kernel.browser_scenario import (
    BrowserScenario, BrowserScenarioStep, snapshot_browser_scenario,
)
from workflow_kernel.browser_target import digest_target_origin, digest_target_route
from workflow_kernel.verification import PersonaCase, VerificationProfile, bind_browser_scenario
from workflow_kernel.adapters.browser import BrowserAdapter, BrowserScenarioAdapter


DIGEST = "sha256:" + "a" * 64
EVIDENCE_DIGEST = "sha256:" + "b" * 64
ORIGIN = digest_target_origin("http://127.0.0.1:8080")


def step(identifier, kind, **payload):
    return BrowserScenarioStep(identifier, kind, tuple(payload.items()))


def scenario(*, terminal="first_pass", status="passed", recovery=False):
    steps = [
        step("state", "state_fixture", profile_ref="fixtures/profiles/member.json",
             cookie_jar_ref="fixtures/cookies/member.jar",
             environment_fixture_refs=("fixtures/env/base.json",),
             login_fixture_ref="fixtures/login/member.json"),
        step("login", "login", lifecycle="success", fixture_ref="fixtures/login/member.json"),
        step("js-off", "javascript", enabled=False),
        step("navigate", "navigate", route="/dashboard"),
        step("interact", "interact", locator_kind="role", locator="button",
             action="click", value_ref=None),
        step("status", "assertion", assertion="status", locator_kind="none",
             locator=None, expected=200),
        step("focus", "assertion", assertion="focus", locator_kind="selector",
             locator="[data-testid=member-name]", expected=True),
        step("toast", "assertion", assertion="toast", locator_kind="role",
             locator="status", expected="Saved"),
        step("validation", "assertion", assertion="validation", locator_kind="label",
             locator="Name", expected="required"),
        step("overflow", "assertion", assertion="overflow", locator_kind="none",
             locator=None, expected=False),
        step("capture", "capture", capture_kind="screenshot",
             artifact_ref="browser/dashboard.png"),
    ]
    if recovery:
        steps.extend([
            step("app-restart", "application_restart", session_expectation="preserved"),
            step("post-restart", "session_assertion", expectation="authenticated"),
            step("primary-quit", "primary_quit"),
            step("primary-launch", "primary_launch", fresh_profile=True),
            step("fresh-session", "session_assertion", expectation="new"),
            step("primary-retry", "primary_retry", attempt=2),
            step("alternate", "alternate_engine", engine="firefox"),
        ])
    steps.append(step("terminal", "terminal", status=status, reason=terminal))
    return BrowserScenario(
        1, "dashboard", "case-sha256:" + "c" * 64,
        "profile-sha256:" + "d" * 64, "member", ORIGIN, "/dashboard",
        "chromium", "firefox", "1440x900", tuple(steps),
    )


def bundle(**changes):
    evidence = BrowserBundleEvidence(
        "capture", "screenshot", "browser/dashboard.png", EVIDENCE_DIGEST,
    )
    values = dict(
        schema_version=1, scenario_digest=scenario().scenario_digest,
        profile_id="profile-sha256:" + "d" * 64, persona_id="member",
        repository_state_digest=DIGEST, evidence_binding_digest=DIGEST,
        login_state="authenticated", javascript_enabled=False,
        restart_state="none", engine="chromium", viewport="1440x900",
        origin_digest=ORIGIN, route_digest=digest_target_route("/dashboard"),
        session_ref="session-1", attempt_refs=("attempt-1",),
        recovery_receipt_digest=DIGEST,
        results=(BrowserStepResult("capture", "passed", None, (EVIDENCE_DIGEST,)),),
        evidence=(evidence,), covered_case_ids=("case-sha256:" + "c" * 64,),
        missing_case_ids=(), terminal_reason="first_pass",
    )
    values.update(changes)
    return BrowserEvidenceBundle(**values)


class BrowserScenarioTests(unittest.TestCase):
    def test_scenario_is_immutable_strict_digest_bound_and_matches_schema(self):
        value = scenario(recovery=True)
        schema = json.loads((KERNEL_REFERENCES / "browser-scenario-schema.json").read_text())
        self.assertTrue(schema_matches(value.to_dict(), schema))
        self.assertEqual(BrowserScenario.from_dict(value.to_dict()), value)
        self.assertEqual(snapshot_browser_scenario(value), value)
        tampered = value.to_dict(); tampered["initial_route"] = "/other"
        with self.assertRaisesRegex(ValueError, "scenario digest mismatch"):
            BrowserScenario.from_dict(tampered)
        with self.assertRaises((AttributeError, TypeError)):
            value.steps += (value.steps[0],)

    def test_closed_steps_cover_fixtures_login_js_restart_and_assertion_vocabulary(self):
        value = scenario(recovery=True)
        kinds = {item.kind for item in value.steps}
        self.assertTrue({
            "state_fixture", "login", "javascript", "application_restart",
            "primary_quit", "primary_launch", "session_assertion", "primary_retry",
            "alternate_engine", "terminal",
        } <= kinds)
        assertions = {dict(item.payload)["assertion"] for item in value.steps if item.kind == "assertion"}
        self.assertEqual(assertions, {"status", "focus", "toast", "validation", "overflow"})

    def test_hostile_steps_and_raw_state_are_rejected(self):
        hostile = (
            lambda: step("bad", "navigate", route="javascript:alert(1)"),
            lambda: step("bad", "interact", locator_kind="selector", locator="xpath=//input",
                         action="click", value_ref=None),
            lambda: step("bad", "interact", locator_kind="label", locator="Email",
                         action="fill", value_ref="password=secret"),
            lambda: step("bad", "state_fixture", profile_ref="fixtures/p.json",
                         cookie_jar_ref="session_cookie=raw", environment_fixture_refs=(),
                         login_fixture_ref=None),
            lambda: step("bad", "capture", capture_kind="screenshot",
                         artifact_ref="https://example.test/proof.png?token=raw"),
            lambda: step("bad", "state_fixture", profile_ref="https://outside.test/profile",
                         cookie_jar_ref=None, environment_fixture_refs=(), login_fixture_ref=None),
            lambda: step("bad", "unknown", arbitrary_js="alert(1)"),
            lambda: step("bad", "assertion", assertion="status", locator_kind="none",
                         locator=None, expected=999999),
            lambda: step("bad", "assertion", assertion="count", locator_kind="selector",
                         locator="main", expected=1),
        )
        for candidate in hostile:
            with self.subTest(candidate=candidate), self.assertRaises(Exception):
                candidate()

    def test_profile_binding_and_separate_adapter_seam(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium", "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (), configured_engines=("chromium", "firefox"),
            target_origin_digest=ORIGIN,
        )
        value = scenario()
        rebound = BrowserScenario(
            1, value.scenario_id, case.case_id, profile.profile_id, value.persona_id,
            ORIGIN, value.initial_route, value.primary_engine, value.alternate_engine,
            value.viewport, value.steps,
        )
        self.assertEqual(bind_browser_scenario(profile, rebound), rebound)
        self.assertIsNot(BrowserScenarioAdapter, BrowserAdapter)

    def test_terminal_statuses_remain_distinct(self):
        for status in ("human_action_required", "human_help_required", "application_failure"):
            value = scenario(terminal=status, status=status)
            self.assertEqual(dict(value.steps[-1].payload)["status"], status)
        pause = step("mfa-pause", "human_pause", pause_id="member-mfa", action="mfa")
        self.assertEqual(dict(pause.payload)["action"], "mfa")

    def test_bundle_exact_reuse_schema_and_stale_reasons(self):
        value = bundle()
        schema = json.loads((KERNEL_REFERENCES / "browser-evidence-bundle-schema.json").read_text())
        self.assertTrue(schema_matches(value.to_dict(), schema))
        self.assertEqual(BrowserEvidenceBundle.from_dict(value.to_dict()), value)
        self.assertEqual(snapshot_browser_evidence_bundle(value), value)
        self.assertEqual(match_browser_evidence_bundle(value, value), {"matches": True, "reasons": []})
        self.assertEqual(bind_browser_evidence_bundle(scenario(), value), value)
        stale = bundle(repository_state_digest="sha256:" + "e" * 64,
                       session_ref="session-2")
        self.assertEqual(
            match_browser_evidence_bundle(value, stale)["reasons"],
            ["repository_state_changed", "session_changed"],
        )

    def test_missing_tampered_and_reachability_evidence_never_upgrade(self):
        raw = bundle().to_dict(); raw["evidence"][0]["evidence_digest"] = DIGEST
        with self.assertRaises(ValueError):
            BrowserEvidenceBundle.from_dict(raw)
        with self.assertRaises(ValueError):
            bundle(results=(BrowserStepResult("other", "passed", None, (EVIDENCE_DIGEST,)),))
        reachability = BrowserBundleEvidence(
            "capture", "screenshot", "browser/dashboard.png", EVIDENCE_DIGEST,
            "reachability",
        )
        with self.assertRaisesRegex(ValueError, "current browser proof"):
            bundle(evidence=(reachability,))
        missing = bundle(
            login_state="human_action_required", results=(BrowserStepResult(
                "login", "human_action_required", "mfa_required", (),
            ),), evidence=(), covered_case_ids=(),
            missing_case_ids=("case-sha256:" + "c" * 64,),
            terminal_reason="human_action_required", recovery_receipt_digest=None,
        )
        self.assertEqual(missing.terminal_reason, "human_action_required")

    def test_application_failure_does_not_require_browser_restart(self):
        value = bundle(
            results=(BrowserStepResult("validation", "application_failure", "product_assertion_failed", ()),),
            evidence=(), covered_case_ids=(), missing_case_ids=("case-sha256:" + "c" * 64,),
            terminal_reason="application_failure", recovery_receipt_digest=None,
        )
        self.assertEqual(value.restart_state, "none")

    def test_first_pass_fresh_primary_alternate_and_human_help_bundles(self):
        self.assertEqual(bundle().terminal_reason, "first_pass")
        fresh = bundle(
            restart_state="fresh_primary", session_ref="session-2",
            attempt_refs=("attempt-1", "attempt-2"), terminal_reason="fresh_primary",
        )
        alternate = bundle(
            restart_state="alternate_engine", engine="firefox", session_ref="session-3",
            attempt_refs=("attempt-1", "attempt-2", "attempt-3"),
            terminal_reason="alternate_engine",
        )
        help_required = bundle(
            results=(BrowserStepResult("terminal", "human_help_required", "browser_unavailable", ()),),
            evidence=(), covered_case_ids=(), missing_case_ids=("case-sha256:" + "c" * 64,),
            terminal_reason="human_help_required", recovery_receipt_digest=None,
        )
        self.assertEqual((fresh.restart_state, alternate.engine, help_required.terminal_reason),
                         ("fresh_primary", "firefox", "human_help_required"))

    def test_bundle_rejects_raw_cookies_and_unknown_fields(self):
        raw = bundle().to_dict(); raw["session_cookie"] = "raw"
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            BrowserEvidenceBundle.from_dict(raw)
        with self.assertRaises(ValueError):
            bundle(session_ref="session_cookie=raw")
        with self.assertRaises(ValueError):
            bundle(session_ref="ghp_abcdefghijk")

    def test_schemas_are_closed_at_nested_boundaries(self):
        scenario_schema = json.loads((KERNEL_REFERENCES / "browser-scenario-schema.json").read_text())
        raw = scenario().to_dict(); raw["steps"][3]["payload"]["enabled"] = True
        self.assertFalse(schema_matches(raw, scenario_schema))
        bundle_schema = json.loads((KERNEL_REFERENCES / "browser-evidence-bundle-schema.json").read_text())
        raw_bundle = bundle().to_dict(); raw_bundle["results"][0]["raw_log"] = "private"
        self.assertFalse(schema_matches(raw_bundle, bundle_schema))


if __name__ == "__main__":
    unittest.main()
