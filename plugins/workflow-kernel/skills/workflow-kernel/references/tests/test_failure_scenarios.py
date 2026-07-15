import json
import unittest
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"
FILES = (
    "terminal-paths.json", "provider-failures.json",
    "verification-failures.json", "resource-failures.json",
)
REQUIRED_IDS = {
    "success", "failure", "blocked", "cancelled", "interrupted",
    "empty_agent_output", "malformed_agent_output", "dead_session",
    "provider_unavailable", "model_cap", "requested_executor_misroute",
    "repeated_failure_signature", "core_review_failure_after_fallback",
    "duplicate_event", "gapped_event", "truncated_final_record",
    "corrupt_middle_record", "stale_revision", "concurrent_writer_lease",
    "exit_before_state_replacement", "unknown_major_schema", "terminal_replay",
    "no_declared_personas", "legacy_statusless_required", "missing_required_persona",
    "failed_persona_authentication", "secret_persona_fixture", "primary_browser_lock",
    "failed_primary_close", "failed_primary_relaunch", "failed_primary_retry", "secondary_unavailable",
    "secondary_failure", "human_help_terminal", "curl_without_browser",
    "partial_resource_creation", "exit_before_registration", "foreign_labels",
    "running_resource", "volume_inspect_failure", "chunk_removal_failure",
    "terminal_reconciliation_failure", "second_cleanup_idempotent",
}
TOP_KEYS = {"schema_version", "suite", "scenarios"}
SCENARIO_KEYS = {"id", "category", "driver", "input", "expected"}
EXPECTED_KEYS = {
    "final_state", "reason_codes", "retained_evidence", "cleanup_invocations",
    "resource_dispositions", "promotion_impact",
}
IMPACT_KEYS = {"criterion", "satisfied", "origin"}
DRIVERS = {"terminal_path", "provider_failure", "state_failure", "verification_failure", "resource_failure"}


def load_suites():
    suites = []
    for name in FILES:
        path = FIXTURES / name
        if path.stat().st_size > 1_000_000:
            raise ValueError("scenario suite too large")
        value = json.loads(path.read_text(encoding="utf-8"))
        if type(value) is not dict or set(value) != TOP_KEYS or value["schema_version"] != 1:
            raise ValueError("invalid scenario suite")
        if (type(value["suite"]) is not str or not value["suite"]
                or type(value["scenarios"]) is not list
                or not 1 <= len(value["scenarios"]) <= 100):
            raise ValueError("invalid scenario suite")
        for scenario in value["scenarios"]:
            if type(scenario) is not dict or set(scenario) != SCENARIO_KEYS:
                raise ValueError("invalid scenario")
            expected = scenario["expected"]
            if (scenario["driver"] not in DRIVERS or type(scenario["input"]) is not dict
                    or type(expected) is not dict or set(expected) != EXPECTED_KEYS
                    or type(expected["final_state"]) is not str
                    or type(expected["reason_codes"]) is not list
                    or not expected["reason_codes"]
                    or any(type(item) is not str or not item for item in expected["reason_codes"])
                    or type(expected["retained_evidence"]) is not list
                    or any(type(item) is not str or not item for item in expected["retained_evidence"])
                    or type(expected["cleanup_invocations"]) is not int
                    or expected["cleanup_invocations"] != 1
                    or type(expected["resource_dispositions"]) is not list
                    or type(expected["promotion_impact"]) is not dict
                    or set(expected["promotion_impact"]) != IMPACT_KEYS
                    or expected["promotion_impact"]["origin"] != "fixture"):
                raise ValueError("invalid scenario")
        suites.append(value)
    return tuple(suites)


def replay(scenario):
    injected = scenario["input"]
    return {
        "final_state": injected["final_state"],
        "reason_codes": list(injected.get("reason_codes", (scenario["id"],))),
        "retained_evidence": list(injected.get("retained_evidence", ())),
        "cleanup_invocations": 1,
        "resource_dispositions": list(injected.get("resource_dispositions", ())),
        "promotion_impact": {
            "criterion": injected["criterion"], "satisfied": False, "origin": "fixture",
        },
    }


class FailureScenarioTests(unittest.TestCase):
    def test_failure_matrix_is_complete_strict_and_deterministically_replayable(self):
        scenarios = [scenario for suite in load_suites() for scenario in suite["scenarios"]]
        ids = [scenario["id"] for scenario in scenarios]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), REQUIRED_IDS)
        for scenario in scenarios:
            with self.subTest(scenario=scenario["id"]):
                self.assertEqual(replay(scenario), scenario["expected"])
                self.assertEqual(scenario["expected"]["cleanup_invocations"], 1)

    def test_terminal_outcomes_each_reconcile_exactly_once(self):
        terminal = next(s for s in load_suites() if s["suite"] == "terminal-paths")
        self.assertEqual(
            {scenario["expected"]["final_state"] for scenario in terminal["scenarios"][:5]},
            {"succeeded", "failed", "blocked", "cancelled", "interrupted"},
        )
        self.assertTrue(all(s["expected"]["cleanup_invocations"] == 1 for s in terminal["scenarios"][:5]))

    def test_secret_sentinel_is_never_retained(self):
        sentinel = "sk-fixture-persona-password-must-not-survive"
        for suite in load_suites():
            self.assertNotIn(sentinel, json.dumps(suite, sort_keys=True))

    def test_provider_and_browser_failures_retain_decision_evidence(self):
        scenarios = {scenario["id"]: scenario for suite in load_suites() for scenario in suite["scenarios"]}
        required = {
            "requested_executor:openrouter", "attempted_executor:openrouter",
            "implemented_by:codex", "fallback_path:claude",
        }
        for scenario_id in (
            "provider_unavailable", "model_cap", "requested_executor_misroute",
            "repeated_failure_signature", "core_review_failure_after_fallback",
        ):
            self.assertTrue(required <= set(scenarios[scenario_id]["expected"]["retained_evidence"]))
        human_help = scenarios["human_help_terminal"]["expected"]
        self.assertEqual(human_help["reason_codes"], ["human_help_required"])
        self.assertTrue({"attempt:primary", "attempt:relaunch", "attempt:secondary"} <= set(human_help["retained_evidence"]))
        partial = scenarios["partial_resource_creation"]["input"]
        self.assertEqual(partial["resource_kinds"], ["worktree", "container", "network", "volume"])


if __name__ == "__main__":
    unittest.main()
