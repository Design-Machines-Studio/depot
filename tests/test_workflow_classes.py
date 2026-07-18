import json
import importlib
import tempfile
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES
from tests import (
    detail_digest, ignored_json_boundary_corpus, json_document_boundary_corpus,
    schema_matches,
)
from workflow_kernel.model import HostCapability, WorkflowClass, WorkflowContext
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.policies import GatePolicy, load_policy
from workflow_kernel.workflows import WorkflowTemplates

class WorkflowClassTests(unittest.TestCase):
    def test_workflow_class_json_loader_has_explicit_parser_boundaries(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        canonical = source.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = json_document_boundary_corpus(
                canonical,
                json_reason="invalid_workflow_classes_json",
                document_reason="invalid_workflow_classes_document",
                version_reason="unsupported_policy_version",
            )
            for name, (content, reason) in documents.items():
                path = root / f"{name}.json"
                path.write_text(content, encoding="utf-8")
                with self.subTest(name=name), self.assertRaises(
                    InvalidSchemaError,
                ) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest(reason),
                )

        self.assertEqual(
            WorkflowTemplates(source)._templates,
            WorkflowTemplates()._templates,
        )

    def test_default_sensitive_globs_are_kernel_owned_and_synced_with_routing_policy(self):
        from workflow_kernel.workflows import DEFAULT_SENSITIVE_POLICY_PATH

        references = KERNEL_REFERENCES
        self.assertEqual(
            DEFAULT_SENSITIVE_POLICY_PATH,
            references / "sensitive-path-policy.json",
        )
        owned = json.loads(DEFAULT_SENSITIVE_POLICY_PATH.read_text(encoding="utf-8"))
        owned_globs = owned["security"]["neverRouteToOpenRouter"]["pathGlobs"]
        self.assertEqual(
            tuple(owned_globs), WorkflowTemplates()._sensitive_globs,
        )
        routing_policy = next(
            (
                parent / "plugins" / "pipeline" / "references" / "routing-policy.json"
                for parent in Path(__file__).resolve().parents
                if (parent / "plugins" / "pipeline" / "references" / "routing-policy.json").is_file()
            ),
            None,
        )
        self.assertIsNotNone(routing_policy, "canonical routing-policy.json not found")
        upstream = json.loads(routing_policy.read_text(encoding="utf-8"))
        self.assertEqual(
            owned_globs,
            upstream["security"]["neverRouteToOpenRouter"]["pathGlobs"],
            "kernel-owned sensitive-path-policy.json drifted from routing-policy.json",
        )

    def test_sensitive_routing_policy_uses_shared_json_boundaries(self):
        canonical = json.dumps({
            "security": {
                "neverRouteToOpenRouter": {"pathGlobs": ["secret/**"]},
            },
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
                        templates = WorkflowTemplates(routing_policy_path=path)
                        self.assertEqual(templates._sensitive_globs, ("secret/**",))
                    continue
                with self.subTest(name=name):
                    with self.assertRaises(InvalidSchemaError) as raised:
                        WorkflowTemplates(routing_policy_path=path)
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("invalid_routing_policy"),
                    )

    def test_workflow_enum_impostors_are_rejected_without_equality_dispatch(self):
        secret = "sk-secret-workflow-detail"
        calls = []

        class Hostile:
            def __eq__(self, other):
                calls.append("ordinary")
                raise RuntimeError(secret)

        with self.assertRaises(InvalidSchemaError) as risk_error:
            WorkflowContext(risk=Hostile())
        self.assertNotIn(secret, repr(risk_error.exception))
        calls.clear()
        with self.assertRaises(InvalidSchemaError) as class_error:
            WorkflowTemplates().expand(Hostile(), WorkflowContext())
        self.assertNotIn(secret, repr(class_error.exception))

        class FatalConversion(BaseException):
            pass

        class Fatal:
            def __eq__(self, other):
                calls.append("fatal")
                raise FatalConversion()

        with self.assertRaises(InvalidSchemaError):
            WorkflowTemplates().expand(Fatal(), WorkflowContext())
        self.assertEqual(calls, [])

    def test_recursive_schema_matcher_supports_shared_superset_keywords(self):
        schema = {
            "type": "object",
            "required": ["count", "items"],
            "properties": {
                "count": {"type": "integer", "minimum": 2},
                "items": {
                    "type": "array", "minItems": 1,
                    "items": {"type": "string", "minLength": 2},
                },
            },
            "additionalProperties": {"type": "string", "minLength": 3},
        }
        self.assertTrue(schema_matches(
            {"count": 2, "items": ["ok"], "note": "yes"}, schema,
        ))
        for invalid in (
            {"count": 1, "items": ["ok"], "note": "yes"},
            {"count": 2, "items": ["x"], "note": "yes"},
            {"count": 2, "items": ["ok"], "note": "no"},
            {"count": 2, "items": []},
        ):
            with self.subTest(invalid=invalid):
                self.assertFalse(schema_matches(invalid, schema))
        self.assertFalse(schema_matches(True, {"const": 1}))
        self.assertFalse(schema_matches(True, {"enum": [1]}))

    def test_authoritative_json_expands_to_dependency_valid_graphs(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
                self.assertTrue(all(node.executor == "codex" for node in routed))
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
        self.assertTrue(all(node.executor == "codex" for node in routed))
        self.assertTrue(all(node.routing_reason == "sensitive_path_override" for node in routed))
        self.assertTrue(all(
            node.required_capability is HostCapability.CODEX_EXECUTION
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
        self.assertEqual(review.executor, "codex")
        self.assertEqual(review.required_capability, HostCapability.CODEX_EXECUTION)
        self.assertEqual(review.routing_reason, "workflow_default")

    def test_legacy_claude_builder_request_normalizes_to_codex(self):
        nodes = WorkflowTemplates().expand(
            WorkflowClass.FEATURE, WorkflowContext(requested_executor="claude"),
        )
        build = next(node for node in nodes if node.node_id == "build")
        self.assertEqual(build.executor, "codex")
        self.assertEqual(build.required_capability, HostCapability.CODEX_EXECUTION)
        self.assertIsNone(build.required_dispatch_capability)
        self.assertEqual(build.routing_reason, "legacy_claude_normalized")

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
                        expected[node.executor] if node.executor is not None else None,
                    )
                    self.assertIsNone(node.required_dispatch_capability)

    def test_trusted_policy_owns_the_only_versioned_safety_anchor(self):
        root = KERNEL_REFERENCES
        document = json.loads((root / "workflow-classes.json").read_text())
        policy = json.loads((root / "workflow-policy.json").read_text())
        class_schema = json.loads((root / "workflow-classes-schema.json").read_text())
        policy_schema = json.loads((root / "workflow-policy-schema.json").read_text())
        self.assertNotIn("requirements", document)
        self.assertNotIn("requirements", class_schema["properties"])
        anchor = policy["workflow_safety_anchor"]
        self.assertEqual(anchor["schema_version"], 1)
        self.assertEqual(
            set(anchor), {
                "schema_version", "common", "classes", "promotion",
                "non_executable_classes",
            },
        )
        self.assertEqual(anchor.get("non_executable_classes"), ["investigation"])
        self.assertEqual(set(anchor["classes"]), {"hotfix", "security", "migration"})
        self.assertEqual(set(anchor["promotion"]), {"investigation"})
        expected = {
            "hotfix": {"build", "focused_validation", "risk_gate", "review"},
            "security": {"threat_risk_evidence", "security_build", "validation",
                         "security_review", "human_gate"},
            "migration": {"preflight", "schema_data_change", "compatibility_validation",
                          "rollback_evidence", "review", "human_gate"},
        }
        for name, stage_ids in expected.items():
            self.assertEqual(
                {stage["id"] for stage in anchor["classes"][name]["stages"]},
                stage_ids,
            )
        self.assertEqual(
            {stage["id"] for stage in anchor["common"]["stages"]}, {"cleanup"},
        )
        self.assertEqual(
            {stage["id"] for stage in anchor["promotion"]["investigation"]["stages"]},
            {"promotion_gate", "promoted_build"},
        )
        self.assertTrue(schema_matches(document, class_schema))
        self.assertTrue(schema_matches(policy, policy_schema))

    def test_schema_and_runtime_reject_empty_gated_evidence_and_impossible_routes(self):
        root = KERNEL_REFERENCES
        document = json.loads((root / "workflow-classes.json").read_text())
        schema = json.loads((root / "workflow-classes-schema.json").read_text())
        mutations = []
        empty = json.loads(json.dumps(document))
        empty["classes"]["feature"]["nodes"][1]["required_evidence"] = []
        mutations.append(empty)
        claude_companion = json.loads(json.dumps(document))
        review = claude_companion["classes"]["feature"]["nodes"][4]
        review["executor"] = "claude"
        review["required_capability"] = "claude_execution"
        review["required_dispatch_capability"] = "companion_dispatch"
        mutations.append(claude_companion)
        codex_wrapper = json.loads(json.dumps(document))
        codex_wrapper["classes"]["feature"]["nodes"][2][
            "required_dispatch_capability"
        ] = "wrapper_dispatch"
        mutations.append(codex_wrapper)
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
        security_build["executor"] = "openrouter"
        security_build["required_capability"] = "openrouter_execution"
        security_build["required_dispatch_capability"] = "openrouter_exec"
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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

    def test_trusted_safety_anchor_rejects_removed_rewired_or_weakened_stages(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []

        removed = json.loads(json.dumps(base))
        hotfix = removed["classes"]["hotfix"]["nodes"]
        hotfix[:] = [node for node in hotfix if node["id"] != "build"]
        next(node for node in hotfix if node["id"] == "focused_validation")[
            "depends_on"
        ] = ["reproduce_impact"]
        mutations.append(removed)

        rewired = json.loads(json.dumps(base))
        next(node for node in rewired["classes"]["migration"]["nodes"]
             if node["id"] == "compatibility_validation")["depends_on"] = ["preflight"]
        next(node for node in rewired["classes"]["migration"]["nodes"]
             if node["id"] == "human_gate")["depends_on"].append("schema_data_change")
        mutations.append(rewired)

        changed_executor = json.loads(json.dumps(base))
        security_build = next(
            node for node in changed_executor["classes"]["security"]["nodes"]
            if node["id"] == "security_build"
        )
        security_build.update({
            "executor": "claude", "required_capability": "anthropic_native_execution",
            "required_dispatch_capability": "native_dispatch",
        })
        mutations.append(changed_executor)

        removed_execution = json.loads(json.dumps(base))
        build = next(node for node in removed_execution["classes"]["hotfix"]["nodes"]
                     if node["id"] == "build")
        build.update({
            "executor": None, "required_capability": None,
            "required_dispatch_capability": None, "executor_overridable": False,
        })
        mutations.append(removed_execution)

        flipped_override = json.loads(json.dumps(base))
        next(node for node in flipped_override["classes"]["migration"]["nodes"]
             if node["id"] == "schema_data_change")["executor_overridable"] = False
        mutations.append(flipped_override)

        for payload in mutations:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("workflow_requirement_unsatisfied"),
                )

    def test_trusted_safety_anchor_rejects_unanchored_executable_work(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        mutations = []
        cases = (
            ("hotfix", "risk_gate", "review", "late_hotfix_build"),
            ("security", "validation", "security_review", "late_security_build"),
            ("migration", "rollback_evidence", "review", "late_migration_build"),
        )
        for class_name, predecessor, protected_review, inserted_id in cases:
            payload = json.loads(json.dumps(base))
            nodes = payload["classes"][class_name]["nodes"]
            review = next(node for node in nodes if node["id"] == protected_review)
            inserted = {
                "id": inserted_id,
                "depends_on": [predecessor],
                "gate_kind": None,
                "required_evidence": [],
                "executor": "codex",
                "required_capability": "codex_execution",
                "required_dispatch_capability": None,
                "executor_overridable": True,
            }
            review["depends_on"] = [inserted_id]
            nodes.insert(nodes.index(review), inserted)
            mutations.append(payload)

        promotion = json.loads(json.dumps(base))
        promoted = promotion["promotion"]["investigation"]["nodes"]
        promoted_build = next(node for node in promoted if node["id"] == "promoted_build")
        extra = {
            "id": "unanchored_promoted_build",
            "depends_on": ["promotion_gate"],
            "gate_kind": None,
            "required_evidence": [],
            "executor": "codex",
            "required_capability": "codex_execution",
            "required_dispatch_capability": None,
            "executor_overridable": True,
        }
        promoted_build["depends_on"] = [extra["id"]]
        promoted.insert(promoted.index(promoted_build), extra)
        mutations.append(promotion)

        for payload in mutations:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("workflow_requirement_unsatisfied"),
                )

    def test_investigation_base_rejects_direct_and_rewired_execution(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))

        inserted = json.loads(json.dumps(base))
        inserted_nodes = inserted["classes"]["investigation"]["nodes"]
        conclusion = next(
            node for node in inserted_nodes
            if node["id"] == "conclusion_next_action"
        )
        unpromoted = {
            "id": "unpromoted_build",
            "depends_on": ["evidence_gathering"],
            "gate_kind": None,
            "required_evidence": [],
            "executor": "codex",
            "required_capability": "codex_execution",
            "required_dispatch_capability": None,
            "executor_overridable": True,
        }
        conclusion["depends_on"] = [unpromoted["id"]]
        inserted_nodes.insert(inserted_nodes.index(conclusion), unpromoted)

        rewired = json.loads(json.dumps(base))
        rewired_conclusion = next(
            node for node in rewired["classes"]["investigation"]["nodes"]
            if node["id"] == "conclusion_next_action"
        )
        rewired_conclusion.update({
            "executor": "codex",
            "required_capability": "codex_execution",
            "executor_overridable": True,
        })

        for payload in (inserted, rewired):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError) as raised:
                    WorkflowTemplates(path)
                self.assertEqual(
                    raised.exception.details["reason_code"],
                    detail_digest("workflow_requirement_unsatisfied"),
                )

    def test_boolean_schema_versions_fail_schema_and_runtime(self):
        root = KERNEL_REFERENCES
        cases = (
            (
                "workflow-classes.json", "workflow-classes-schema.json",
                lambda path: WorkflowTemplates(path),
            ),
            (
                "workflow-policy.json", "workflow-policy-schema.json",
                lambda path: load_policy(path),
            ),
        )
        for default_name, schema_name, load in cases:
            payload = json.loads((root / default_name).read_text(encoding="utf-8"))
            schema = json.loads((root / schema_name).read_text(encoding="utf-8"))
            payload["schema_version"] = True
            with self.subTest(default=default_name):
                self.assertFalse(schema_matches(payload, schema))
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / default_name
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(InvalidSchemaError) as raised:
                        load(path)
                    self.assertEqual(
                        raised.exception.details["reason_code"],
                        detail_digest("unsupported_policy_version"),
                    )

    def test_gate_policy_snapshots_and_revalidates_injected_policy_document(self):
        document = load_policy()
        gate_policy = GatePolicy(policy_document=document)
        object.__setattr__(document, "risk_human_approval", ())
        decision = gate_policy.decide(
            WorkflowClass.HOTFIX, "risk", (), WorkflowContext(risk="high"),
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.human_required)

        for field in ("risk_human_approval", "workflow_safety_anchor"):
            malformed = load_policy()
            object.__setattr__(malformed, field, object())
            with self.subTest(field=field), self.assertRaises(
                InvalidSchemaError,
            ) as raised:
                GatePolicy(policy_document=malformed)
            self.assertEqual(
                raised.exception.details["reason_code"],
                detail_digest("invalid_policy_document"),
            )

        malformed_anchor = load_policy()
        anchor = malformed_anchor.workflow_safety_anchor
        cleanup = dict(anchor["common"][0])
        cleanup["unexpected"] = True
        object.__setattr__(malformed_anchor, "workflow_safety_anchor", {
            "schema_version": anchor["schema_version"],
            "common": (cleanup,),
            "classes": anchor["classes"],
            "promotion": anchor["promotion"],
        })
        with self.assertRaises(InvalidSchemaError) as raised:
            GatePolicy(policy_document=malformed_anchor)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("invalid_policy_document"),
        )

    def test_canonical_safety_anchor_rejects_removed_cleanup_and_promotion(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))

        no_cleanup = json.loads(json.dumps(base))
        no_cleanup["classes"]["chore"]["nodes"][-1]["id"] = "finish"

        no_promotion = json.loads(json.dumps(base))
        no_promotion["promotion"]["investigation"]["nodes"].pop(0)
        no_promotion["promotion"]["investigation"]["nodes"][0]["depends_on"] = [
            "evidence_gathering"
        ]

        for payload in (no_cleanup, no_promotion):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "classes.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(InvalidSchemaError):
                    WorkflowTemplates(path)

    def test_anthropic_native_constraint_requires_claude_native_dispatch(self):
        source = KERNEL_REFERENCES / "workflow-classes.json"
        base = json.loads(source.read_text(encoding="utf-8"))
        for executor, capability, dispatch in (
            ("codex", "anthropic_native_execution", "native_dispatch"),
            ("claude", "anthropic_native_execution", None),
        ):
            payload = json.loads(json.dumps(base))
            node = payload["classes"]["security"]["nodes"][1]
            node["executor"] = executor
            node["required_capability"] = capability
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
            (KERNEL_REFERENCES / "workflow-classes-schema.json").read_text()
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
        source = KERNEL_REFERENCES / "workflow-classes.json"
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
