import json
import inspect
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tests import detail_digest
import workflow_kernel.adapters.base as adapter_base
from workflow_kernel.adapters.base import (
    HostCapabilities, HostCapability, HostRoute, NodeSpec, route_satisfies_node,
)
from workflow_kernel.adapters.host import capabilities_from_harness_profile
from workflow_kernel.schema import InvalidSchemaError


class HostCapabilityTests(unittest.TestCase):
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
        with patch.object(adapter_base, "_snapshot_host_route", wraps=original) as snapshot:
            self.assertTrue(route_satisfies_node(next(iter(capabilities.routes)), node))
        self.assertEqual(snapshot.call_count, 1)

    def test_supports_revalidates_mutated_host_capabilities(self):
        capabilities = HostCapabilities("test", (HostCapability.WORKTREE,))
        object.__setattr__(capabilities, "capabilities", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            capabilities.supports(HostCapability.WORKTREE)
        self.assertEqual(
            raised.exception.details["reason_code"],
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
