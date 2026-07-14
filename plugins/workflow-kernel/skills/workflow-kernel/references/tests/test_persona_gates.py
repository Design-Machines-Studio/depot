import json
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


def evidence(
    case, *, evaluation=None, authenticated=True, proof_kind="browser",
    actual_engine=None, substitution=None,
):
    return EvidenceRef(
        case.case_id, case.persona_id, case.scenario_id, case.route,
        case.browser_engine, case.viewport, 1,
        case.expected_outcome if evaluation is None else evaluation,
        authenticated, "proof/screenshot.png", proof_kind,
        actual_engine or case.browser_engine, substitution,
    )


class PersonaGateTests(unittest.TestCase):
    def test_complete_set_requires_every_required_case_not_a_sample_count(self):
        cases = (
            PersonaCase("p1", "s1", "member", "/one", "chromium", "1440x900", True),
            PersonaCase("p2", "s2", "member", "/two", "firefox", "375x812", True),
            PersonaCase("p3", "s3", "member", "/three", "firefox", "375x812", False),
        )
        profile = VerificationProfile(1, "project_declaration", cases, ())
        missing = VerificationGate().evaluate(profile, [evidence(cases[0])])
        self.assertFalse(missing.allowed)
        self.assertEqual(missing.reason_code, "missing_required_persona_evidence")
        self.assertEqual(missing.missing_case_ids, (cases[1].case_id,))
        complete = VerificationGate().evaluate(profile, [evidence(cases[0]), evidence(cases[1])])
        self.assertTrue(complete.allowed)

    def test_expected_blocked_is_evaluative_but_unauthenticated_or_curl_is_not(self):
        case = PersonaCase(
            "new-member", "vote", "probationary", "/vote", "chromium",
            "375x812", True, expected_outcome="BLOCKED", requires_auth=True,
        )
        profile = VerificationProfile(1, "project_declaration", (case,), ())
        gate = VerificationGate()
        self.assertTrue(gate.evaluate(profile, [evidence(case)]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, authenticated=False)]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, proof_kind="curl")]).allowed)
        self.assertFalse(gate.evaluate(profile, [evidence(case, evaluation="")]).allowed)

    def test_only_explicit_alternate_engine_substitution_satisfies_requested_case(self):
        case = PersonaCase(
            "member", "dashboard", "member", "/dashboard", "chromium",
            "1440x900", True,
        )
        profile = VerificationProfile(1, "project_declaration", (case,), ())
        generic_mismatch = evidence(case, actual_engine="firefox")
        explicit_substitution = evidence(
            case, actual_engine="firefox",
            substitution="alternate_engine_recovery",
        )
        self.assertFalse(VerificationGate().evaluate(profile, [generic_mismatch]).allowed)
        self.assertTrue(VerificationGate().evaluate(profile, [explicit_substitution]).allowed)

    def test_declared_empty_profile_requires_non_runnable_provenance(self):
        with self.assertRaises(InvalidSchemaError):
            VerificationProfile(1, "project_declaration", (), ())
        non_runnable = VerificationProfile(
            1, "project_declaration", (), (), "declared", "no_runnable_tasks",
        )
        decision = VerificationGate().evaluate(non_runnable, (), work_kind="ui")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason_code, "no_runnable_persona_cases_declared")

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
