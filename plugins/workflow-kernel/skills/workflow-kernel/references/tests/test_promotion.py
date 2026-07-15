import unittest

from workflow_kernel.promotion import (
    EvidenceOrigin, PromotionEvidence, PromotionState, evaluate_promotion,
)


ENFORCE_CRITERIA = (
    "zero_unexplained_receipt_gaps",
    "illegal_transition_scenarios_passed",
    "terminal_cleanup_scenarios_passed",
    "host_fixture_claude_passed",
    "host_fixture_codex_passed",
    "host_fixture_generic_passed",
    "persona_completeness_scenarios_passed",
    "browser_recovery_scenarios_passed",
    "provider_security_boundaries_unchanged",
)


def evidence(names, origin=EvidenceOrigin.FIXTURE):
    return tuple(PromotionEvidence(name, True, origin) for name in names)


class PromotionTests(unittest.TestCase):
    def test_shadow_to_enforce_fails_closed_then_allows_complete_fixture_evidence(self):
        blocked = evaluate_promotion("shadow", "enforce_available", ())
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.reason_codes, ("promotion_evidence_missing",))
        self.assertEqual(blocked.missing_evidence, ENFORCE_CRITERIA)

        allowed = evaluate_promotion(
            PromotionState.SHADOW, PromotionState.ENFORCE_AVAILABLE,
            evidence(ENFORCE_CRITERIA),
        )
        self.assertTrue(allowed.allowed)
        self.assertEqual(allowed.reason_codes, ("promotion_allowed",))
        self.assertEqual(allowed.missing_evidence, ())

    def test_native_requires_real_run_origin_for_every_supported_host(self):
        base = evidence(ENFORCE_CRITERIA)
        native_fixture = evidence((
            "injected_interruption_reconstructs_state",
            "builder_resume_evidence", "builder_non_resume_evidence",
            "git_cleanup_success", "git_cleanup_failure", "git_cleanup_blocking",
            "docker_cleanup_success", "docker_cleanup_failure", "docker_cleanup_blocking",
            "real_shadow_run:claude", "real_shadow_run:codex", "real_shadow_run:generic",
        ))
        blocked = evaluate_promotion(
            "enforce_available", "native_available", base + native_fixture,
        )
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.missing_evidence, (
            "real_shadow_run:claude", "real_shadow_run:codex", "real_shadow_run:generic",
        ))

        real = evidence(
            ("real_shadow_run:claude", "real_shadow_run:codex", "real_shadow_run:generic"),
            EvidenceOrigin.REAL_RUN,
        )
        allowed = evaluate_promotion(
            "enforce_available", "native_available", base + native_fixture + real,
        )
        self.assertTrue(allowed.allowed)

    def test_native_default_is_always_separate_human_decision(self):
        decision = evaluate_promotion("native_available", "native_default", ())
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("separate_human_approval_required",))
        self.assertEqual(decision.missing_evidence, ("separate_human_approval",))

    def test_non_adjacent_transition_and_conflicting_evidence_fail_closed(self):
        invalid = evaluate_promotion("shadow", "native_available", ())
        self.assertFalse(invalid.allowed)
        self.assertEqual(invalid.reason_codes, ("invalid_promotion_transition",))
        with self.assertRaises(ValueError):
            evaluate_promotion(
                "shadow", "enforce_available",
                (PromotionEvidence("x", True, EvidenceOrigin.FIXTURE),
                 PromotionEvidence("x", False, EvidenceOrigin.FIXTURE)),
            )


if __name__ == "__main__":
    unittest.main()
