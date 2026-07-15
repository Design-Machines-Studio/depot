import json
import hashlib
import tempfile
import traceback
import unittest
from pathlib import Path

from workflow_kernel.verification import (
    EvidenceRef, PersonaCase, VerificationGate, VerificationProfile,
)
from workflow_kernel.adapters.personas import ProjectPersonaAdapter
from workflow_kernel.schema import ErrorDetailKey, InvalidSchemaError
from tests import KERNEL_REFERENCES
from tests import detail_digest


ROOT = KERNEL_REFERENCES
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
                    case.declared_route_digest,
                )

        secondary = next(
            (engine for engine in configured if engine != case.browser_engine), None,
        )
        recovery_receipt = BrowserRecovery().run(
            BrowserRequest(
                case.case_id, url, case.viewport, case.browser_engine, secondary,
                profile.profile_id, profile.configured_engines,
                profile.target_origin_digest,
                case.declared_route_digest,
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
        case.declared_route_digest,
    )


class PersonaGateTests(unittest.TestCase):
    def test_gate_snapshots_profile_and_nested_cases_before_coverage(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (), configured_engines=("chromium",),
        ).bind_target_origin(TARGET_ORIGIN)

        object.__setattr__(profile.cases[0], "required", False)
        with self.assertRaises(InvalidSchemaError):
            VerificationGate().evaluate(profile, ())

    def test_profile_snapshot_ignores_instance_controlled_dataclass_fields(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (), configured_engines=("chromium",),
        ).bind_target_origin(TARGET_ORIGIN)
        forged = {
            "forged_schema": 1,
            "forged_source": "project_declaration",
            "forged_cases": (),
            "forged_auth": (),
            "forged_discovery": "declared",
            "forged_selection": "no_runnable_tasks",
            "forged_engines": ("chromium",),
            "forged_origin": None,
            "forged_diagnostics": (),
        }
        for name, value in forged.items():
            object.__setattr__(profile, name, value)
        object.__setattr__(
            profile, "__dataclass_fields__", dict.fromkeys(forged),
        )

        decision = VerificationGate().evaluate(profile, ())

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "missing_required_persona_evidence")

        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(
            1, "project_declaration", (case,), (), configured_engines=("chromium",),
        ).bind_target_origin(TARGET_ORIGIN)
        object.__setattr__(profile, "cases", ())
        with self.assertRaises(InvalidSchemaError):
            VerificationGate().evaluate(profile, ())

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
            BrowserReadinessEvidence, BrowserRecovery, BrowserRequest,
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
                    case.declared_route_digest,
                )
            def quit_engine(self, engine):
                return BrowserQuitEvidence(engine, False, "primary-1")
            def launch_engine(self, engine, fresh_profile=True):
                return BrowserLaunchEvidence(engine, True, True, "secondary-1")
            def recheck_readiness(self, request, previous_session_id):
                return BrowserReadinessEvidence(
                    request.case_id, previous_session_id,
                    request.target_url_digest, request.target_origin_digest,
                    True, True, True,
                )

        request = BrowserRequest(
            case.case_id, url, case.viewport, "chromium", "firefox",
            profile.profile_id, profile.configured_engines, TARGET_ORIGIN_DIGEST,
            case.declared_route_digest,
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

    def test_governance_task_without_explicit_role_fails_closed(self):
        import shutil

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ux"
            shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__"))
            task = target / "tasks" / "governance" / "sample-task.md"
            lines = [
                line for line in task.read_text().splitlines(keepends=True)
                if not line.startswith("requires_role:")
            ]
            task.write_text("".join(lines))
            adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
            with self.assertRaises(InvalidSchemaError) as raised:
                adapter.discover(target, declaration_root=".")
            self.assertEqual(
                raised.exception.details[ErrorDetailKey.REASON_CODE.value],
                detail_digest("invalid_verification_declaration"),
            )

    def test_governance_gate_cannot_be_bypassed_by_omitted_miscased_or_mismatched_area(self):
        # Finding 090: the fail-closed governance gate keys on the task
        # path's tasks/<area>/ directory, not only the optional frontmatter
        # value. Omitting `area:`, mis-casing it, contradicting the
        # governance directory, or declaring governance outside it all fail
        # closed instead of silently defaulting to member/public scope.
        import shutil

        def drop_role(text):
            return "".join(
                line for line in text.splitlines(keepends=True)
                if not line.startswith("requires_role:")
            )

        mutations = (
            ("omitted-area", lambda text: drop_role("".join(
                line for line in text.splitlines(keepends=True)
                if not line.startswith("area:")
            ))),
            ("mis-cased-area", lambda text: drop_role(
                text.replace("area: governance", "area: Governance")
            )),
            ("mismatched-area", lambda text: text.replace(
                "area: governance", "area: onboarding",
            )),
        )
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "ux"
                shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__"))
                task = target / "tasks" / "governance" / "sample-task.md"
                task.write_text(mutate(task.read_text()))
                adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
                with self.assertRaises(InvalidSchemaError) as raised:
                    adapter.discover(target, declaration_root=".")
                self.assertEqual(
                    raised.exception.details[ErrorDetailKey.REASON_CODE.value],
                    detail_digest("invalid_verification_declaration"),
                )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ux"
            shutil.copytree(FIXTURE, target, ignore=shutil.ignore_patterns("__pycache__"))
            task = target / "tasks" / "governance" / "sample-task.md"
            misfiled = target / "tasks" / "onboarding" / task.name
            misfiled.parent.mkdir()
            misfiled.write_text(task.read_text())  # keeps `area: governance`
            task.unlink()
            adapter = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json")
            with self.assertRaises(InvalidSchemaError) as raised:
                adapter.discover(target, declaration_root=".")
            self.assertEqual(
                raised.exception.details[ErrorDetailKey.REASON_CODE.value],
                detail_digest("invalid_verification_declaration"),
            )

    def test_discovery_outputs_and_failures_do_not_retain_auth_values(self):
        profile = ProjectPersonaAdapter(policy_path=ROOT / "workflow-policy.json").discover(
            FIXTURE, declaration_root=".",
        )
        serialized = json.dumps(profile.to_dict(), sort_keys=True)
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("member@example.invalid", serialized)
        self.assertNotIn(SECRET, repr(profile))

    def test_project_persona_adapter_executes_through_injected_executor(self):
        calls = []

        class Executor:
            def execute(self, case, profile):
                calls.append((case.case_id, profile.profile_id))
                return evidence(case, profile=profile)

        adapter = ProjectPersonaAdapter(
            policy_path=ROOT / "workflow-policy.json", executor=Executor(),
        )
        profile = adapter.discover(
            FIXTURE, declaration_root=".", target_origin=TARGET_ORIGIN,
        )
        result = adapter.execute(profile.cases[0])
        self.assertEqual(result.case_id, profile.cases[0].case_id)
        self.assertEqual(result.verification_profile_id, profile.profile_id)
        self.assertEqual(calls, [(profile.cases[0].case_id, profile.profile_id)])

    def test_project_persona_adapter_execute_fails_closed_without_bound_context(self):
        class Executor:
            def execute(self, case, profile):
                return evidence(case, profile=profile)

        adapter = ProjectPersonaAdapter(
            policy_path=ROOT / "workflow-policy.json", executor=Executor(),
        )
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        with self.assertRaises(InvalidSchemaError):
            adapter.execute(case)
        profile = adapter.discover(FIXTURE, declaration_root=".")
        with self.assertRaises(InvalidSchemaError):
            adapter.execute(profile.cases[0])

    def test_executor_exceptions_have_stable_redacted_unchained_evidence(self):
        class HostileExecutorError(RuntimeError):
            def __str__(self):
                raise RuntimeError("hostile str leaked")

            def __repr__(self):
                raise RuntimeError("hostile repr leaked")

        for error in (RuntimeError(SECRET), HostileExecutorError(SECRET)):
            with self.subTest(error_type=type(error).__name__):
                class Executor:
                    def execute(self, case, profile):
                        raise error

                adapter = ProjectPersonaAdapter(
                    policy_path=ROOT / "workflow-policy.json", executor=Executor(),
                )
                profile = adapter.discover(
                    FIXTURE, declaration_root=".", target_origin=TARGET_ORIGIN,
                )
                try:
                    adapter.execute(profile.cases[0])
                except InvalidSchemaError as raised:
                    rendered = "".join(
                        traceback.TracebackException.from_exception(raised).format()
                    )
                    self.assertTrue(raised.__suppress_context__)
                    self.assertIsNone(raised.__cause__)
                    self.assertIsNone(raised.__context__)
                    self.assertNotIn(SECRET, str(raised))
                    self.assertNotIn(SECRET, repr(raised))
                    self.assertNotIn(SECRET, rendered)
                    self.assertNotIn("hostile str leaked", rendered)
                    self.assertNotIn("hostile repr leaked", rendered)
                    self.assertEqual(
                        raised.details[ErrorDetailKey.REASON_CODE.value],
                        detail_digest("invalid_verification_evidence"),
                    )
                else:
                    self.fail("executor exception must fail closed")


if __name__ == "__main__":
    unittest.main()
