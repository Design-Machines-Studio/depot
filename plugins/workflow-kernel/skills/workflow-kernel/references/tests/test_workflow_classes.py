import json
import importlib
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest
from workflow_kernel.adapters.base import HostCapability, WorkflowClass, WorkflowContext
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.workflows import WorkflowTemplates


class WorkflowClassTests(unittest.TestCase):
    def test_authoritative_json_expands_to_dependency_valid_graphs(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        definitions = json.loads(source.read_text(encoding="utf-8"))["classes"]
        templates = WorkflowTemplates()
        self.assertEqual({kind.value for kind in WorkflowClass}, set(definitions))
        for kind in WorkflowClass:
            with self.subTest(kind=kind.value):
                nodes = templates.expand(kind, WorkflowContext())
                expected = tuple(
                    (record["id"], tuple(record["depends_on"]), record["gate_kind"])
                    for record in definitions[kind.value]["nodes"]
                )
                actual = tuple(
                    (node.node_id, node.dependencies, node.gate_kind) for node in nodes
                )
                self.assertEqual(actual, expected)
                self.assertEqual(nodes[-1].node_id, "cleanup")
                seen = set()
                for node in nodes:
                    self.assertTrue(set(node.dependencies) <= seen)
                    seen.add(node.node_id)

    def test_investigation_build_requires_explicit_approved_promotion(self):
        templates = WorkflowTemplates()
        plain = templates.expand(WorkflowClass.INVESTIGATION, WorkflowContext())
        requested = templates.expand(
            WorkflowClass.INVESTIGATION,
            WorkflowContext(investigation_promotion=True, evidence=("promotion_decision",)),
        )
        approved = templates.expand(
            WorkflowClass.INVESTIGATION,
            WorkflowContext(
                investigation_promotion=True,
                promotion_approved=True,
                evidence=("promotion_decision", "hypothesis", "investigation_evidence",
                          "conclusion", "next_action"),
            ),
        )
        self.assertNotIn("promoted_build", {node.node_id for node in plain})
        self.assertNotIn("promoted_build", {node.node_id for node in requested})
        self.assertIn("promoted_build", {node.node_id for node in approved})
        gate = next(node for node in approved if node.node_id == "promotion_gate")
        self.assertTrue(gate.gate_decision.allowed)

    def test_sensitive_and_security_routing_override_requests_without_path_disclosure(self):
        templates = WorkflowTemplates()
        contexts = (
            (WorkflowClass.CHORE, WorkflowContext(
                changed_paths=("internal/auth/credentials.py",),
                requested_executor="openrouter", economics_preference="cheapest",
            )),
            (WorkflowClass.SECURITY, WorkflowContext(
                changed_paths=("docs/safe.md",), requested_executor="codex",
                economics_preference="cheapest",
            )),
        )
        for kind, context in contexts:
            with self.subTest(kind=kind.value):
                nodes = templates.expand(kind, context)
                routed = [node for node in nodes if node.executor is not None]
                self.assertTrue(routed)
                self.assertTrue(all(node.executor == "claude" for node in routed))
                self.assertTrue(all(node.routing_reason in {
                    "sensitive_path_override", "security_workflow_override"
                } for node in routed))
                self.assertTrue(all(not node.executor_overridable for node in routed))
                self.assertNotIn("credentials.py", repr(nodes))

    def test_sensitive_paths_are_normalized_and_take_precedence_over_security_class(self):
        context = WorkflowContext(
            changed_paths=("./internal/auth/keys.py",), requested_executor="openrouter",
        )
        self.assertEqual(context.changed_paths, ("internal/auth/keys.py",))
        nodes = WorkflowTemplates().expand(WorkflowClass.SECURITY, context)
        routed = [node for node in nodes if node.executor is not None]
        self.assertTrue(routed)
        self.assertTrue(all(node.executor == "claude" for node in routed))
        self.assertTrue(all(node.routing_reason == "sensitive_path_override" for node in routed))
        self.assertTrue(all(
            node.required_capability is HostCapability.ANTHROPIC_NATIVE_EXECUTION
            for node in routed
        ))

    def test_changed_paths_reject_absolute_parent_and_non_posix_forms(self):
        for path in ("/internal/auth/keys.py", "../internal/auth/keys.py",
                     "internal/auth/../safe.py", "internal\\auth\\keys.py",
                     "internal/auth/\x00keys.py", "internal/auth/\x1fkeys.py",
                     "internal/auth/\u0085keys.py", "internal/auth/\u009fkeys.py",
                     "x" * 4_097):
            with self.subTest(path=path):
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowContext(changed_paths=(path,))
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("invalid_changed_path"),
                )
        with self.assertRaises(InvalidSchemaError) as raised:
            WorkflowContext(changed_paths=tuple(f"file-{index}" for index in range(1_025)))
        self.assertEqual(
            raised.exception.details["reason_code"], detail_digest("invalid_changed_path"),
        )

    def test_requested_executor_changes_only_overridable_builder_nodes(self):
        nodes = WorkflowTemplates().expand(
            WorkflowClass.FEATURE, WorkflowContext(requested_executor="openrouter"),
        )
        build = next(node for node in nodes if node.node_id == "build")
        review = next(node for node in nodes if node.node_id == "review")
        self.assertEqual(build.executor, "openrouter")
        self.assertEqual(build.required_capability, HostCapability.OPENROUTER_EXECUTION)
        self.assertEqual(
            build.required_dispatch_capability, HostCapability.OPENROUTER_EXEC,
        )
        self.assertEqual(review.executor, "claude")
        self.assertEqual(review.required_capability, HostCapability.CLAUDE_EXECUTION)
        self.assertEqual(review.routing_reason, "workflow_default")

    def test_executor_nodes_declare_matching_provider_capability(self):
        expected = {
            "claude": HostCapability.CLAUDE_EXECUTION,
            "codex": HostCapability.CODEX_EXECUTION,
            "openrouter": HostCapability.OPENROUTER_EXECUTION,
        }
        for kind in WorkflowClass:
            for node in WorkflowTemplates().expand(kind, WorkflowContext()):
                with self.subTest(kind=kind.value, node=node.node_id):
                    self.assertEqual(
                        node.required_capability,
                        (HostCapability.ANTHROPIC_NATIVE_EXECUTION
                         if kind is WorkflowClass.SECURITY and node.executor == "claude"
                         else expected[node.executor] if node.executor is not None else None),
                    )
                    self.assertEqual(
                        node.required_dispatch_capability,
                        HostCapability.NATIVE_DISPATCH if node.executor is not None else None,
                    )

    def test_authoritative_json_has_no_schema_boundary_mirror(self):
        root = Path(__file__).parents[1]
        schema = json.loads((root / "workflow-classes-schema.json").read_text())
        self.assertNotIn("x-kernel-boundaries", schema)
        node_schema = schema["$defs"]["node"]
        self.assertIn("allOf", node_schema)

    def test_resume_parser_has_no_redundant_json_shape_traversal(self):
        host_module = importlib.import_module("workflow_kernel.adapters.host")
        self.assertFalse(hasattr(host_module, "_json_shape"))

    def test_malformed_scalar_shapes_fail_with_stable_errors(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        for field, value, reason in (
            ("gate_kind", [], "unknown_gate_kind"),
            ("gate_kind", {}, "unknown_gate_kind"),
            ("executor", [], "unknown_executor"),
            ("executor", {}, "unknown_executor"),
        ):
            payload = json.loads(json.dumps(base))
            payload["classes"]["chore"]["nodes"][0][field] = value
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(raised.exception.details["reason_code"],
                                 detail_digest(reason))

    def test_executor_capability_relationship_mutations_match_schema_contract(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []
        null_with_capability = json.loads(json.dumps(base))
        null_with_capability["classes"]["chore"]["nodes"][0][
            "required_capability"
        ] = "codex_execution"
        mutations.append(null_with_capability)
        mismatched = json.loads(json.dumps(base))
        mismatched["classes"]["chore"]["nodes"][1][
            "required_capability"
        ] = "openrouter_execution"
        mutations.append(mismatched)
        null_overridable = json.loads(json.dumps(base))
        null_overridable["classes"]["chore"]["nodes"][0][
            "executor_overridable"
        ] = True
        mutations.append(null_overridable)
        for payload in mutations:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("inconsistent_executor_capability"),
                )

    def test_human_approval_cannot_repair_missing_mandatory_evidence(self):
        nodes = WorkflowTemplates().expand(
            WorkflowClass.SECURITY, WorkflowContext(human_approved=True),
        )
        gate = next(node for node in nodes if node.node_id == "human_gate")
        self.assertFalse(gate.gate_decision.allowed)
        self.assertEqual(gate.gate_decision.reason_code, "missing_mandatory_evidence")

    def test_hotfix_migration_and_security_keep_mandatory_gates(self):
        templates = WorkflowTemplates()
        expected = {
            WorkflowClass.HOTFIX: {"risk"},
            WorkflowClass.MIGRATION: {"human_approval", "evidence"},
            WorkflowClass.SECURITY: {"human_approval", "evidence"},
        }
        for kind, gate_kinds in expected.items():
            actual = {node.gate_kind for node in templates.expand(kind, WorkflowContext())}
            self.assertTrue(gate_kinds <= actual)

    def test_invalid_version_missing_id_and_cycle_fail_with_stable_reason_codes(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []
        invalid_version = json.loads(json.dumps(base))
        invalid_version["schema_version"] = 2
        mutations.append(("unsupported_policy_version", invalid_version))
        missing_id = json.loads(json.dumps(base))
        del missing_id["classes"]["chore"]["nodes"][0]["id"]
        mutations.append(("missing_node_id", missing_id))
        cycle = json.loads(json.dumps(base))
        cycle["classes"]["chore"]["nodes"][0]["depends_on"] = ["cleanup"]
        mutations.append(("template_dependency_cycle", cycle))
        for reason, payload in mutations:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest(reason))

    def test_template_loader_rejects_only_generic_mandatory_constraints(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []

        erased_evidence = json.loads(json.dumps(base))
        human = next(node for node in erased_evidence["classes"]["migration"]["nodes"]
                     if node["id"] == "human_gate")
        human["required_evidence"] = []
        mutations.append(("invalid_workflow_node", erased_evidence))

        missing_dispatch = json.loads(json.dumps(base))
        build = next(node for node in missing_dispatch["classes"]["chore"]["nodes"]
                     if node["id"] == "build")
        build["required_dispatch_capability"] = None
        mutations.append(("inconsistent_executor_capability", missing_dispatch))

        bypassed_promotion = json.loads(json.dumps(base))
        bypassed_promotion["promotion"]["investigation"]["nodes"][1]["depends_on"] = [
            "evidence_gathering"
        ]
        mutations.append(("promotion_gate_required", bypassed_promotion))

        for reason, payload in mutations:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest(reason))

    def test_template_loader_rejects_forward_order_and_multiple_terminal_sinks(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        forward = json.loads(json.dumps(base))
        nodes = forward["classes"]["chore"]["nodes"]
        nodes[0], nodes[1] = nodes[1], nodes[0]
        orphan = json.loads(json.dumps(base))
        orphan["classes"]["chore"]["nodes"].insert(-1, {
            "id": "orphan_observation", "depends_on": ["assess"], "gate_kind": None,
            "required_evidence": [], "executor": None, "required_capability": None,
            "required_dispatch_capability": None,
            "executor_overridable": False,
        })
        for reason, payload in (
            ("non_topological_dependency_order", forward),
            ("cleanup_terminal_invariant", orphan),
        ):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(raised.exception.details["reason_code"], detail_digest(reason))


if __name__ == "__main__":
    unittest.main()
