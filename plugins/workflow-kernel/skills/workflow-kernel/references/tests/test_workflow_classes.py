import json
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest
from workflow_kernel.adapters.base import WorkflowClass, WorkflowContext
from workflow_kernel.schema import InvalidSchemaError
from workflow_kernel.workflows import WorkflowTemplates


EXPECTED = {
    "chore": (
        ("assess", (), None),
        ("build", ("assess",), None),
        ("deterministic_validation", ("build",), "deterministic_validation"),
        ("review", ("deterministic_validation",), None),
        ("cleanup", ("review",), "cleanup"),
    ),
    "bug": (
        ("reproduce", (), None),
        ("build_fix", ("reproduce",), None),
        ("regression_validation", ("build_fix",), "deterministic_validation"),
        ("review", ("regression_validation",), None),
        ("cleanup", ("review",), "cleanup"),
    ),
    "feature": (
        ("assess", (), None),
        ("research_plan", ("assess",), "evidence"),
        ("build", ("research_plan",), None),
        ("validation", ("build",), "deterministic_validation"),
        ("review", ("validation",), None),
        ("requirements_evidence", ("review",), "evidence"),
        ("cleanup", ("requirements_evidence",), "cleanup"),
    ),
    "hotfix": (
        ("reproduce_impact", (), "evidence"),
        ("build", ("reproduce_impact",), None),
        ("focused_validation", ("build",), "deterministic_validation"),
        ("risk_gate", ("focused_validation",), "risk"),
        ("review", ("risk_gate",), None),
        ("cleanup", ("review",), "cleanup"),
    ),
    "security": (
        ("threat_risk_evidence", (), "evidence"),
        ("security_build", ("threat_risk_evidence",), None),
        ("validation", ("security_build",), "deterministic_validation"),
        ("security_review", ("validation",), "evidence"),
        ("human_gate", ("security_review",), "human_approval"),
        ("cleanup", ("human_gate",), "cleanup"),
    ),
    "investigation": (
        ("hypothesis", (), "evidence"),
        ("evidence_gathering", ("hypothesis",), "evidence"),
        ("conclusion_next_action", ("evidence_gathering",), "next_action"),
        ("cleanup", ("conclusion_next_action",), "cleanup"),
    ),
    "migration": (
        ("preflight", (), "evidence"),
        ("schema_data_change", ("preflight",), None),
        ("compatibility_validation", ("schema_data_change",), "deterministic_validation"),
        ("rollback_evidence", ("compatibility_validation",), "evidence"),
        ("review", ("rollback_evidence",), "evidence"),
        ("human_gate", ("review",), "human_approval"),
        ("cleanup", ("human_gate",), "cleanup"),
    ),
}


class WorkflowClassTests(unittest.TestCase):
    def test_all_workflow_classes_expand_to_exact_dependency_valid_graphs(self):
        templates = WorkflowTemplates()
        self.assertEqual({kind.value for kind in WorkflowClass}, set(EXPECTED))
        for kind in WorkflowClass:
            with self.subTest(kind=kind.value):
                nodes = templates.expand(kind, WorkflowContext())
                actual = tuple((node.node_id, node.dependencies, node.gate_kind) for node in nodes)
                self.assertEqual(actual, EXPECTED[kind.value])
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
                self.assertNotIn("credentials.py", repr(nodes))

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


if __name__ == "__main__":
    unittest.main()
