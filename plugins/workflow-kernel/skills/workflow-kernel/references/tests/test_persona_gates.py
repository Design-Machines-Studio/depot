import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from workflow_kernel.verification import (
    EvidenceRef, PersonaCase, VerificationGate, VerificationProfile,
)
from workflow_kernel.adapters.personas import ProjectPersonaAdapter
from workflow_kernel.schema import InvalidSchemaError


ROOT = Path(__file__).parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "ux" / "assembly"
SECRET = "sk-fixture-persona-password-must-not-survive"
TARGET_ORIGIN = "https://example.invalid"
TARGET_ORIGIN_DIGEST = "origin-sha256:" + hashlib.sha256(TARGET_ORIGIN.encode()).hexdigest()


def evidence(
    case, *, evaluation=None, authenticated=True, proof_kind="browser",
    actual_engine=None, substitution=None, profile=None, recovery_receipt=None,
):
    configured = profile.configured_engines if profile is not None else (case.browser_engine,)
    profile_id = profile.profile_id if profile is not None else "profile-sha256:" + "a" * 64
    if (proof_kind == "browser" and recovery_receipt is None
            and substitution is None
            and actual_engine in {None, case.browser_engine}
            and profile is not None):
        from workflow_kernel.adapters.browser import (
            BrowserAttempt, BrowserRecovery, BrowserRequest,
        )
        url = TARGET_ORIGIN + case.route
        url_digest = "url-sha256:" + hashlib.sha256(url.encode()).hexdigest()
        route_digest = "sha256:" + hashlib.sha256(case.route.encode()).hexdigest()

        class CleanAdapter:
            def attempt(self, request, engine):
                return BrowserAttempt(
                    case.case_id, 1, case.browser_engine, engine, "verify", "passed",
                    None, None, "proof/screenshot.png", None, None, "primary-1",
                    "browser", None, profile.profile_id, profile.configured_engines,
                    url_digest, profile.target_origin_digest, route_digest, case.viewport,
                )

        secondary = next(
            (engine for engine in configured if engine != case.browser_engine), None,
        )
        recovery_receipt = BrowserRecovery().run(
            BrowserRequest(
                case.case_id, url, case.viewport, case.browser_engine, secondary,
                profile.profile_id, profile.configured_engines,
                profile.target_origin_digest,
            ),
            CleanAdapter(),
        )
    attempt_number = recovery_receipt.attempts[-1].attempt_number if recovery_receipt else 1
    return EvidenceRef(
        case.case_id, case.persona_id, case.scenario_id, case.route,
        case.browser_engine, case.viewport, attempt_number,
        case.expected_outcome if evaluation is None else evaluation,
        authenticated, "proof/screenshot.png", proof_kind,
        actual_engine or case.browser_engine, substitution, profile_id,
        configured, recovery_receipt,
        profile.target_origin_digest if profile is not None else TARGET_ORIGIN_DIGEST,
    )


class PersonaGateTests(unittest.TestCase):
    def test_complete_set_requires_every_required_case_not_a_sample_count(self):
        cases = (
            PersonaCase("p1", "s1", "member", "/one", "chromium", "1440x900", True),
            PersonaCase("p2", "s2", "member", "/two", "firefox", "375x812", True),
            PersonaCase("p3", "s3", "member", "/three", "firefox", "375x812", False),
        )
        profile = VerificationProfile(1, "project_declaration", cases, ()).bind_target_origin(TARGET_ORIGIN)
        missing = VerificationGate().evaluate(profile, [evidence(cases[0], profile=profile)])
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason_code, "missing_required_persona_evidence")
        self.assertEqual(missing.missing_case_ids, (cases[1].case_id,))
        complete = VerificationGate().evaluate(
            profile, [evidence(cases[0], profile=profile), evidence(cases[1], profile=profile)]
        )
        self.assertTrue(complete.allowed)

    def test_expected_blocked_is_evaluative_but_unauthenticated_or_curl_is_not(self):
        case = PersonaCase(
            "new-member", "vote", "probationary", "/vote", "chromium",
            "375x812", True, expected_outcome="BLOCKED", requires_auth=True,
        )
        profile = VerificationProfile(1, "project_declaration", (case,), ()).bind_target_origin(TARGET_ORIGIN)
        gate = VerificationGate()
        self.assertTrue(gate.evaluate(profile, [evidence(case, profile=profile)]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, profile=profile, authenticated=False)]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, profile=profile, proof_kind="curl")]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, profile=profile, evaluation="")]).allowed)

    def test_only_explicit_alternate_engine_substitution_satisfies_requested_case(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (),
            configured_engines=("chromium", "firefox"),
        ).bind_target_origin(TARGET_ORIGIN)
        with self.assertRaises(InvalidSchemaError):
            evidence(case, profile=profile, actual_engine="firefox")
        with self.assertRaises(InvalidSchemaError):
            evidence(
                case, profile=profile, actual_engine="firefox",
                substitution="alternate_engine_recovery",
            )

    def test_substitution_requires_receipt_from_same_profile_and_configured_set(self):
        from workflow_kernel.adapters.browser import (
            BrowserAttempt, BrowserLaunchEvidence, BrowserQuitEvidence,
            BrowserRecovery, BrowserRequest,
        )
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (),
            configured_engines=("chromium", "firefox"),
        ).bind_target_origin(TARGET_ORIGIN)
        url = "https://example.invalid/dashboard"
        url_digest = "url-sha256:" + hashlib.sha256(url.encode()).hexdigest()
        route_digest = "sha256:" + hashlib.sha256(b"/dashboard").hexdigest()

        class Adapter:
            def __init__(self): self.count = 0
            def attempt(self, request, engine):
                self.count += 1
                result = "failed" if self.count == 1 else "passed"
                return BrowserAttempt(
                    case.case_id, self.count, "chromium", engine, "verify", result,
                    "browser_tool_failure" if result == "failed" else None,
                    "failed" if result == "failed" else None,
                    "proof/screenshot.png", None, None,
                    "primary-1" if self.count == 1 else "secondary-1", "browser",
                    None if engine == "chromium" else "alternate_engine_recovery",
                    profile.profile_id, profile.configured_engines,
                    url_digest, TARGET_ORIGIN_DIGEST, route_digest, case.viewport,
                )
            def quit_engine(self, engine):
                return BrowserQuitEvidence(engine, False, "primary-1")
            def launch_engine(self, engine, fresh_profile=True):
                return BrowserLaunchEvidence(engine, True, True, "secondary-1")

        request = BrowserRequest(
            case.case_id, url, case.viewport, "chromium", "firefox",
            profile.profile_id, profile.configured_engines, TARGET_ORIGIN_DIGEST,
        )
        receipt = BrowserRecovery().run(request, Adapter())
        valid = evidence(
            case, profile=profile, actual_engine="firefox",
            substitution="alternate_engine_recovery", recovery_receipt=receipt,
        )
        self.assertTrue(VerificationGate().evaluate(profile, [valid]).allowed)
        other = VerificationProfile(
            1, "project_declaration", (case,), (),
            configured_engines=("chromium", "webkit"),
        ).bind_target_origin(TARGET_ORIGIN)
        with self.assertRaises(InvalidSchemaError):
            evidence(
                case, profile=other, actual_engine="firefox",
                substitution="alternate_engine_recovery", recovery_receipt=receipt,
            )

    def test_gate_reconstructs_evidence_and_nested_receipt_before_trusting_it(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (), configured_engines=("chromium",),
        ).bind_target_origin(TARGET_ORIGIN)
        for mutation in ("evidence_origin", "nested_attempt", "curl_promotion"):
            with self.subTest(mutation=mutation):
                item = evidence(case, profile=profile)
                if mutation == "evidence_origin":
                    object.__setattr__(item, "target_origin_digest", "origin-sha256:" + "b" * 64)
                elif mutation == "nested_attempt":
                    object.__setattr__(
                        item.recovery_receipt.attempts[0], "proof_kind", "curl",
                    )
                else:
                    object.__setattr__(item, "proof_kind", "curl")
                    object.__setattr__(item, "recovery_receipt", None)
                    object.__setattr__(item, "proof_kind", "browser")
                with self.assertRaises(InvalidSchemaError):
                    VerificationGate().evaluate(profile, (item,))
        ignored_profile = VerificationProfile(
            1, "project_declaration", (), (),
            selection_status="no_runnable_tasks", configured_engines=("chromium",),
        )
        item = evidence(case, profile=profile)
        object.__setattr__(item, "proof_kind", "curl")
        with self.assertRaises(InvalidSchemaError):
            VerificationGate().evaluate(ignored_profile, (item,))

    def test_declared_empty_profile_requires_non_runnable_provenance(self):
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile(1, "project_declaration", (), ())
        non_runnable = VerificationProfile(
            1, "project_declaration", (), (), "declared", "no_runnable_tasks",
        )
        decision = VerificationGate().evaluate(non_runnable, (), work_kind="ui")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, "no_runnable_persona_cases_declared")

    def test_declared_profile_cannot_claim_not_declared_selection(self):
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile(
                1, "project_declaration", (), (), "declared", "not_declared",
            )

    def test_not_declared_blocks_ui_but_not_non_ui_and_fabricates_no_personas(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(Path(directory))
        self.assertEqual(profile.discovery_status, "not_declared")
        self.assertEqual(profile.cases, ())
        self.assertFalse(VerificationGate().evaluate(profile, (), work_kind="ui").allowed)
        self.assertTrue(VerificationGate().evaluate(profile, (), work_kind="logic").allowed)

    def test_discovery_outputs_and_failures_do_not_retain_auth_values(self):
        profile = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(FIXTURE)
        serialized = json.dumps(profile.to_dict(), sort_keys=True)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("member@example.invalid", serialized)
        self.assertNotIn(SECRET, repr(profile))


if __name__ == "__main__":
    unittest.main()
