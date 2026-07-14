import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from tests import detail_digest, schema_matches
import workflow_kernel.adapters.base as adapter_base
from workflow_kernel.adapters.base import (
    AttemptLedger, FailureReason, HostCapability, WorkflowClass, WorkflowContext,
)
import workflow_kernel.policies as policy_module
from workflow_kernel.policies import GatePolicy, RetryPolicy, load_policy
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.workflows import WorkflowTemplates


class RetryPolicyTests(unittest.TestCase):
    def test_attempt_ledger_accessors_normalize_before_mapping_lookup(self):
        ledger = AttemptLedger(
            {FailureReason.CLEANUP: 1},
            {FailureReason.CLEANUP: ("first",)},
        )
        for reason in (FailureReason.CLEANUP, "cleanup"):
            with self.subTest(reason=reason):
                self.assertEqual(ledger.count(reason), 1)
                self.assertEqual(ledger.history(reason), ("first",))

        calls = []

        class EnumImpostor:
            def __hash__(self):
                calls.append("hash")
                raise RuntimeError("sk-secret-ledger-hash")

            def __eq__(self, other):
                calls.append("equal")
                raise RuntimeError("sk-secret-ledger-equal")

        class FatalImpostor:
            def __hash__(self):
                calls.append("fatal_hash")
                raise FatalLookup()

            def __eq__(self, other):
                calls.append("fatal_equal")
                raise FatalLookup()

        class FatalLookup(BaseException):
            pass

        for method in (ledger.count, ledger.history):
            for value in (EnumImpostor(), FatalImpostor()):
                with self.subTest(method=method.__name__, value=type(value).__name__):
                    with self.assertRaises(InvalidSchemaError) as raised:
                        method(value)
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("unknown_failure_reason"),
                    )
        self.assertEqual(calls, [])

    def test_attempt_ledger_accessor_snapshot_exceptions_are_normalized(self):
        class HostileMapping(dict):
            def items(self):
                raise RuntimeError("sk-secret-ledger-items")

        class FatalLookup(BaseException):
            pass

        class FatalMapping(dict):
            def items(self):
                raise FatalLookup()

        for method_name in ("count", "history"):
            hostile = AttemptLedger()
            object.__setattr__(hostile, "counts", HostileMapping())
            with self.subTest(method=method_name, failure="ordinary"):
                with self.assertRaises(InvalidSchemaError) as raised:
                    getattr(hostile, method_name)(FailureReason.CLEANUP)
                self.assertNotIn("sk-secret-ledger-items", repr(raised.exception))

            fatal = AttemptLedger()
            object.__setattr__(fatal, "counts", FatalMapping())
            with self.subTest(method=method_name, failure="base"):
                with self.assertRaises(FatalLookup):
                    getattr(fatal, method_name)(FailureReason.CLEANUP)

    def test_retry_reason_enum_impostors_are_rejected_without_equality_dispatch(self):
        secret = "sk-secret-retry-detail"
        calls = []

        class Hostile:
            def __eq__(self, other):
                calls.append("ordinary")
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as raised:
            RetryPolicy().decide(Hostile(), AttemptLedger(), None)
        self.assertNotIn(secret, repr(raised.exception))

        class FatalConversion(BaseException):
            pass

        class Fatal:
            def __eq__(self, other):
                calls.append("fatal")
                raise FatalConversion()

        with self.assertRaises(InvalidSchemaError):
            RetryPolicy().decide(Fatal(), AttemptLedger(), None)
        self.assertEqual(calls, [])

    def test_retry_decision_snapshots_attempt_ledger_exactly_once(self):
        snapshots = []
        original = adapter_base._snapshot_attempt_ledger

        def snapshot(value):
            snapshots.append(value)
            return original(value)

        with (
            patch.object(policy_module, "_snapshot_attempt_ledger", side_effect=snapshot),
            patch.object(adapter_base, "_snapshot_attempt_ledger", side_effect=snapshot),
        ):
            RetryPolicy().decide(
                FailureReason.REVIEWER_FINDING,
                AttemptLedger(
                    {FailureReason.REVIEWER_FINDING: 1},
                    {FailureReason.REVIEWER_FINDING: ("signature",)},
                ),
                "next-signature",
            )
        self.assertEqual(len(snapshots), 1)

    def test_gate_evidence_iterator_failures_are_secret_safe(self):
        secret = "sk-secret-gate-detail"

        class HostileTuple(tuple):
            def __iter__(self):
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as raised:
            GatePolicy().decide(
                WorkflowClass.CHORE, "evidence", HostileTuple(), WorkflowContext(),
            )
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_gate_evidence"),
        )
        self.assertNotIn(secret, repr(raised.exception))

        class FatalIteration(BaseException):
            pass

        class FatalTuple(tuple):
            def __iter__(self):
                raise FatalIteration()

        with self.assertRaises(FatalIteration):
            GatePolicy().decide(
                WorkflowClass.CHORE, "evidence", FatalTuple(), WorkflowContext(),
            )

    def test_file_and_injected_policy_share_canonical_normalization(self):
        root = Path(__file__).parents[1]
        source = root / "workflow-policy.json"
        canonical_payload = json.loads(source.read_text(encoding="utf-8"))
        document = load_policy(source)

        cases = []
        bad_budget_payload = json.loads(json.dumps(canonical_payload))
        bad_budget_payload["retry"]["budgets"]["cleanup"] = True
        bad_budgets = dict(document.retry_budgets)
        bad_budgets[FailureReason.CLEANUP] = True
        cases.append((
            bad_budget_payload,
            replace(document, retry_budgets=MappingProxyType(bad_budgets)),
        ))

        bad_limit_payload = json.loads(json.dumps(canonical_payload))
        bad_limit_payload["retry"]["identical_signature_limit"] = 1
        cases.append((
            bad_limit_payload,
            replace(document, identical_signature_limit=1),
        ))

        missing_classes_payload = json.loads(json.dumps(canonical_payload))
        del missing_classes_payload["workflow_safety_anchor"]["classes"]
        missing_classes_anchor = dict(document.workflow_safety_anchor)
        del missing_classes_anchor["classes"]
        cases.append((
            missing_classes_payload,
            replace(
                document,
                workflow_safety_anchor=MappingProxyType(missing_classes_anchor),
            ),
        ))

        bad_stage_payload = json.loads(json.dumps(canonical_payload))
        bad_stage_payload["workflow_safety_anchor"]["common"]["stages"][0][
            "required_evidence"
        ] = [""]
        bad_stage_anchor = dict(document.workflow_safety_anchor)
        bad_common = [dict(stage) for stage in bad_stage_anchor["common"]]
        bad_common[0]["required_evidence"] = ("",)
        bad_stage_anchor["common"] = tuple(
            MappingProxyType(stage) for stage in bad_common
        )
        cases.append((
            bad_stage_payload,
            replace(
                document,
                workflow_safety_anchor=MappingProxyType(bad_stage_anchor),
            ),
        ))

        non_iterable_downgrade_payload = json.loads(json.dumps(canonical_payload))
        non_iterable_downgrade_payload["isolation"]["forbidden_downgrades"] = None
        cases.append((
            non_iterable_downgrade_payload,
            replace(document, forbidden_downgrades=None),
        ))

        hostile_downgrade_payload = json.loads(json.dumps(canonical_payload))
        hostile_downgrade_payload["isolation"]["forbidden_downgrades"] = {}

        class HostileDowngrades(dict):
            def __iter__(self):
                raise RuntimeError("sk-secret-downgrade-detail")

        cases.append((
            hostile_downgrade_payload,
            replace(document, forbidden_downgrades=HostileDowngrades()),
        ))

        for payload, injected in cases:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as file_error:
                    load_policy(path)
            with self.assertRaises(InvalidSchemaError) as injected_error:
                GatePolicy(policy_document=injected)
            self.assertEqual(
                injected_error.exception.details["reason_code"],
                file_error.exception.details["reason_code"],
            )
            self.assertNotIn(
                "sk-secret-downgrade-detail", repr(injected_error.exception),
            )

    def test_policy_origin_seal_never_executes_malformed_nested_containers(self):
        source = Path(__file__).parents[1] / "workflow-policy.json"
        canonical_payload = json.loads(source.read_text(encoding="utf-8"))
        document = load_policy(source)
        calls = []

        class FatalTraversal(BaseException):
            pass

        class HostileList(list):
            def __iter__(self):
                calls.append("list_iter")
                raise RuntimeError("sk-secret-list-iter")

            def __repr__(self):
                calls.append("list_repr")
                raise RuntimeError("sk-secret-list-repr")

        class FatalList(list):
            def __iter__(self):
                calls.append("fatal_list_iter")
                raise FatalTraversal()

            def __repr__(self):
                calls.append("fatal_list_repr")
                raise FatalTraversal()

        class HostileDict(dict):
            def items(self):
                calls.append("dict_items")
                raise RuntimeError("sk-secret-dict-items")

            def __iter__(self):
                calls.append("dict_iter")
                raise RuntimeError("sk-secret-dict-iter")

        class HostileTuple(tuple):
            def __iter__(self):
                calls.append("tuple_iter")
                raise RuntimeError("sk-secret-tuple-iter")

            def __repr__(self):
                calls.append("tuple_repr")
                raise RuntimeError("sk-secret-tuple-repr")

        cases = []
        bad_forbidden = json.loads(json.dumps(canonical_payload))
        bad_forbidden["isolation"]["forbidden_downgrades"] = [{"bad": 1}]
        cases.append((
            bad_forbidden,
            {"forbidden_downgrades": HostileList([{"bad": 1}])},
        ))

        fatal_forbidden = json.loads(json.dumps(canonical_payload))
        fatal_forbidden["isolation"]["forbidden_downgrades"] = [{"bad": 1}]
        cases.append((
            fatal_forbidden,
            {"forbidden_downgrades": FatalList([{"bad": 1}])},
        ))

        bad_budgets = json.loads(json.dumps(canonical_payload))
        bad_budgets["retry"]["budgets"] = {}
        cases.append((bad_budgets, {"retry_budgets": HostileDict()}))

        bad_order = json.loads(json.dumps(canonical_payload))
        bad_order["isolation"]["order"] = ["remote_sandbox"]
        cases.append((
            bad_order,
            {"isolation_order": HostileTuple(("remote_sandbox",))},
        ))

        non_iterable = json.loads(json.dumps(canonical_payload))
        non_iterable["isolation"]["forbidden_downgrades"] = None
        cases.append((non_iterable, {"forbidden_downgrades": None}))

        for payload, changes in cases:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as file_error:
                    load_policy(path)
            injected = replace(document, **changes)
            with self.assertRaises(InvalidSchemaError) as injected_error:
                GatePolicy(policy_document=injected)
            self.assertEqual(
                injected_error.exception.details["reason_code"],
                file_error.exception.details["reason_code"],
            )
        self.assertEqual(calls, [])

    def test_policy_structural_origin_detects_normal_and_malformed_mutation(self):
        document = load_policy()
        object.__setattr__(document, "economics_mode", "automatic")
        with self.assertRaises(InvalidSchemaError) as normal_error:
            GatePolicy(policy_document=document)
        self.assertEqual(
            normal_error.exception.details["reason_code"],
            detail_digest("invalid_policy_document"),
        )

        mutable = replace(load_policy(), forbidden_downgrades=[])
        mutable.forbidden_downgrades.append({"bad": 1})
        with self.assertRaises(InvalidSchemaError) as malformed_error:
            GatePolicy(policy_document=mutable)
        self.assertEqual(
            malformed_error.exception.details["reason_code"],
            detail_digest("invalid_policy_document"),
        )

    def test_attempt_ledger_seal_cannot_be_spoofed(self):
        ledger = AttemptLedger({FailureReason.CLEANUP: 1})
        rewritten = MappingProxyType({FailureReason.CLEANUP: 0})
        object.__setattr__(ledger, "counts", rewritten)
        object.__setattr__(ledger, "_origin_seal", "spoofed")
        with self.assertRaises(InvalidSchemaError) as raised:
            RetryPolicy().decide(FailureReason.CLEANUP, ledger, None)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_attempt_ledger"),
        )

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

    def test_retry_policy_revalidates_mutated_attempt_ledger(self):
        ledger = AttemptLedger()
        object.__setattr__(ledger, "counts", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            RetryPolicy().decide(FailureReason.CLEANUP, ledger, None)
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

    def test_canonical_policy_schema_coherence_lives_in_tests_not_runtime(self):
        root = Path(__file__).parents[1]
        self.assertFalse(hasattr(policy_module, "_matches_schema"))
        self.assertFalse(hasattr(policy_module, "validate_canonical_policy_schema"))
        payload = json.loads((root / "workflow-policy.json").read_text())
        schema = json.loads((root / "workflow-policy-schema.json").read_text())
        self.assertTrue(schema_matches(payload, schema))
        root_keys = set(schema["required"])
        self.assertEqual(set(payload), root_keys)
        capability_schema = schema["properties"]["capability_names"]
        self.assertEqual(len(payload["capability_names"]), capability_schema["minItems"])
        self.assertEqual(len(payload["capability_names"]), capability_schema["maxItems"])
        self.assertEqual(
            set(payload["capability_names"]), set(capability_schema["items"]["enum"]),
        )
        invalid = json.loads(json.dumps(payload))
        invalid["retry"]["budgets"]["cleanup"] = "two"
        self.assertFalse(schema_matches(invalid, schema))

    def test_policy_schema_and_runtime_validate_the_safety_anchor_shape(self):
        root = Path(__file__).parents[1]
        payload = json.loads((root / "workflow-policy.json").read_text())
        schema = json.loads((root / "workflow-policy-schema.json").read_text())
        self.assertTrue(schema_matches(payload, schema))
        mutations = []
        boolean_version = json.loads(json.dumps(payload))
        boolean_version["workflow_safety_anchor"]["schema_version"] = True
        mutations.append(boolean_version)
        missing_override = json.loads(json.dumps(payload))
        del missing_override["workflow_safety_anchor"]["classes"]["hotfix"][
            "stages"
        ][0]["executor_overridable"]
        mutations.append(missing_override)
        impossible_tuple = json.loads(json.dumps(payload))
        stage = next(
            item for item in impossible_tuple["workflow_safety_anchor"]["classes"][
                "hotfix"
            ]["stages"] if item["id"] == "review"
        )
        stage["required_dispatch_capability"] = "companion_dispatch"
        mutations.append(impossible_tuple)
        for mutation in mutations:
            self.assertFalse(schema_matches(mutation, schema))
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(mutation), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError):
                    load_policy(path)


if __name__ == "__main__":
    unittest.main()
