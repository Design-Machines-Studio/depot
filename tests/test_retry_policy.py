import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from tests import KERNEL_REFERENCES
from tests import detail_digest, json_document_boundary_corpus, schema_matches
import workflow_kernel.model as kernel_model
from workflow_kernel.model import (
    AttemptLedger, FailureReason, HostCapability, IsolationMode, WorkflowClass,
    WorkflowContext,
)
import workflow_kernel.policies as policy_module
from workflow_kernel.policies import GatePolicy, RetryPolicy, load_policy
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.workflows import WorkflowTemplates


class RetryPolicyTests(unittest.TestCase):
    def test_policy_viewport_validation_is_local_and_layer_independent(self):
        package = KERNEL_REFERENCES / "workflow_kernel"
        policies = (package / "policies.py").read_text()
        self.assertIn("def _validate_policy_viewport", policies)
        self.assertNotIn("from .verification import validate_viewport", policies)

        environment = dict(os.environ, PYTHONPATH=str(package.parent))
        result = subprocess.run(
            [
                sys.executable, "-c",
                "import sys\n"
                "import workflow_kernel.policies\n"
                "assert 'workflow_kernel.verification' not in sys.modules\n"
                "assert 'workflow_kernel.adapters.personas' not in sys.modules\n",
            ],
            cwd="/tmp", env=environment, capture_output=True, text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_policy_value_classifier_has_one_exact_type_taxonomy(self):
        document = load_policy()
        trusted = document.retry_budgets
        cases = (
            (None, "scalar"),
            (True, "scalar"),
            (1, "scalar"),
            ("value", "scalar"),
            (FailureReason.CLEANUP, "enum"),
            ({}, "dict"),
            ([], "list"),
            ((), "tuple"),
            (set(), "set"),
            (frozenset(), "frozenset"),
            (trusted, "trusted_map"),
            (MappingProxyType({}), "untrusted_mappingproxy"),
            (object(), "other"),
        )
        for value, expected in cases:
            with self.subTest(value_type=type(value).__name__):
                self.assertEqual(
                    policy_module._classify_policy_value(value), expected,
                )

        class DictSubclass(dict):
            pass

        class StringSubclass(str):
            pass

        self.assertEqual(
            policy_module._classify_policy_value(DictSubclass()), "other",
        )
        self.assertEqual(
            policy_module._classify_policy_value(StringSubclass("value")),
            "other",
        )

    def test_normalized_policy_maps_are_trusted_immutable_mappings(self):
        document = load_policy()
        budgets = document.retry_budgets
        self.assertIs(type(budgets), policy_module._TrustedPolicyMap)
        self.assertIsInstance(budgets, Mapping)
        self.assertEqual(len(budgets), len(FailureReason))
        self.assertEqual(
            budgets[FailureReason.CLEANUP],
            dict(budgets.items())[FailureReason.CLEANUP],
        )
        self.assertEqual(tuple(budgets), tuple(dict(budgets)))
        self.assertEqual(
            budgets.get(FailureReason.CLEANUP),
            document.retry_budgets[FailureReason.CLEANUP],
        )
        self.assertIn(FailureReason.CLEANUP, budgets)
        self.assertNotIn("unknown", budgets)
        self.assertEqual(budgets, dict(budgets))
        self.assertFalse(budgets != dict(budgets))
        self.assertFalse(hasattr(budgets, "__dict__"))
        with self.assertRaises(TypeError):
            budgets[FailureReason.CLEANUP] = 999
        for mutate in (
            lambda: setattr(budgets, "_items", ()),
            lambda: object.__setattr__(budgets, "_items", ()),
            lambda: object.__setattr__(budgets, "extra", ()),
        ):
            with self.subTest(mutate=mutate):
                with self.assertRaises((AttributeError, TypeError)):
                    mutate()

        anchor = document.workflow_safety_anchor
        self.assertIs(type(anchor), policy_module._TrustedPolicyMap)
        self.assertIs(type(anchor["classes"]), policy_module._TrustedPolicyMap)
        self.assertIs(
            type(anchor["common"][0]), policy_module._TrustedPolicyMap,
        )

    def test_policy_decisions_are_stable_after_map_mutation_attempts(self):
        retry = RetryPolicy()
        budgets = retry._policy.retry_budgets
        rewritten = tuple(
            (reason, 999 if reason is FailureReason.CLEANUP else budget)
            for reason, budget in budgets.items()
        )
        before_retry = retry.decide(
            FailureReason.CLEANUP, AttemptLedger(), None,
        )
        with self.assertRaises((AttributeError, TypeError)):
            object.__setattr__(budgets, "_items", rewritten)
        self.assertEqual(
            retry.decide(FailureReason.CLEANUP, AttemptLedger(), None),
            before_retry,
        )

        gate = GatePolicy()
        anchor = gate._policy.workflow_safety_anchor
        before_gate = gate.decide(
            WorkflowClass.CHORE, "risk", (), WorkflowContext(risk="high"),
        )
        with self.assertRaises((AttributeError, TypeError)):
            object.__setattr__(anchor, "_items", ())
        self.assertEqual(
            gate.decide(
                WorkflowClass.CHORE, "risk", (), WorkflowContext(risk="high"),
            ),
            before_gate,
        )

    def test_unordered_containers_are_rejected_for_ordered_policy_fields(self):
        document = load_policy()
        anchor = dict(document.workflow_safety_anchor)
        common = [dict(stage) for stage in anchor["common"]]
        common[0]["required_evidence"] = {"cleanup_receipt"}
        anchor["common"] = tuple(common)
        cases = (
            (
                {"isolation_order": set(IsolationMode)},
                "invalid_isolation_order",
            ),
            (
                {"risk_human_approval": frozenset({"high", "critical"})},
                "invalid_gate_policy",
            ),
            (
                {"workflow_safety_anchor": anchor},
                "invalid_workflow_safety_anchor",
            ),
        )
        for changes, reason in cases:
            with self.subTest(field=next(iter(changes))):
                with self.assertRaises(InvalidSchemaError) as raised:
                    GatePolicy(policy_document=replace(document, **changes))
                self.assertEqual(
                    raised.exception.details["reason_code"], detail_digest(reason),
                )

        GatePolicy(policy_document=replace(
            document,
            forbidden_downgrades=frozenset(document.forbidden_downgrades),
        ))

    def test_file_and_injected_anchor_share_the_actual_item_budget(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["workflow_safety_anchor"]["common"]["stages"][0][
            "required_evidence"
        ] = [
            f"near-limit-{index}"
            for index in range(policy_module.MAX_PAYLOAD_ITEMS - 1_000)
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "near-limit-policy.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            document = load_policy(path)

        injected = GatePolicy(policy_document=document)._policy
        self.assertEqual(
            policy_module._policy_origin_primitives(
                injected.workflow_safety_anchor,
            ),
            policy_module._policy_origin_primitives(
                document.workflow_safety_anchor,
            ),
        )

    def test_caller_mapping_proxies_are_rejected_without_backing_traversal(self):
        document = load_policy()
        backing = dict(document.retry_budgets)
        injected = replace(
            document, retry_budgets=MappingProxyType(backing),
        )
        for budget in (document.retry_budgets[FailureReason.CLEANUP], 999):
            backing[FailureReason.CLEANUP] = budget
            with self.subTest(budget=budget):
                with self.assertRaises(InvalidSchemaError) as raised:
                    GatePolicy(policy_document=injected)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_retry_policy"),
                )

        calls = []

        class FatalTraversal(BaseException):
            pass

        class HostileBacking(dict):
            def items(self):
                calls.append("ordinary_items")
                raise RuntimeError("sk-secret-proxy-items")

            def __iter__(self):
                calls.append("ordinary_iter")
                raise RuntimeError("sk-secret-proxy-iter")

        class FatalBacking(dict):
            def items(self):
                calls.append("fatal_items")
                raise FatalTraversal()

            def __iter__(self):
                calls.append("fatal_iter")
                raise FatalTraversal()

        class FatalMapping(Mapping):
            def __getitem__(self, key):
                calls.append("mapping_getitem")
                raise FatalTraversal()

            def __iter__(self):
                calls.append("mapping_iter")
                raise FatalTraversal()

            def __len__(self):
                calls.append("mapping_len")
                raise FatalTraversal()

        hostile_values = (
            MappingProxyType(HostileBacking(backing)),
            MappingProxyType(FatalBacking(backing)),
            FatalMapping(),
        )
        for value in hostile_values:
            hostile = replace(document, retry_budgets=value)
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(InvalidSchemaError) as raised:
                    GatePolicy(policy_document=hostile)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_retry_policy"),
                )
        self.assertEqual(calls, [])

    def test_policy_structure_bounds_cycles_depth_and_aggregate_items(self):
        from workflow_kernel import redaction

        self.assertEqual(policy_module.MAX_PAYLOAD_DEPTH, redaction.MAX_PAYLOAD_DEPTH)
        self.assertEqual(policy_module.MAX_PAYLOAD_ITEMS, redaction.MAX_PAYLOAD_ITEMS)
        document = load_policy()

        cyclic = []
        cyclic.append(cyclic)
        deep = []
        for _ in range(1_500):
            deep = [deep]
        for value in (cyclic, deep):
            with self.subTest(shape="cycle" if value is cyclic else "deep"):
                with self.assertRaises(InvalidSchemaError) as raised:
                    replace(document, forbidden_downgrades=value)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_policy_document"),
                )

        with patch.object(policy_module, "MAX_PAYLOAD_ITEMS", 8, create=True):
            with self.assertRaises(InvalidSchemaError) as raised:
                replace(document, forbidden_downgrades=[None] * 20)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_policy_document"),
        )

        payload = json.loads(
            (KERNEL_REFERENCES / "workflow-policy.json").read_text(
                encoding="utf-8",
            )
        )
        payload["economics"]["mode"] = cyclic
        with self.assertRaises(InvalidSchemaError) as raised:
            policy_module._normalize_policy_payload(payload)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_policy_document"),
        )

        with tempfile.TemporaryDirectory() as directory:
            deep_path = Path(directory) / "deep-policy.json"
            deep_path.write_text(
                '{"nested":' + "[" * 1_500 + "0" + "]" * 1_500 + "}",
                encoding="utf-8",
            )
            with self.assertRaises(InvalidSchemaError) as raised:
                load_policy(deep_path)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_policy_document"),
            )

            wide_payload = json.loads(
                (KERNEL_REFERENCES / "workflow-policy.json").read_text(
                    encoding="utf-8",
                )
            )
            wide_payload["gates"]["risk_human_approval"] = (
                [None] * (redaction.MAX_PAYLOAD_ITEMS + 1)
            )
            wide_path = Path(directory) / "wide-policy.json"
            wide_path.write_text(json.dumps(wide_payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                load_policy(wide_path)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_policy_document"),
            )

    def test_policy_json_loader_has_explicit_parser_boundaries(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
        canonical = source.read_text(encoding="utf-8")
        self.assertFalse(hasattr(policy_module, "_load_json_document"))
        self.assertIsNotNone(importlib.util.find_spec("workflow_kernel.limits"))
        limits = importlib.import_module("workflow_kernel.limits")
        loader = limits.load_json_document
        depth_error = limits.JSONDocumentDepthError
        syntax_error = limits.JSONDocumentSyntaxError
        max_depth = limits.MAX_JSON_DOCUMENT_DEPTH

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = json_document_boundary_corpus(
                canonical,
                json_reason="invalid_policy_json",
                document_reason="invalid_policy_document",
                version_reason="unsupported_policy_version",
            )
            for name, (content, reason) in documents.items():
                path = root / f"{name}.json"
                path.write_text(content, encoding="utf-8")
                with self.subTest(name=name), self.assertRaises(
                    InvalidSchemaError,
                ) as raised:
                    load_policy(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest(reason),
                )

            boundary = root / "boundary.json"
            boundary.write_text(
                "[" * max_depth + "0" + "]" * max_depth,
                encoding="utf-8",
            )
            parsed = loader(boundary)
            for _ in range(max_depth):
                self.assertIs(type(parsed), list)
                self.assertEqual(len(parsed), 1)
                parsed = parsed[0]
            self.assertEqual(parsed, 0)

            over_boundary = root / "over-boundary.json"
            over_boundary.write_text(
                "[" * (max_depth + 1) + "0" + "]" * (max_depth + 1),
                encoding="utf-8",
            )
            with self.assertRaises(depth_error):
                loader(over_boundary)

            escaped = root / "escaped.json"
            literal = '\\"' + "[{" * (max_depth + 10) + "}]"
            escaped.write_text(json.dumps({"literal": literal}), encoding="utf-8")
            self.assertEqual(loader(escaped), {"literal": literal})

            integer_boundary = root / "integer-boundary.json"
            integer_boundary.write_text(
                "-" + "9" * limits.MAX_JSON_INTEGER_DIGITS,
                encoding="utf-8",
            )
            parsed_integer = loader(integer_boundary)
            self.assertLess(parsed_integer, 0)
            digit_count = 0
            remaining = abs(parsed_integer)
            while remaining:
                remaining //= 10
                digit_count += 1
            self.assertEqual(digit_count, limits.MAX_JSON_INTEGER_DIGITS)

            mismatched = root / "mismatched.json"
            mismatched.write_text("{]", encoding="utf-8")
            with self.assertRaises(syntax_error):
                loader(mismatched)

            constant = root / "constant.json"
            constant.write_text("NaN", encoding="utf-8")
            with patch.object(limits, "_scan_json_document", return_value=False):
                with self.assertRaises(ValueError):
                    loader(constant)

        self.assertEqual(load_policy(source), load_policy())

    def test_large_policy_and_class_integers_ignore_interpreter_digit_limits(self):
        if not hasattr(sys, "set_int_max_str_digits"):
            self.skipTest("interpreter integer digit controls unavailable")
        root = KERNEL_REFERENCES
        policy = (root / "workflow-policy.json").read_text(encoding="utf-8")
        classes = (root / "workflow-classes.json").read_text(encoding="utf-8")
        cases = (
            ("policy", policy, load_policy),
            ("classes", classes, WorkflowTemplates),
        )
        original = sys.get_int_max_str_digits()
        try:
            for digit_limit in (640, 0):
                sys.set_int_max_str_digits(digit_limit)
                for name, canonical, load in cases:
                    document = canonical.replace(
                        '"schema_version": 1',
                        '"schema_version": ' + "9" * 1_000,
                        1,
                    )
                    with self.subTest(limit=digit_limit, loader=name), \
                            tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / f"{name}.json"
                        path.write_text(document, encoding="utf-8")
                        with self.assertRaises(InvalidSchemaError) as raised:
                            load(path)
                        self.assertEqual(
                            raised.exception.details["reason_code"],
                            detail_digest("unsupported_policy_version"),
                        )
        finally:
            sys.set_int_max_str_digits(original)

    def test_economics_mode_requires_an_exact_proposal_only_string(self):
        document = load_policy()
        calls = []

        class FatalEquality(BaseException):
            pass

        class HostileString(str):
            def __eq__(self, other):
                calls.append("ordinary_string_equal")
                raise RuntimeError("sk-secret-economics-equal")

        class FatalString(str):
            def __eq__(self, other):
                calls.append("fatal_string_equal")
                raise FatalEquality()

        class HostileValue:
            def __eq__(self, other):
                calls.append("ordinary_value_equal")
                raise RuntimeError("sk-secret-economics-value")

        class FatalValue:
            def __eq__(self, other):
                calls.append("fatal_value_equal")
                raise FatalEquality()

        for value in (
            HostileString("proposal_only"), FatalString("proposal_only"),
            HostileValue(), FatalValue(), True, 1, None, "automatic",
        ):
            malformed = replace(document, economics_mode=value)
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(InvalidSchemaError) as raised:
                    GatePolicy(policy_document=malformed)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("economics_must_be_proposal_only"),
                )
                self.assertNotIn("sk-secret", repr(raised.exception))
        self.assertEqual(calls, [])

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
        original = kernel_model._snapshot_attempt_ledger

        def snapshot(value):
            snapshots.append(value)
            return original(value)

        with (
            patch.object(policy_module, "_snapshot_attempt_ledger", side_effect=snapshot),
            patch.object(kernel_model, "_snapshot_attempt_ledger", side_effect=snapshot),
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
        root = KERNEL_REFERENCES
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
            replace(document, retry_budgets=bad_budgets),
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
                workflow_safety_anchor=missing_classes_anchor,
            ),
        ))

        bad_stage_payload = json.loads(json.dumps(canonical_payload))
        bad_stage_payload["workflow_safety_anchor"]["common"]["stages"][0][
            "required_evidence"
        ] = [""]
        bad_stage_anchor = dict(document.workflow_safety_anchor)
        bad_common = [dict(stage) for stage in bad_stage_anchor["common"]]
        bad_common[0]["required_evidence"] = ("",)
        bad_stage_anchor["common"] = tuple(bad_common)
        cases.append((
            bad_stage_payload,
            replace(
                document,
                workflow_safety_anchor=bad_stage_anchor,
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

    def test_malformed_downgrade_tuples_reach_the_canonical_normalizer(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
        canonical_payload = json.loads(source.read_text(encoding="utf-8"))
        document = load_policy(source)
        cases = (
            (["remote_sandbox"], (IsolationMode.REMOTE_SANDBOX,)),
            (
                ["remote_sandbox", "container", "worktree"],
                (
                    IsolationMode.REMOTE_SANDBOX,
                    IsolationMode.CONTAINER,
                    IsolationMode.WORKTREE,
                ),
            ),
            (
                {"from": "remote_sandbox", "to": "unknown"},
                (IsolationMode.REMOTE_SANDBOX, "unknown"),
            ),
        )
        for file_item, injected_item in cases:
            payload = json.loads(json.dumps(canonical_payload))
            payload["isolation"]["forbidden_downgrades"] = [file_item]
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as file_error:
                    load_policy(path)
            injected = replace(
                document, forbidden_downgrades=frozenset({injected_item}),
            )
            with self.assertRaises(InvalidSchemaError) as injected_error:
                GatePolicy(policy_document=injected)
            self.assertEqual(
                injected_error.exception.details["reason_code"],
                file_error.exception.details["reason_code"],
            )

    def test_downgrade_shape_errors_precede_unknown_modes_in_every_order(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
        canonical_payload = json.loads(source.read_text(encoding="utf-8"))
        malformed = ["remote_sandbox"]
        unknown = {"from": "remote_sandbox", "to": "unknown"}
        for items in ([malformed, unknown], [unknown, malformed]):
            payload = json.loads(json.dumps(canonical_payload))
            payload["isolation"]["forbidden_downgrades"] = items
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    load_policy(path)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_isolation_policy"),
            )

        code = """
import json
from dataclasses import replace
from workflow_kernel.model import IsolationMode
from workflow_kernel.policies import GatePolicy, _policy_document_payload, load_policy
from workflow_kernel.schema import InvalidSchemaError
candidate = replace(load_policy(), forbidden_downgrades=frozenset({
    (IsolationMode.REMOTE_SANDBOX,),
    (IsolationMode.REMOTE_SANDBOX, 'unknown'),
}))
captured = (
    candidate.retry_budgets, candidate.identical_signature_limit,
    candidate.risk_human_approval, candidate.isolation_order,
    candidate.forbidden_downgrades, candidate.workflow_safety_anchor,
    candidate.economics_mode,
)
forbidden = _policy_document_payload(captured)['isolation']['forbidden_downgrades']
try:
    GatePolicy(policy_document=candidate)
except InvalidSchemaError as error:
    print(json.dumps({
        'forbidden': forbidden,
        'reason': error.details['reason_code'],
    }, sort_keys=True))
else:
    raise SystemExit('mixed downgrade policy accepted')
"""
        outputs = set()
        for seed in ("1", "2", "3", "4"):
            env = dict(os.environ)
            env.update({
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(KERNEL_REFERENCES),
            })
            result = subprocess.run(
                [sys.executable, "-c", code], check=True, capture_output=True,
                text=True, env=env,
            )
            outputs.add(result.stdout.strip())
        self.assertEqual(len(outputs), 1)
        self.assertEqual(
            json.loads(next(iter(outputs))), {
                "forbidden": [None],
                "reason": detail_digest("invalid_isolation_policy"),
            },
        )

    def test_downgrade_payload_and_document_order_are_canonical(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
        canonical_payload = json.loads(source.read_text(encoding="utf-8"))
        valid = [
            {"from": "remote_sandbox", "to": "container"},
            {"from": "container", "to": "worktree"},
        ]
        documents = []
        for items in (valid, list(reversed(valid))):
            payload = json.loads(json.dumps(canonical_payload))
            payload["isolation"]["forbidden_downgrades"] = items
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "policy.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                documents.append(load_policy(path))
        injected = GatePolicy(policy_document=replace(
            load_policy(source),
            forbidden_downgrades=frozenset({
                (IsolationMode.REMOTE_SANDBOX, IsolationMode.CONTAINER),
                (IsolationMode.CONTAINER, IsolationMode.WORKTREE),
            }),
        ))._policy
        self.assertEqual(documents[0], documents[1])
        self.assertEqual(documents[0], injected)

        code = """
import json
from dataclasses import replace
from workflow_kernel.model import IsolationMode
from workflow_kernel.policies import GatePolicy, _policy_document_payload, load_policy
from workflow_kernel.schema import InvalidSchemaError
document = replace(load_policy(), forbidden_downgrades=frozenset({
    ('z-unknown', 'container'),
    ('a-unknown', 'worktree'),
    (IsolationMode.CONTAINER, IsolationMode.WORKTREE),
    (IsolationMode.REMOTE_SANDBOX, IsolationMode.CONTAINER),
}))
captured = (
    document.retry_budgets, document.identical_signature_limit,
    document.risk_human_approval, document.isolation_order,
    document.forbidden_downgrades, document.workflow_safety_anchor,
    document.economics_mode,
)
forbidden = _policy_document_payload(captured)['isolation']['forbidden_downgrades']
try:
    GatePolicy(policy_document=document)
except InvalidSchemaError as error:
    print(json.dumps({
        'forbidden': forbidden,
        'reason': error.details['reason_code'],
    }, sort_keys=True))
else:
    raise SystemExit('unknown downgrade policy accepted')
"""
        outputs = set()
        for seed in ("1", "2", "3", "4"):
            env = dict(os.environ)
            env.update({
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(KERNEL_REFERENCES),
            })
            result = subprocess.run(
                [sys.executable, "-c", code], check=True, capture_output=True,
                text=True, env=env,
            )
            outputs.add(result.stdout.strip())
        self.assertEqual(len(outputs), 1)
        self.assertEqual(json.loads(next(iter(outputs))), {
            "forbidden": [
                {"from": "a-unknown", "to": "worktree"},
                {"from": "container", "to": "worktree"},
                {"from": "remote_sandbox", "to": "container"},
                {"from": "z-unknown", "to": "container"},
            ],
            "reason": detail_digest("unknown_isolation_mode"),
        })

    def test_policy_origin_seal_never_executes_malformed_nested_containers(self):
        source = KERNEL_REFERENCES / "workflow-policy.json"
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
        source = KERNEL_REFERENCES / "workflow-policy.json"
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
        source = KERNEL_REFERENCES / "workflow-policy.json"
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
        source = KERNEL_REFERENCES / "workflow-policy.json"
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
        root = KERNEL_REFERENCES
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
        root = KERNEL_REFERENCES
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
        root = KERNEL_REFERENCES
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
