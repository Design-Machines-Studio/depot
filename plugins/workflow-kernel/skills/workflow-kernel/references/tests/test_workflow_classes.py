import json
import importlib
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest
from workflow_kernel.adapters.base import HostCapability, WorkflowClass, WorkflowContext
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.policies import GatePolicy
from workflow_kernel.workflows import WorkflowTemplates


def schema_matches(value, schema, root=None):
    root = schema if root is None else root
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return schema_matches(value, target, root)
    expected_type = schema.get("type")
    if expected_type is not None:
        names = expected_type if isinstance(expected_type, list) else [expected_type]
        matches = {
            "object": type(value) is dict,
            "array": type(value) is list,
            "string": type(value) is str,
            "boolean": type(value) is bool,
            "null": value is None,
        }
        if not any(matches.get(name, False) for name in names):
            return False
    if "const" in schema and value != schema["const"]:
        return False
    if "enum" in schema and value not in schema["enum"]:
        return False
    if any(not schema_matches(value, item, root) for item in schema.get("allOf", [])):
        return False
    if "if" in schema and schema_matches(value, schema["if"], root):
        if not schema_matches(value, schema.get("then", {}), root):
            return False
    if type(value) is dict:
        properties = schema.get("properties", {})
        if not set(schema.get("required", [])) <= set(value):
            return False
        additional = schema.get("additionalProperties", True)
        extras = set(value) - set(properties)
        if additional is False and extras:
            return False
        if type(additional) is dict and any(
            not schema_matches(value[name], additional, root) for name in extras
        ):
            return False
        if any(
            name in properties and not schema_matches(item, properties[name], root)
            for name, item in value.items()
        ):
            return False
    if type(value) is list:
        if len(value) < schema.get("minItems", 0):
            return False
        if schema.get("uniqueItems") and len({json.dumps(
            item, sort_keys=True,
        ) for item in value}) != len(value):
            return False
        if "items" in schema and any(
            not schema_matches(item, schema["items"], root) for item in value
        ):
            return False
    return True


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

    def test_template_expansion_snapshots_and_revalidates_workflow_context(self):
        context = WorkflowContext(changed_paths=("docs/safe.md",))
        object.__setattr__(context, "changed_paths", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            WorkflowTemplates().expand(WorkflowClass.CHORE, context)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_workflow_context"),
        )

    def test_gate_policy_snapshots_workflow_context_before_use(self):
        context = WorkflowContext(evidence=("risk_assessment",))
        object.__setattr__(context, "evidence", object())
        with self.assertRaises(InvalidSchemaError) as raised:
            GatePolicy().decide(
                WorkflowClass.HOTFIX, "risk", ("risk_assessment",), context,
            )
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_gate_context"),
        )

    def test_requested_executor_changes_only_overridable_builder_nodes(self):
        nodes = WorkflowTemplates().expand(
            WorkflowClass.FEATURE, WorkflowContext(requested_executor="openrouter"),
        )
        build = next(node for node in nodes if node.node_id == "build")
        review = next(node for node in nodes if node.node_id == "review")
        self.assertEqual(build.executor, "openrouter")
        self.assertEqual(build.required_capability, HostCapability.OPENROUTER_EXECUTION)
        self.assertIsNone(build.required_dispatch_capability)
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
                        (HostCapability.NATIVE_DISPATCH
                         if kind is WorkflowClass.SECURITY and node.executor is not None
                         else None),
                    )

    def test_authoritative_json_has_no_schema_boundary_mirror(self):
        root = Path(__file__).parents[1]
        document = json.loads((root / "workflow-classes.json").read_text())
        schema = json.loads((root / "workflow-classes-schema.json").read_text())
        self.assertIn("requirements", document)
        self.assertIn("requirements", schema["properties"])
        self.assertNotIn("x-kernel-boundaries", schema)
        node_schema = schema["$defs"]["node"]
        self.assertIn("allOf", node_schema)

        requirements = schema["properties"]["requirements"]["properties"]
        class_schema = requirements["classes"]
        self.assertEqual(
            class_schema["required"], ["hotfix", "security", "migration"],
        )
        self.assertFalse(class_schema["additionalProperties"])
        promotion_schema = requirements["promotion"]
        self.assertEqual(promotion_schema["required"], ["investigation"])
        self.assertFalse(promotion_schema["additionalProperties"])
        self.assertIn("executor_constraint", schema["$defs"])
        self.assertEqual(
            node_schema["allOf"][0], {"$ref": "#/$defs/executor_constraint"},
        )

    def test_workflow_schema_default_and_runtime_share_exact_requirement_contract(self):
        root = Path(__file__).parents[1]
        document = json.loads((root / "workflow-classes.json").read_text())
        schema = json.loads((root / "workflow-classes-schema.json").read_text())
        self.assertIn("stages", document["requirements"]["classes"]["security"])
        self.assertTrue(schema_matches(document, schema))

        mutations = []
        missing = json.loads(json.dumps(document))
        del missing["requirements"]["classes"]["hotfix"]
        mutations.append(missing)
        unknown = json.loads(json.dumps(document))
        unknown["requirements"]["classes"]["bug"] = unknown["requirements"][
            "classes"
        ]["hotfix"]
        mutations.append(unknown)
        invalid_tuple = json.loads(json.dumps(document))
        stage = next(
            item for item in invalid_tuple["requirements"]["classes"]["security"][
                "stages"
            ] if item["id"] == "security_build"
        )
        stage["executor"] = "codex"
        mutations.append(invalid_tuple)
        unknown_stage_key = json.loads(json.dumps(document))
        unknown_stage_key["requirements"]["classes"]["hotfix"]["stages"][0][
            "optional"
        ] = True
        mutations.append(unknown_stage_key)
        missing_stage_key = json.loads(json.dumps(document))
        del missing_stage_key["requirements"]["classes"]["migration"]["stages"][0][
            "required_ancestors"
        ]
        mutations.append(missing_stage_key)

        for payload in mutations:
            self.assertFalse(schema_matches(payload, schema))
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError):
                    WorkflowTemplates(path)

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

        weakened_security = json.loads(json.dumps(base))
        security_build = next(
            node for node in weakened_security["classes"]["security"]["nodes"]
            if node["id"] == "security_build"
        )
        security_build["required_capability"] = "claude_execution"
        security_build["required_dispatch_capability"] = None
        mutations.append(("workflow_requirement_unsatisfied", weakened_security))

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

    def test_declared_semantic_requirements_reject_class_and_cleanup_mutations(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []
        for class_name, node_id, replacement in (
            ("hotfix", "risk_gate", "evidence"),
            ("migration", "human_gate", "risk"),
        ):
            payload = json.loads(json.dumps(base))
            node = next(item for item in payload["classes"][class_name]["nodes"]
                        if item["id"] == node_id)
            node["gate_kind"] = replacement
            mutations.append(("workflow_requirement_unsatisfied", payload))

        cleanup = json.loads(json.dumps(base))
        cleanup["classes"]["chore"]["nodes"][-1]["gate_kind"] = None
        mutations.append(("workflow_requirement_unsatisfied", cleanup))

        promotion = json.loads(json.dumps(base))
        promotion["promotion"]["investigation"]["nodes"][0]["gate_kind"] = "evidence"
        mutations.append(("promotion_gate_required", promotion))

        for reason, payload in mutations:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"], detail_digest(reason),
                )

    def test_canonical_safety_anchor_rejects_joint_graph_and_requirement_weakening(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []

        placeholder = json.loads(json.dumps(base))
        for node in placeholder["classes"]["security"]["nodes"]:
            if node["gate_kind"] in ("evidence", "human_approval"):
                node["required_evidence"] = ["placeholder"]
        for stage in placeholder["requirements"]["classes"]["security"]["stages"]:
            if stage["gate_kind"] in ("evidence", "human_approval"):
                stage["required_evidence"] = ["placeholder"]
        mutations.append(placeholder)

        removed_security_review = json.loads(json.dumps(base))
        security = removed_security_review["classes"]["security"]["nodes"]
        security[:] = [node for node in security if node["id"] != "security_review"]
        next(node for node in security if node["id"] == "human_gate")[
            "depends_on"
        ] = ["validation"]
        security_requirements = removed_security_review["requirements"]["classes"][
            "security"
        ]["stages"]
        security_requirements[:] = [
            stage for stage in security_requirements
            if stage["id"] != "security_review"
        ]
        mutations.append(removed_security_review)

        removed_rollback = json.loads(json.dumps(base))
        migration = removed_rollback["classes"]["migration"]["nodes"]
        migration[:] = [node for node in migration if node["id"] != "rollback_evidence"]
        next(node for node in migration if node["id"] == "review")["depends_on"] = [
            "compatibility_validation"
        ]
        migration_requirements = removed_rollback["requirements"]["classes"][
            "migration"
        ]["stages"]
        migration_requirements[:] = [
            stage for stage in migration_requirements
            if stage["id"] != "rollback_evidence"
        ]
        mutations.append(removed_rollback)

        removed_hotfix = json.loads(json.dumps(base))
        hotfix = removed_hotfix["classes"]["hotfix"]["nodes"]
        hotfix[:] = [node for node in hotfix if node["id"] != "risk_gate"]
        next(node for node in hotfix if node["id"] == "review")["depends_on"] = [
            "focused_validation"
        ]
        del removed_hotfix["requirements"]["classes"]["hotfix"]
        mutations.append(removed_hotfix)

        for payload in mutations:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertIn(
                    raised.exception.details["reason_code"],
                    {detail_digest("invalid_workflow_requirements"),
                     detail_digest("workflow_requirement_unsatisfied")},
                )

    def test_canonical_safety_anchor_rejects_removed_cleanup_and_promotion(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))

        no_cleanup = json.loads(json.dumps(base))
        no_cleanup["classes"]["chore"]["nodes"][-1]["id"] = "finish"
        no_cleanup["requirements"]["global"]["cleanup"]["id"] = "finish"

        no_promotion = json.loads(json.dumps(base))
        no_promotion["promotion"]["investigation"]["nodes"].pop(0)
        no_promotion["promotion"]["investigation"]["nodes"][0]["depends_on"] = [
            "evidence_gathering"
        ]
        no_promotion["requirements"]["promotion"]["investigation"]["stages"].pop(0)

        for payload in (no_cleanup, no_promotion):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError):
                    WorkflowTemplates(path)

    def test_anthropic_native_constraint_requires_claude_native_dispatch(self):
        source = Path(__file__).parents[1] / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        for executor, dispatch in (("codex", "native_dispatch"),
                                   ("claude", None)):
            payload = json.loads(json.dumps(base))
            node = payload["classes"]["security"]["nodes"][1]
            node["executor"] = executor
            node["required_dispatch_capability"] = dispatch
            with self.subTest(executor=executor, dispatch=dispatch), \
                    tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertIn(
                    raised.exception.details["reason_code"],
                    {detail_digest("inconsistent_executor_capability"),
                     detail_digest("inconsistent_dispatch_capability")},
                )

        schema = json.loads(
            (Path(__file__).parents[1] / "workflow-classes-schema.json").read_text()
        )
        clause = next(
            item for item in schema["$defs"]["executor_constraint"]["allOf"]
            if item["if"]["properties"].get("required_capability")
            == {"const": "anthropic_native_execution"}
        )
        self.assertEqual(
            clause["then"]["properties"],
            {"executor": {"const": "claude"},
             "required_dispatch_capability": {"const": "native_dispatch"}},
        )

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
