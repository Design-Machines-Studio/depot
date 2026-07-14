import json
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest
from workflow_kernel.adapters.base import (
    AttemptLedger, FailureReason, HostCapability, WorkflowClass, WorkflowContext,
)
from workflow_kernel.policies import RetryPolicy, validate_canonical_policy_schema
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.workflows import WorkflowTemplates


class RetryPolicyTests(unittest.TestCase):
    def test_each_normalized_reason_uses_its_own_budget(self):
        policy = RetryPolicy()
        budgets = {
            FailureReason.PROVIDER_UNAVAILABLE: 2,
            FailureReason.DETERMINISTIC_VALIDATION_FAILURE: 1,
            FailureReason.REVIEWER_FINDING: 3,
            FailureReason.BROWSER_RECOVERY: 1,
            FailureReason.CLEANUP: 2,
            FailureReason.INFRASTRUCTURE: 1,
        }
        self.assertEqual(set(budgets), set(FailureReason))
        for reason, budget in budgets.items():
            with self.subTest(reason=reason.value):
                allowed = policy.decide(reason, AttemptLedger({reason: budget - 1}), None)
                blocked = policy.decide(reason, AttemptLedger({reason: budget}), None)
                self.assertTrue(allowed.allowed)
                self.assertEqual(allowed.budget, budget)
                self.assertFalse(blocked.allowed)
                self.assertEqual(blocked.reason_code, "retry_budget_exhausted")

    def test_identical_signature_converges_before_unrelated_budget_is_spent(self):
        policy = RetryPolicy()
        ledger = AttemptLedger(
            {FailureReason.REVIEWER_FINDING: 2},
            {FailureReason.REVIEWER_FINDING: ("same", "same")},
        )
        decision = policy.decide(FailureReason.REVIEWER_FINDING, ledger, "same")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_code, "identical_failure_convergence")
        self.assertEqual(decision.prior_signature, "same")
        self.assertEqual(decision.attempt_count, 2)
        self.assertEqual(decision.budget, 3)
        self.assertEqual(ledger.count(FailureReason.PROVIDER_UNAVAILABLE), 0)

    def test_policy_decisions_do_not_mutate_proposal_only_economics_or_policy_file(self):
        source = Path(__file__).parents[1] / "workflow-policy.json"
        before = source.read_bytes()
        policy = RetryPolicy(source)
        self.assertEqual(policy.economics_mode, "proposal_only")
        policy.decide(FailureReason.PROVIDER_UNAVAILABLE, AttemptLedger(), "provider-down")
        WorkflowTemplates().expand(
            WorkflowClass.CHORE,
            WorkflowContext(requested_executor="codex", economics_preference="cheapest"),
        )
        self.assertEqual(source.read_bytes(), before)

    def test_invalid_policy_version_fails_closed(self):
        source = Path(__file__).parents[1] / "workflow-policy.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["schema_version"] = 99
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                RetryPolicy(path)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unsupported_policy_version"),
        )

    def test_attempt_ledger_rejects_history_without_matching_attempt_count(self):
        invalid = (
            ({}, {FailureReason.REVIEWER_FINDING: ("same",)}),
            ({FailureReason.REVIEWER_FINDING: 1},
             {FailureReason.REVIEWER_FINDING: ("same", "same")}),
        )
        for counts, signatures in invalid:
            with self.subTest(counts=counts), self.assertRaises(InvalidSchemaError) as raised:
                AttemptLedger(counts, signatures)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_attempt_ledger"),
            )

    def test_runtime_rejects_duplicate_capability_names_like_json_schema(self):
        source = Path(__file__).parents[1] / "workflow-policy.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["capability_names"].append(payload["capability_names"][0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                RetryPolicy(path)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("duplicate_capability_name"),
        )

    def test_policy_schema_and_runtime_require_exactly_thirteen_capabilities(self):
        root = Path(__file__).parents[1]
        schema = json.loads((root / "workflow-policy-schema.json").read_text())
        capability_schema = schema["properties"]["capability_names"]
        self.assertEqual(capability_schema["minItems"], 13)
        self.assertEqual(capability_schema["maxItems"], 13)
        self.assertTrue(capability_schema["uniqueItems"])
        self.assertEqual(
            set(capability_schema["items"]["enum"]),
            {value.value for value in HostCapability},
        )
        payload = json.loads((root / "workflow-policy.json").read_text())
        self.assertEqual(len(payload["capability_names"]), 13)
        payload["capability_names"].pop()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                RetryPolicy(path)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unknown_capability_name"),
        )

    def test_canonical_policy_is_validated_against_schema_with_stdlib_only(self):
        root = Path(__file__).parents[1]
        validate_canonical_policy_schema()
        schema = json.loads((root / "workflow-policy-schema.json").read_text())
        schema["properties"]["capability_names"]["maxItems"] = 12
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.json"
            path.write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                validate_canonical_policy_schema(
                    root / "workflow-policy.json", path,
                )
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("policy_schema_mismatch"),
        )


if __name__ == "__main__":
    unittest.main()
