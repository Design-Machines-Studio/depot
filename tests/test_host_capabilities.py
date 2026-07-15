import gc
import json
import inspect
import os
import subprocess
import sys
import tempfile
import unittest
import weakref
from unittest.mock import patch
from pathlib import Path
from typing import get_type_hints, Optional, Union

from tests import KERNEL_REFERENCES
from tests import (
    canonical_harness_profile, detail_digest, ignored_json_boundary_corpus,
    snapshot_during_validated_mutation,
)
import workflow_kernel.model as kernel_model
from workflow_kernel.model import (
    GateDecision, HostCapabilities, HostCapability, HostRoute, NodeSpec,
    WorkflowContext, route_satisfies_node,
)
from workflow_kernel.adapters.host import capabilities_from_harness_profile
from workflow_kernel.schema import InvalidSchemaError

class HostCapabilityTests(unittest.TestCase):
    def test_live_identities_cannot_be_resealed_through_post_init(self):
        route = HostRoute(
            "anthropic", HostCapability.ANTHROPIC_NATIVE_EXECUTION, "native",
        )
        object.__setattr__(route, "provider", "openai")
        object.__setattr__(route, "capability", HostCapability.CODEX_EXECUTION)
        with self.assertRaises(ValueError):
            route.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            _ = route.dispatch_capability

        node = NodeSpec(
            "security_build", executor="claude",
            required_capability=HostCapability.ANTHROPIC_NATIVE_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(node, "executor", "codex")
        object.__setattr__(node, "required_capability", HostCapability.CODEX_EXECUTION)
        with self.assertRaises(ValueError):
            node.__post_init__()
        self.assertFalse(route_satisfies_node(
            HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"), node,
        ))

        capabilities = HostCapabilities(
            "claude", (), routes=frozenset({
                HostRoute(
                    "anthropic", HostCapability.ANTHROPIC_NATIVE_EXECUTION,
                    "native",
                ),
            }),
        )
        object.__setattr__(capabilities, "capabilities", frozenset())
        object.__setattr__(capabilities, "routes", frozenset({
            HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
        }))
        with self.assertRaises(ValueError):
            capabilities.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            capabilities.supports_route(
                HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
            )

        context = kernel_model.ResumeStateContext(
            "run-1", "build", "attempt-1", "openai", "native",
            HostCapability.CODEX_EXECUTION,
        )
        object.__setattr__(context, "run_id", "run-2")
        with self.assertRaises(ValueError):
            context.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            context.to_dict()

        handle = kernel_model.SessionHandle(
            "codex", "opaque-one", "2026-07-14T00:00:00Z", True,
            kernel_model.ResumeStateContext(
                "run-1", "build", "attempt-1", "openai", "native",
                HostCapability.CODEX_EXECUTION,
            ),
        )
        object.__setattr__(handle, "opaque_handle", "opaque-two")
        with self.assertRaises(ValueError):
            handle.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            handle.to_dict()

    def test_identity_registry_allows_only_guarded_dead_entry_reuse(self):
        class Token:
            pass

        registry = kernel_model._IdentitySealRegistry()
        live = Token()
        registry.register(live, "Token", ("first",))
        with self.assertRaises(ValueError):
            registry.register(live, "Token", ("first",))
        with self.assertRaises(ValueError):
            registry.register(live, "Token", ("second",))

        stale_entry = registry._entries[id(live)]
        stale_callback = stale_entry[0].__callback__
        del live
        gc.collect()
        replacement = Token()
        registry._entries[id(replacement)] = stale_entry
        registry.register(replacement, "Token", ("replacement",))
        stale_callback(stale_entry[0])
        registry.validate(replacement, "Token", ("replacement",))

    def test_enum_impostors_are_rejected_without_hash_or_equality_dispatch(self):
        secret = "sk-secret-capability-detail"
        calls = []

        class Hostile:
            def __eq__(self, other):
                calls.append("equal")
                raise RuntimeError(secret)

        for field in ("required_capability", "required_dispatch_capability"):
            values = {
                "node_id": "build", "executor": "codex",
                "required_capability": HostCapability.CODEX_EXECUTION,
                "required_dispatch_capability": HostCapability.NATIVE_DISPATCH,
            }
            values[field] = Hostile()
            with self.subTest(field=field):
                with self.assertRaises(InvalidSchemaError) as raised:
                    NodeSpec(**values)
                self.assertNotIn(secret, repr(raised.exception))

        class FatalConversion(BaseException):
            pass

        class Fatal:
            def __eq__(self, other):
                calls.append("fatal_equal")
                raise FatalConversion()

        with self.assertRaises(InvalidSchemaError):
            NodeSpec(
                "build", executor="codex", required_capability=Fatal(),
                required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
            )

        class HostileHash:
            def __hash__(self):
                calls.append("hash")
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as hash_error:
            NodeSpec(
                "build", executor="codex", required_capability=HostileHash(),
                required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
            )
        self.assertNotIn(secret, repr(hash_error.exception))

        class FatalHash:
            def __hash__(self):
                calls.append("fatal_hash")
                raise FatalConversion()

        with self.assertRaises(InvalidSchemaError):
            NodeSpec(
                "build", executor="codex", required_capability=FatalHash(),
                required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
            )

        self.assertEqual(calls, [])

        class HostileIterable(tuple):
            def __iter__(self):
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as iterable_error:
            HostCapabilities("host", HostileIterable())
        self.assertNotIn(secret, repr(iterable_error.exception))

        class FatalIterable(tuple):
            def __iter__(self):
                raise FatalConversion()

        with self.assertRaises(FatalConversion):
            HostCapabilities("host", FatalIterable())

    def test_snapshots_reconstruct_only_from_one_validated_capture(self):
        context = WorkflowContext(risk="low")
        captured_context = snapshot_during_validated_mutation(
            context, kernel_model._snapshot_workflow_context,
            lambda: object.__setattr__(context, "risk", "high"),
        )
        self.assertEqual(captured_context.risk, "low")

        blocked = GateDecision(
            False, "missing_mandatory_evidence", ("review",),
        )
        node = NodeSpec(
            "build", gate_kind="evidence", required_evidence=("review",),
            executor="claude", gate_decision=blocked,
            required_capability=HostCapability.CLAUDE_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )

        def mutate_node():
            object.__setattr__(node, "executor", "codex")
            object.__setattr__(
                node, "required_capability", HostCapability.CODEX_EXECUTION,
            )
            object.__setattr__(node, "gate_decision", GateDecision(
                True, "gate_satisfied",
            ))

        captured_node = snapshot_during_validated_mutation(
            node, kernel_model._snapshot_node_spec, mutate_node,
        )
        self.assertEqual(captured_node.executor, "claude")
        self.assertFalse(captured_node.gate_decision.allowed)

        original_route = HostRoute(
            "anthropic", HostCapability.CLAUDE_EXECUTION, "native",
        )
        capabilities = HostCapabilities(
            "claude", (), routes=frozenset({original_route}),
        )
        stored_route = next(iter(capabilities.routes))

        def mutate_capabilities():
            object.__setattr__(capabilities, "host_name", "codex")
            object.__setattr__(stored_route, "provider", "openai")
            object.__setattr__(
                stored_route, "capability", HostCapability.CODEX_EXECUTION,
            )

        captured_capabilities = snapshot_during_validated_mutation(
            capabilities, kernel_model._snapshot_host_capabilities,
            mutate_capabilities,
        )
        self.assertEqual(captured_capabilities.host_name, "claude")
        self.assertEqual(
            next(iter(captured_capabilities.routes)).provider, "anthropic",
        )

    def test_module_owned_seals_reject_instance_field_spoofing(self):
        companion = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "codex_companion",
        )

        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        object.__setattr__(route, "rail", "codex_companion")
        object.__setattr__(
            route, "_origin_seal",
            ("openai", "codex_execution", "codex_companion"),
        )
        with self.assertRaises(InvalidSchemaError):
            _ = route.dispatch_capability

        node = NodeSpec(
            "security_build", executor="claude",
            required_capability=HostCapability.ANTHROPIC_NATIVE_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(node, "executor", "codex")
        object.__setattr__(node, "required_capability", HostCapability.CODEX_EXECUTION)
        object.__setattr__(
            node, "required_dispatch_capability", HostCapability.COMPANION_DISPATCH,
        )
        object.__setattr__(node, "_origin_seal", (
            "security_build", (), None, (), "codex", None,
            (True, "gate_not_required", (), False),
            "codex_execution", "companion_dispatch", False,
        ))
        self.assertFalse(route_satisfies_node(companion, node))

        aggregate = HostCapabilities(
            "codex", (), routes=(
                HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
            ),
        )
        stored = next(iter(aggregate.routes))
        object.__setattr__(stored, "rail", "codex_companion")
        object.__setattr__(stored, "_origin_seal", (
            "openai", "codex_execution", "codex_companion",
        ))
        rewritten = frozenset({
            HostCapability.CODEX_EXECUTION,
            HostCapability.COMPANION_DISPATCH,
        })
        object.__setattr__(aggregate, "capabilities", rewritten)
        object.__setattr__(aggregate, "_sealed_capabilities", rewritten)
        object.__setattr__(aggregate, "_sealed_routes", frozenset({
            ("openai", "codex_execution", "codex_companion"),
        }))
        with self.assertRaises(InvalidSchemaError):
            aggregate.supports_route(companion)

    def test_module_owned_seal_registry_releases_dead_identities(self):
        self.assertTrue(hasattr(kernel_model, "_origin_seal_registry_size"))
        before = kernel_model._origin_seal_registry_size()
        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        reference = weakref.ref(route)
        self.assertEqual(kernel_model._origin_seal_registry_size(), before + 1)
        del route
        gc.collect()
        self.assertIsNone(reference())
        self.assertLessEqual(kernel_model._origin_seal_registry_size(), before)

    def test_host_authorization_exposes_immutable_concrete_routes(self):
        self.assertTrue(hasattr(kernel_model, "HostRoute"))
        self.assertIn("routes", inspect.signature(HostCapabilities).parameters)

        explicit = HostCapabilities("test", (), routes=frozenset({
            HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
        }))
        self.assertEqual(explicit.capabilities, frozenset({
            HostCapability.CODEX_EXECUTION, HostCapability.NATIVE_DISPATCH,
        }))
        with self.assertRaises(TypeError):
            type("HostileRoute", (HostRoute,), {})

    def test_harness_routes_preserve_provider_capability_and_dispatch_coherence(self):
        claude = capabilities_from_harness_profile("claude-code", canonical_harness_profile())
        expected = {
            HostRoute("anthropic", HostCapability.CLAUDE_EXECUTION, "native"),
            HostRoute("anthropic", HostCapability.ANTHROPIC_NATIVE_EXECUTION, "native"),
            HostRoute("openai", HostCapability.CODEX_EXECUTION, "codex_companion"),
            HostRoute("openrouter", HostCapability.OPENROUTER_EXECUTION,
                      "openrouter_exec"),
        }
        self.assertTrue(expected.issubset(claude.routes))
        self.assertNotIn(
            HostRoute("openrouter", HostCapability.CLAUDE_EXECUTION,
                      "openrouter_exec"),
            claude.routes,
        )
        self.assertTrue(all(route.provider in {"anthropic", "openai", "openrouter"}
                            for route in claude.routes))

    def test_incoherent_or_credential_like_routes_fail_closed(self):
        cases = (
            ("sk-provider-secret", HostCapability.CODEX_EXECUTION, "native"),
            ("anthropic", HostCapability.CODEX_EXECUTION, "native"),
            ("openai", HostCapability.CODEX_EXECUTION, "wrapper"),
            ("openrouter", HostCapability.ANTHROPIC_NATIVE_EXECUTION,
             "openrouter_exec"),
        )
        for values in cases:
            with self.subTest(values=values), self.assertRaises(InvalidSchemaError):
                HostRoute(*values)

    def test_route_scoped_capabilities_are_derived_only_from_routes(self):
        route_scoped = {
            HostCapability.NATIVE_DISPATCH,
            HostCapability.COMPANION_DISPATCH,
            HostCapability.WRAPPER_DISPATCH,
            HostCapability.OPENROUTER_EXEC,
            HostCapability.CLAUDE_EXECUTION,
            HostCapability.CODEX_EXECUTION,
            HostCapability.OPENROUTER_EXECUTION,
            HostCapability.ANTHROPIC_NATIVE_EXECUTION,
        }
        for capability in route_scoped:
            with self.subTest(capability=capability):
                with self.assertRaises(InvalidSchemaError) as raised:
                    HostCapabilities("test", (capability,))
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("route_capability_requires_route"),
                )

    def test_host_route_properties_and_repr_revalidate_hostile_mutation(self):
        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        object.__setattr__(route, "rail", object())
        with self.assertRaises(InvalidSchemaError) as dispatch_rejected:
            _ = route.dispatch_capability
        self.assertEqual(
            dispatch_rejected.exception.details["reason_code"],
            detail_digest("invalid_host_route"),
        )
        with self.assertRaises(InvalidSchemaError):
            _ = route.agentic
        self.assertEqual(repr(route), "HostRoute([INVALID])")

        coherent = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "native",
        )
        object.__setattr__(coherent, "rail", "codex_companion")
        with self.assertRaises(InvalidSchemaError) as coherent_rejected:
            _ = coherent.dispatch_capability
        self.assertEqual(
            coherent_rejected.exception.details["reason_code"],
            detail_digest("invalid_host_route"),
        )
        self.assertEqual(repr(coherent), "HostRoute([INVALID])")

    def test_route_authorization_and_aggregate_snapshot_each_route_once(self):
        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        original = kernel_model._snapshot_host_route
        with patch.object(kernel_model, "_snapshot_host_route", wraps=original) as snapshot:
            capabilities = HostCapabilities("test", (), routes=(route,))
        self.assertEqual(snapshot.call_count, 1)
        node = NodeSpec(
            "build", executor="codex",
            required_capability=HostCapability.CODEX_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        original_node = kernel_model._snapshot_node_spec
        with patch.object(kernel_model, "_snapshot_host_route", wraps=original) as route_snapshot, \
                patch.object(kernel_model, "_snapshot_node_spec", wraps=original_node) as node_snapshot:
            self.assertTrue(route_satisfies_node(next(iter(capabilities.routes)), node))
        self.assertEqual(route_snapshot.call_count, 1)
        self.assertEqual(node_snapshot.call_count, 1)

    def test_route_authorization_rejects_mutated_incoherent_node(self):
        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        node = NodeSpec(
            "build", executor="codex",
            required_capability=HostCapability.CODEX_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(node, "executor", "claude")
        self.assertFalse(route_satisfies_node(route, node))

    def test_route_authorization_rejects_coherent_node_rewrite_and_hostile_iterable(self):
        node = NodeSpec(
            "security_build", executor="claude",
            required_capability=HostCapability.ANTHROPIC_NATIVE_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(node, "executor", "codex")
        object.__setattr__(node, "required_capability", HostCapability.CODEX_EXECUTION)
        object.__setattr__(
            node, "required_dispatch_capability", HostCapability.COMPANION_DISPATCH,
        )
        companion = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "codex_companion",
        )
        self.assertFalse(route_satisfies_node(companion, node))

        class HostileTuple(tuple):
            def __iter__(self):
                raise RuntimeError("provider-detail://credential")

        hostile = NodeSpec(
            "build", executor="codex",
            required_capability=HostCapability.CODEX_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        object.__setattr__(hostile, "dependencies", HostileTuple())
        try:
            accepted = route_satisfies_node(
                HostRoute("openai", HostCapability.CODEX_EXECUTION, "native"),
                hostile,
            )
        except Exception as raised:
            self.fail("route predicate leaked " + type(raised).__name__)
        self.assertFalse(accepted)

    def test_supports_revalidates_mutated_host_capabilities(self):
        capabilities = HostCapabilities("test", (HostCapability.WORKTREE,))
        object.__setattr__(capabilities, "capabilities", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            capabilities.supports(HostCapability.WORKTREE)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_host_capabilities"),
        )

    def test_supports_route_rejects_substituted_or_malformed_routes(self):
        original = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        substituted = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "codex_companion",
        )
        capabilities = HostCapabilities("test", (), routes=(original,))
        object.__setattr__(capabilities, "routes", frozenset({substituted}))
        with self.assertRaises(InvalidSchemaError) as replaced:
            capabilities.supports_route(substituted)
        self.assertEqual(
            replaced.exception.details["reason_code"],
            detail_digest("invalid_host_capabilities"),
        )

        malformed = HostCapabilities("test", (), routes=(original,))
        object.__setattr__(malformed, "routes", object())
        with self.assertRaises(InvalidSchemaError) as invalid:
            malformed.supports_route(original)
        self.assertEqual(
            invalid.exception.details["reason_code"],
            detail_digest("invalid_host_capabilities"),
        )

        candidate = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "native",
        )
        object.__setattr__(candidate, "rail", object())
        with self.assertRaises(InvalidSchemaError) as invalid_candidate:
            HostCapabilities(
                "test", (), routes=(original,),
            ).supports_route(candidate)
        self.assertEqual(
            invalid_candidate.exception.details["reason_code"],
            detail_digest("invalid_host_route"),
        )

        nested = HostCapabilities("test", (), routes=(original,))
        stored = next(iter(nested.routes))
        object.__setattr__(stored, "rail", "codex_companion")
        coherent_substitution = HostRoute(
            "openai", HostCapability.CODEX_EXECUTION, "codex_companion",
        )
        with self.assertRaises(InvalidSchemaError) as nested_rejected:
            nested.supports_route(coherent_substitution)
        self.assertEqual(
            nested_rejected.exception.details["reason_code"],
            detail_digest("invalid_host_capabilities"),
        )

    def test_openrouter_exec_is_a_distinct_dispatch_rail_capability(self):
        values = {capability.value for capability in HostCapability}
        self.assertIn("openrouter_exec", values)
        payload = {
            "hosts": {
                "explicit": {"roles": {"only": {
                    "kind": "openrouter_exec", "probe": "openrouter",
                    "models": ["z-ai/glm-5.2"],
                }}},
                "wrapper": {"roles": {"only": {
                    "kind": "wrapper", "probe": "openrouter",
                    "models": ["z-ai/glm-5.2"],
                }}},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            explicit = {value.value for value in
                        capabilities_from_harness_profile("explicit", path).capabilities}
            wrapper = {value.value for value in
                       capabilities_from_harness_profile("wrapper", path).capabilities}
        self.assertIn("openrouter_exec", explicit)
        self.assertNotIn("wrapper_dispatch", explicit)
        self.assertIn("wrapper_dispatch", wrapper)
        self.assertNotIn("openrouter_exec", wrapper)

    def test_harness_fixtures_declare_only_observed_dispatch_rails(self):
        expected = {
            "claude-code": {
                HostCapability.NATIVE_DISPATCH,
                HostCapability.COMPANION_DISPATCH,
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
                HostCapability.ANTHROPIC_NATIVE_EXECUTION,
            },
            "codex": {
                HostCapability.NATIVE_DISPATCH,
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
            },
            "generic": {
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
            },
        }
        for host, capabilities in expected.items():
            with self.subTest(host=host):
                fixture = capabilities_from_harness_profile(host, canonical_harness_profile())
                self.assertEqual(fixture.capabilities, frozenset(capabilities))
                self.assertEqual(fixture.transition_model_version, 1)
                self.assertEqual(fixture.evidence_model_version, 1)
                self.assertNotIn(HostCapability.SESSION_RESUME, fixture.capabilities)

    def test_unknown_host_capability_fails_with_stable_reason(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            HostCapabilities("test", ("telepathy",))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unknown_capability_name"),
        )

    def test_duplicate_host_capabilities_fail_like_policy_schema(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            HostCapabilities("test", (HostCapability.NATIVE_DISPATCH,
                                      HostCapability.NATIVE_DISPATCH))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("duplicate_capability_name"),
        )

    def test_unknown_harness_role_kind_fails_closed(self):
        payload = {
            "hosts": {"test": {"roles": {"mystery": {"kind": "telepathy"}}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                capabilities_from_harness_profile("test", path)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unknown_capability_name"),
        )

    def test_harness_profile_uses_shared_json_boundaries(self):
        canonical = json.dumps({
            "hosts": {"test": {"roles": {"only": {"kind": "none"}}}},
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, (content, accepted) in ignored_json_boundary_corpus(
                canonical,
            ).items():
                path = root / f"{name}.json"
                path.write_text(content, encoding="utf-8")
                if accepted:
                    with self.subTest(name=name):
                        profile = capabilities_from_harness_profile("test", path)
                        self.assertEqual(profile.capabilities, frozenset())
                    continue
                with self.subTest(name=name):
                    with self.assertRaises(InvalidSchemaError) as raised:
                        capabilities_from_harness_profile("test", path)
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("invalid_harness_profile"),
                    )

    def test_harness_profile_validates_exact_names_before_profile_state(self):
        invalid_names = ("", " ", "\t", "\n", "UPPER", "-leading", "slash/name")
        valid_role = {"roles": {"only": {"kind": "none"}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profiles = {
                "present": json.dumps({
                    "hosts": {name: valid_role for name in invalid_names},
                }),
                "malformed_roles": json.dumps({
                    "hosts": {name: {"roles": []} for name in invalid_names},
                }),
                "malformed_json": "{",
            }
            paths = {"absent": root / "absent.json"}
            for state, content in profiles.items():
                paths[state] = root / f"{state}.json"
                paths[state].write_text(content, encoding="utf-8")

            for host_name in invalid_names:
                with self.subTest(surface="capabilities", host_name=host_name):
                    with self.assertRaises(InvalidSchemaError) as raised:
                        HostCapabilities(host_name, frozenset())
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("invalid_host_name"),
                    )
                for state, path in paths.items():
                    with self.subTest(
                        surface="profile", host_name=host_name, state=state,
                    ):
                        with self.assertRaises(InvalidSchemaError) as raised:
                            capabilities_from_harness_profile(host_name, path)
                        self.assertEqual(
                            raised.exception.details["reason_code"],
                            detail_digest("invalid_host_name"),
                        )

    def test_harness_profile_rejects_hostile_names_before_key_dispatch(self):
        secret = "sk-secret-host-name-callback"
        calls = []

        class Hostile:
            def __hash__(self):
                calls.append("hash")
                raise RuntimeError(secret)

            def __eq__(self, other):
                calls.append("eq")
                raise RuntimeError(secret)

        class HostileString(str):
            def __hash__(self):
                calls.append("str-hash")
                raise RuntimeError(secret)

            def __eq__(self, other):
                calls.append("str-eq")
                raise RuntimeError(secret)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / "present.json"
            present.write_text(json.dumps({
                "hosts": {"test": {"roles": {"only": {"kind": "none"}}}},
            }), encoding="utf-8")
            malformed = root / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            paths = (present, malformed, root / "absent.json")
            for name, host_name in (
                ("object", Hostile()),
                ("str_subclass", HostileString("test")),
            ):
                for path in paths:
                    calls.clear()
                    with self.subTest(name=name, profile=path.name):
                        with self.assertRaises(InvalidSchemaError) as raised:
                            capabilities_from_harness_profile(host_name, path)
                        self.assertEqual(
                            raised.exception.details["reason_code"],
                            detail_digest("invalid_host_name"),
                        )
                        self.assertNotIn(secret, repr(raised.exception))
                        self.assertEqual(calls, [])

    def test_harness_profile_contains_pathlike_conversion_failures(self):
        secret = "sk-secret-harness-path-callback"

        class HostilePathLike(os.PathLike):
            def __init__(self, outcome):
                self.outcome = outcome
                self.calls = 0

            def __fspath__(self):
                self.calls += 1
                if isinstance(self.outcome, BaseException):
                    raise self.outcome
                return self.outcome

        candidates = (
            HostilePathLike(RuntimeError(secret)),
            HostilePathLike(object()),
        )
        for candidate in candidates:
            with self.subTest(outcome=type(candidate.outcome).__name__):
                with self.assertRaises(InvalidSchemaError) as raised:
                    capabilities_from_harness_profile("test", candidate)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_harness_profile"),
                )
                self.assertNotIn(secret, repr(raised.exception))
                self.assertEqual(candidate.calls, 1)

    def test_harness_profile_preserves_valid_string_and_pathlike_support(self):
        class ValidPathLike(os.PathLike):
            def __init__(self, path):
                self.path = path
                self.calls = 0

            def __fspath__(self):
                self.calls += 1
                return os.fspath(self.path)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps({
                "hosts": {"test": {"roles": {"only": {"kind": "none"}}}},
            }), encoding="utf-8")
            string_profile = capabilities_from_harness_profile(
                "test", os.fspath(path),
            )
            candidate = ValidPathLike(path)
            pathlike_profile = capabilities_from_harness_profile(
                "test", candidate,
            )
        self.assertEqual(string_profile.capabilities, frozenset())
        self.assertEqual(pathlike_profile.capabilities, frozenset())
        self.assertEqual(candidate.calls, 1)

    def test_harness_profile_materializes_pathlike_string_subclasses(self):
        secret = "sk-secret-path-string-callback"
        path_calls = []
        string_calls = []

        class HostileString(str):
            def __getitem__(self, item):
                string_calls.append("getitem")
                raise RuntimeError(secret)

            def __str__(self):
                string_calls.append("str")
                raise RuntimeError(secret)

        class StringPathLike(os.PathLike):
            def __fspath__(self):
                path_calls.append("fspath")
                return HostileString("/absent/harness.json")

        with self.assertRaises(InvalidSchemaError) as raised:
            capabilities_from_harness_profile("test", StringPathLike())
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_harness_profile"),
        )
        self.assertNotIn(secret, repr(raised.exception))
        self.assertEqual(path_calls, ["fspath"])
        self.assertEqual(string_calls, [])

    def test_harness_profile_contains_concrete_path_subclass_callbacks(self):
        secret = "sk-secret-path-subclass-callback"
        calls = []

        class HostilePath(type(Path())):
            def __fspath__(self):
                calls.append("fspath")
                raise RuntimeError(secret)

            def read_text(self, *args, **kwargs):
                calls.append("read_text")
                raise RuntimeError(secret)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps({
                "hosts": {"test": {"roles": {"only": {"kind": "none"}}}},
            }), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                capabilities_from_harness_profile("test", HostilePath(path))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_harness_profile"),
        )
        self.assertNotIn(secret, repr(raised.exception))
        self.assertEqual(calls, ["fspath"])

    def test_harness_profile_rejects_bytes_without_subclass_callbacks(self):
        secret = "sk-secret-path-bytes-callback"
        path_calls = []
        bytes_calls = []

        class HostileBytes(bytes):
            def __bytes__(self):
                bytes_calls.append("bytes")
                raise RuntimeError(secret)

            def __getitem__(self, item):
                bytes_calls.append("getitem")
                raise RuntimeError(secret)

        class BytesPathLike(os.PathLike):
            def __fspath__(self):
                path_calls.append("fspath")
                return HostileBytes(b"/absent/harness.json")

        for name, candidate in (
            ("exact", b"/absent/harness.json"),
            ("subclass", BytesPathLike()),
        ):
            with self.subTest(name=name):
                with self.assertRaises(InvalidSchemaError) as raised:
                    capabilities_from_harness_profile("test", candidate)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_harness_profile"),
                )
                self.assertNotIn(secret, repr(raised.exception))
        self.assertEqual(path_calls, ["fspath"])
        self.assertEqual(bytes_calls, [])

    def test_harness_profile_path_annotation_matches_runtime_contract(self):
        annotation = get_type_hints(
            capabilities_from_harness_profile,
        )["path"]
        self.assertEqual(
            annotation,
            Union[str, os.PathLike[str]],
        )

    def test_invalid_host_name_precedes_hostile_path_dispatch(self):
        secret = "sk-secret-unreached-path-callback"
        calls = []

        class HostilePathLike(os.PathLike):
            def __fspath__(self):
                calls.append("fspath")
                raise RuntimeError(secret)

        for host_name in (" ", "UPPER"):
            with self.subTest(host_name=host_name):
                with self.assertRaises(InvalidSchemaError) as raised:
                    capabilities_from_harness_profile(
                        host_name, HostilePathLike(),
                    )
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_host_name"),
                )
                self.assertNotIn(secret, repr(raised.exception))
                self.assertEqual(calls, [])

    def test_valid_harness_names_preserve_profile_failure_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.json"
            missing.write_text(json.dumps({"hosts": {}}), encoding="utf-8")
            malformed_roles = root / "malformed-roles.json"
            malformed_roles.write_text(json.dumps({
                "hosts": {"test": {"roles": []}},
            }), encoding="utf-8")
            malformed_json = root / "malformed-json.json"
            malformed_json.write_text("{", encoding="utf-8")
            cases = (
                ("missing", "missing", missing),
                ("malformed_roles", "test", malformed_roles),
                ("malformed_json", "test", malformed_json),
                ("absent", "test", root / "absent.json"),
            )
            for state, host_name, path in cases:
                with self.subTest(state=state):
                    with self.assertRaises(InvalidSchemaError) as raised:
                        capabilities_from_harness_profile(host_name, path)
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("invalid_harness_profile"),
                    )

    def test_native_provider_capability_comes_from_validated_role_not_host_name(self):
        payload = {
            "hosts": {
                "renamed-claude": {"roles": {"native": {
                    "kind": "native", "probe": "claude", "models": ["opus"],
                }}},
                "wrapper-only": {"roles": {"api": {
                    "kind": "wrapper", "probe": "openrouter",
                    "models": ["anthropic/claude-opus-4.8"],
                }}},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            native = capabilities_from_harness_profile("renamed-claude", path)
            wrapper = capabilities_from_harness_profile("wrapper-only", path)
        self.assertIn(HostCapability.ANTHROPIC_NATIVE_EXECUTION,
                      native.capabilities)
        self.assertNotIn(HostCapability.ANTHROPIC_NATIVE_EXECUTION,
                         wrapper.capabilities)
        self.assertIn(HostCapability.CLAUDE_EXECUTION, wrapper.capabilities)

    def test_inconsistent_harness_role_fields_fail_closed(self):
        roles = (
            {"kind": "native", "probe": "openrouter", "models": ["opus"]},
            {"kind": "codex_companion", "probe": "claude", "models": ["gpt-5"]},
            {"kind": "wrapper", "probe": "codex", "models": ["openai/gpt-5"]},
            {"kind": "none", "probe": "claude"},
            {"kind": "native", "probe": "claude", "models": ["openai/gpt-5"]},
            {"kind": "native", "probe": "codex", "models": ["anthropic/claude-opus"]},
        )
        for role in roles:
            payload = {"hosts": {"test": {"roles": {"bad": role}}}}
            with self.subTest(role=role), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "harness.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    capabilities_from_harness_profile("test", path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_harness_profile"),
                )

    def test_required_modules_import_in_clean_processes_without_cycles(self):
        root = str(KERNEL_REFERENCES)
        environment = dict(os.environ, PYTHONPATH=root)
        statements = (
            "import workflow_kernel.policies",
            "import workflow_kernel.workflows",
            "import workflow_kernel.adapters",
            "from workflow_kernel.adapters import IsolationSelector, BuilderSessionManager",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                result = subprocess.run(
                    [sys.executable, "-c", statement], cwd="/tmp", env=environment,
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
