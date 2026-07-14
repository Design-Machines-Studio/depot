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

from tests import detail_digest, snapshot_during_validated_mutation
import workflow_kernel.adapters.base as adapter_base
from workflow_kernel.adapters.base import (
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

        context = adapter_base.ResumeStateContext(
            "run-1", "build", "attempt-1", "openai", "native",
            HostCapability.CODEX_EXECUTION,
        )
        object.__setattr__(context, "run_id", "run-2")
        with self.assertRaises(ValueError):
            context.__post_init__()
        with self.assertRaises(InvalidSchemaError):
            context.to_dict()

        handle = adapter_base.SessionHandle(
            "codex", "opaque-one", "2026-07-14T00:00:00Z", True,
            adapter_base.ResumeStateContext(
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

        registry = adapter_base._IdentitySealRegistry()
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
            context, adapter_base._snapshot_workflow_context,
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
            node, adapter_base._snapshot_node_spec, mutate_node,
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
            capabilities, adapter_base._snapshot_host_capabilities,
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
        self.assertTrue(hasattr(adapter_base, "_origin_seal_registry_size"))
        before = adapter_base._origin_seal_registry_size()
        route = HostRoute("openai", HostCapability.CODEX_EXECUTION, "native")
        reference = weakref.ref(route)
        self.assertEqual(adapter_base._origin_seal_registry_size(), before + 1)
        del route
        gc.collect()
        self.assertIsNone(reference())
        self.assertLessEqual(adapter_base._origin_seal_registry_size(), before)

    def test_host_authorization_exposes_immutable_concrete_routes(self):
        self.assertTrue(hasattr(adapter_base, "HostRoute"))
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
        claude = capabilities_from_harness_profile("claude-code")
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
        original = adapter_base._snapshot_host_route
        with patch.object(adapter_base, "_snapshot_host_route", wraps=original) as snapshot:
            capabilities = HostCapabilities("test", (), routes=(route,))
        self.assertEqual(snapshot.call_count, 1)
        node = NodeSpec(
            "build", executor="codex",
            required_capability=HostCapability.CODEX_EXECUTION,
            required_dispatch_capability=HostCapability.NATIVE_DISPATCH,
        )
        original_node = adapter_base._snapshot_node_spec
        with patch.object(adapter_base, "_snapshot_host_route", wraps=original) as route_snapshot, \
                patch.object(adapter_base, "_snapshot_node_spec", wraps=original_node) as node_snapshot:
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
                fixture = capabilities_from_harness_profile(host)
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
        root = str(Path(__file__).parents[1])
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
