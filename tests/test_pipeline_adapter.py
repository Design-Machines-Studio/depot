import json
import copy
import unittest
from pathlib import Path

from workflow_kernel.model import BuilderOutcome, BuilderSessionDecision, HostCapabilities, HostCapability, ResumeStateContext, WorkflowClass
from workflow_kernel.pipeline_adapter import translate_builder_decision, translate_manifest, translate_pipeline_receipts


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


class PipelineAdapterTests(unittest.TestCase):
    def profile(self):
        return HostCapabilities("codex", frozenset())

    def manifest(self, workflow_class="feature"):
        result = {
            "feature": "Pipeline 1", "executionMode": "codex_native",
            "changedPaths": ["src/app.py"],
            "chunks": [
                {"id": "chunk-b", "dependsOn": ["chunk-a"]},
                {"id": "chunk-a", "dependsOn": []},
            ],
            "executionPlan": {"levels": [
                {"level": 0, "strategy": "sequential", "chunks": ["chunk-b"]},
                {"level": 1, "strategy": "sequential", "chunks": ["chunk-a"]},
            ]},
        }
        if workflow_class is not None:
            result["workflowClass"] = workflow_class
        return result

    def test_recomputes_levels_from_authoritative_chunks_and_reports_cached_disagreement(self):
        spec = translate_manifest(self.manifest(), self.profile())
        self.assertEqual(spec.run_id, "pipeline-1")
        self.assertEqual(spec.execution_levels, (("chunk-a",), ("chunk-b",)))
        self.assertTrue(spec.execution_plan_disagreement)
        self.assertEqual(tuple(chunk.node_id for chunk in spec.chunks), ("chunk-b", "chunk-a"))

    def test_checked_in_manifest_translates_with_canonical_feature_and_object_plan(self):
        root = next(parent for parent in Path(__file__).parents if (parent / "plans" / "ai-developer-workflow-kernel" / "manifest.json").is_file())
        manifest = json.loads((root / "plans" / "ai-developer-workflow-kernel" / "manifest.json").read_text())
        spec = translate_manifest(manifest, self.profile())
        self.assertEqual(spec.run_id, "ai-developer-workflow-kernel")
        self.assertEqual(len(spec.execution_levels), 5)
        self.assertFalse(spec.execution_plan_disagreement)

    def test_run_spec_dict_retains_policy_and_gate_fields(self):
        encoded = translate_manifest(self.manifest("security"), self.profile()).to_dict()
        self.assertEqual(encoded["workflow_class"], "security")
        self.assertEqual(encoded["execution_mode"], "codex_native")
        for node in encoded["nodes"]:
            self.assertIn("gate_decision", node)
            self.assertIn("required_capability", node)
            self.assertIn("required_dispatch_capability", node)
            self.assertIn("executor_overridable", node)

    def test_all_workflow_classes_and_legacy_default_survive_translation(self):
        for value in ("chore", "bug", "feature", "hotfix", "security", "investigation", "migration"):
            with self.subTest(value=value):
                spec = translate_manifest(self.manifest(value), self.profile())
                self.assertEqual(spec.workflow_class, WorkflowClass(value))
                self.assertFalse(spec.workflow_class_defaulted)
                self.assertTrue(spec.nodes)
        legacy = translate_manifest(self.manifest(None), self.profile())
        self.assertEqual(legacy.workflow_class, WorkflowClass.FEATURE)
        self.assertTrue(legacy.workflow_class_defaulted)
        with self.assertRaises(ValueError):
            translate_manifest(self.manifest("unknown"), self.profile())

    def test_pipeline_receipts_map_named_stages_and_keep_authoritative_refs(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        events = translate_pipeline_receipts(receipts)
        self.assertEqual(len(events), len(receipts))
        self.assertEqual([event.payload["stage"] for event in events], [item["stage"] for item in receipts])
        self.assertTrue(all(event.kind == "evidence.recorded" for event in events))
        self.assertTrue(all(event.payload["authoritative_receipt"] in event.payload["evidence"] for event in events))

    def test_receipt_without_authoritative_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(({"run_id": "r", "sequence": 0, "stage": "run_summary", "status": "succeeded", "occurred_at": "2026-07-14T00:00:00Z"},))

    def test_receipts_require_one_run_contiguous_order_and_context_continuity(self):
        original = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        mutations = []
        duplicate = copy.deepcopy(original); duplicate[1]["sequence"] = 0; mutations.append(duplicate)
        gap = copy.deepcopy(original); gap[1]["sequence"] = 2; mutations.append(gap)
        reordered = copy.deepcopy(original); reordered[0], reordered[1] = reordered[1], reordered[0]; mutations.append(reordered)
        mixed_run = copy.deepcopy(original); mixed_run[-1]["run_id"] = "other"; mutations.append(mixed_run)
        mixed_class = copy.deepcopy(original); mixed_class[-1]["workflow_class"] = "bug"; mutations.append(mixed_class)
        mixed_mode = copy.deepcopy(original); mixed_mode[-1]["execution_mode"] = "codex_native"; mutations.append(mixed_mode)
        for receipts in mutations:
            with self.subTest(receipts=receipts[:2]), self.assertRaises(ValueError):
                translate_pipeline_receipts(receipts)

    def test_receipts_validate_workflow_class_and_preserve_default_provenance(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        invalid = copy.deepcopy(receipts)
        for receipt in invalid:
            receipt["workflow_class"] = "not-a-workflow-class"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(invalid)
        legacy = copy.deepcopy(receipts)
        for receipt in legacy:
            receipt.pop("workflow_class", None)
        events = translate_pipeline_receipts(legacy)
        self.assertTrue(all(event.payload["workflow_class_defaulted"] for event in events))
        self.assertTrue(all(event.payload["workflow_class"] == "feature" for event in events))
        explicit = copy.deepcopy(receipts)
        for receipt in explicit:
            receipt["workflow_class_defaulted"] = True
        events = translate_pipeline_receipts(explicit)
        self.assertTrue(all(event.payload["workflow_class_defaulted"] for event in events))
        explicit[2]["workflow_class_defaulted"] = "true"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(explicit)

    def test_receipts_reject_false_default_provenance_without_a_class(self):
        # Finding 085: a receipt set that omits workflow_class derived the
        # default; it cannot explicitly claim workflow_class_defaulted=false.
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        derived = copy.deepcopy(receipts)
        for receipt in derived:
            receipt.pop("workflow_class", None)
            receipt["workflow_class_defaulted"] = False
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(derived)
        truthful = copy.deepcopy(receipts)
        for receipt in truthful:
            receipt["workflow_class_defaulted"] = False
        events = translate_pipeline_receipts(truthful)
        self.assertFalse(any(event.payload["workflow_class_defaulted"] for event in events))
        inherited = copy.deepcopy(receipts)
        for receipt in inherited[1:]:
            receipt.pop("workflow_class", None)
            receipt["workflow_class_defaulted"] = False
        events = translate_pipeline_receipts(inherited)
        self.assertFalse(any(event.payload["workflow_class_defaulted"] for event in events))

    def test_isolation_strategy_is_a_separate_receipt_field_from_execution_mode(self):
        # Finding 083: sequential-on-branch is an isolation strategy carried
        # in its own receipt field; executionMode stays in the closed host set.
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        for receipt in receipts:
            receipt["isolationStrategy"] = "sequential-on-branch"
        events = translate_pipeline_receipts(receipts)
        self.assertEqual(events[2].payload["isolation_strategy"], "sequential-on-branch")
        self.assertEqual(events[2].payload["execution_mode"], "full_cli")
        self.assertEqual(events[3].payload["isolation_strategy"], "sequential-on-branch")
        self.assertNotIn("isolationStrategy", events[2].payload)
        widened = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        for receipt in widened:
            receipt["execution_mode"] = "sequential-on-branch"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(widened)

    def test_receipts_reject_invalid_or_discontinuous_isolation_strategy(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        invalid = copy.deepcopy(receipts)
        invalid[2]["isolationStrategy"] = "shared-main"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(invalid)
        wrong_type = copy.deepcopy(receipts)
        wrong_type[2]["isolationStrategy"] = {"mode": "sequential-on-branch"}
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(wrong_type)
        explicit_null = copy.deepcopy(receipts)
        for receipt in explicit_null:
            receipt["isolationStrategy"] = None
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(explicit_null)
        discontinuous = copy.deepcopy(receipts)
        for receipt in discontinuous:
            receipt["isolationStrategy"] = "sequential-on-branch"
        discontinuous[-1]["isolationStrategy"] = "per-chunk-worktree"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(discontinuous)

    def test_review_receipts_do_not_invent_pipeline_isolation(self):
        from workflow_kernel.dm_review_adapter import translate_review_receipts

        receipts = json.loads((FIXTURES / "dm-review.json").read_text())
        events = translate_review_receipts(receipts)
        self.assertTrue(events)
        self.assertTrue(all(
            "isolation_strategy" not in event.payload for event in events
        ))
        for receipt in receipts:
            receipt["isolationStrategy"] = None
        with self.assertRaises(ValueError):
            translate_review_receipts(receipts)

    def test_documented_camelcase_execution_context_is_normalized(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        for receipt in receipts:
            receipt["executionMode"] = receipt.pop("execution_mode")
            receipt["workflowClass"] = receipt.pop("workflow_class")
            receipt["workflowClassDefaulted"] = False
            receipt["isolationStrategy"] = "per-chunk-worktree"
        events = translate_pipeline_receipts(receipts)
        self.assertTrue(all(event.payload["execution_mode"] == "full_cli" for event in events))
        self.assertTrue(all(event.payload["workflow_class"] == "feature" for event in events))
        self.assertTrue(all(not event.payload["workflow_class_defaulted"] for event in events))
        self.assertTrue(all(
            event.payload["isolation_strategy"] == "per-chunk-worktree"
            for event in events
        ))
        conflicting = copy.deepcopy(receipts)
        conflicting[0]["execution_mode"] = "codex_native"
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)

    def test_model_used_alias_normalizes_to_canonical_model_field(self):
        # Finding 087: documented modelUsed descent evidence feeds the
        # canonical model field instead of being silently dropped.
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2]["modelUsed"] = "claude-opus-4-8"
        event = translate_pipeline_receipts(receipts)[2]
        self.assertEqual(event.payload["model"], "claude-opus-4-8")
        self.assertNotIn("modelUsed", event.payload)
        conflicting = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        conflicting[2].update({"modelUsed": "claude-opus-4-8", "model": "gpt-5.6-sol"})
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)

    def test_receipt_redaction_preserves_safe_routing_facts_and_drops_secret_shapes(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2].update({
            "requested_provider": "claude", "attempted_provider": "claude",
            "implemented_by": "claude", "fallback_path": ["claude"],
            "lane": "builder", "password": "never-show", "authorization": "Bearer never-show",
        })
        event = translate_pipeline_receipts(receipts)[2]
        self.assertEqual(event.payload["requested_provider"], "claude")
        self.assertEqual(event.payload["implemented_by"], "claude")
        self.assertNotIn("password", event.payload)
        self.assertNotIn("authorization", event.payload)
        self.assertNotIn("never-show", repr(event.payload))

    def test_documented_camelcase_receipt_fields_are_preserved_not_dropped(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        receipts[2].update({
            "requestedProvider": "claude", "attemptedProvider": "openrouter",
            "implementedBy": "claude", "fallbackReason": "provider_unavailable",
        })
        event = translate_pipeline_receipts(receipts)[2]
        self.assertEqual(event.payload["requested_provider"], "claude")
        self.assertEqual(event.payload["attempted_provider"], "openrouter")
        self.assertEqual(event.payload["implemented_by"], "claude")
        self.assertEqual(event.payload["fallback_reason"], "provider_unavailable")
        self.assertNotIn("requestedProvider", event.payload)
        agreeing = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        agreeing[2].update({
            "requestedProvider": "claude", "requested_provider": "claude",
        })
        self.assertEqual(
            translate_pipeline_receipts(agreeing)[2].payload["requested_provider"],
            "claude",
        )
        conflicting = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        conflicting[2].update({
            "requestedProvider": "claude", "requested_provider": "openrouter",
        })
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)

    def test_manifest_dual_keys_are_camel_primary_and_reject_conflicts(self):
        snake = self.manifest()
        snake["workflow_class"] = snake.pop("workflowClass")
        snake["execution_mode"] = snake.pop("executionMode")
        snake["changed_paths"] = snake.pop("changedPaths")
        spec = translate_manifest(snake, self.profile())
        self.assertEqual(spec.execution_mode, "codex_native")
        self.assertEqual(spec.workflow_class.value, "feature")
        conflicting = self.manifest()
        conflicting["execution_mode"] = "generic"
        with self.assertRaises(ValueError):
            translate_manifest(conflicting, self.profile())

    def test_hostile_mapping_callbacks_are_rejected_without_invocation(self):
        class Hostile(dict):
            def get(self, *_args, **_kwargs):
                raise AssertionError("callback invoked")
        with self.assertRaises(ValueError):
            translate_manifest(Hostile(self.manifest()), self.profile())
        with self.assertRaises(ValueError):
            translate_pipeline_receipts((Hostile(),))

    def test_builder_decision_is_observation_only_and_requires_authoritative_receipt(self):
        context = ResumeStateContext("run-1", "build", "attempt-1", "anthropic", "native", HostCapability.CLAUDE_EXECUTION)
        decision = BuilderSessionDecision(BuilderOutcome.NODE_GATE_BLOCKED, context)
        with self.assertRaises(ValueError):
            translate_builder_decision(decision, authoritative_receipt_reference="", sequence=3, occurred_at="2026-07-14T00:00:00Z")
        event = translate_builder_decision(decision, authoritative_receipt_reference="receipts/builder.json", sequence=3, occurred_at="2026-07-14T00:00:00Z")
        self.assertEqual(event.kind, "evidence.recorded")
        self.assertEqual(event.node_id, "build")
        self.assertIn("receipts/builder.json", event.payload["evidence"])
        self.assertIn("builder-observation/dispatch-blocked", event.payload["evidence"])
        self.assertFalse(event.payload["verification_contract_bound"])
        self.assertEqual(
            event.payload["verification_contract_provenance"],
            "legacy_default_absent",
        )

        digest = "sha256:" + "a" * 64
        current = translate_builder_decision(
            decision, authoritative_receipt_reference="receipts/builder.json",
            sequence=3, occurred_at="2026-07-14T00:00:00Z",
            current_contract_digest=digest, claimed_contract_digest=digest,
        )
        self.assertEqual(current.payload["contract_digest"], digest)
        self.assertTrue(current.payload["verification_contract_bound"])
        for claimed in (None, "sha256:" + "b" * 64, "not-a-digest"):
            with self.subTest(claimed=claimed), self.assertRaises(ValueError):
                translate_builder_decision(
                    decision,
                    authoritative_receipt_reference="receipts/builder.json",
                    sequence=3, occurred_at="2026-07-14T00:00:00Z",
                    current_contract_digest=digest,
                    claimed_contract_digest=claimed,
                )

    def test_contract_receipts_are_semantic_contiguous_and_current(self):
        first = "sha256:" + "a" * 64
        second = "sha256:" + "b" * 64

        def contract_receipt(stage, sequence, digest, revision, previous):
            return {
                "run_id": "run-1", "sequence": sequence, "stage": stage,
                "occurred_at": f"2026-07-14T00:00:0{sequence}Z",
                "authoritative_receipt": f"receipts/{sequence}.json",
                "workflow_class": "feature", "execution_mode": "generic",
                "contract_id": "contract-1", "schema_version": 1,
                "revision": revision, "contract_digest": digest,
                "contract_ref": (
                    "verification-contracts/sha256-"
                    + digest.removeprefix("sha256:") + ".json"
                ),
                "previous_contract_digest": previous,
                "reason_code": "approved_revision",
                "human_approval_evidence_ref": "approvals/reviewer.json",
            }

        receipts = [
            contract_receipt(
                "verification_contract_bound", 0, first, 1, None,
            ),
            contract_receipt(
                "verification_contract_revised", 1, second, 2, first,
            ),
            {
                "run_id": "run-1", "sequence": 2, "stage": "dispatch",
                "occurred_at": "2026-07-14T00:00:02Z",
                "authoritative_receipt": "receipts/2.json",
                "workflow_class": "feature", "execution_mode": "generic",
                "contract_digest": second, "status": "completed",
            },
        ]
        events = translate_pipeline_receipts(receipts)
        self.assertIn("verification_contract_bound", events[0].payload["evidence"])
        self.assertIn("verification_contract_revised", events[1].payload["evidence"])
        self.assertEqual(events[1].payload["revision"], 2)
        self.assertEqual(events[1].payload["previous_contract_digest"], first)
        self.assertEqual(events[2].payload["contract_digest"], second)
        self.assertTrue(all(
            event.payload["verification_contract_provenance"]
            == "authoritative_receipt"
            for event in events
        ))

        prebinding = copy.deepcopy(receipts)
        prebinding.insert(0, {
            "run_id": "run-1", "sequence": 0, "stage": "manifest_validation",
            "occurred_at": "2026-07-14T00:00:00Z",
            "authoritative_receipt": "receipts/prebinding.json",
            "workflow_class": "feature", "execution_mode": "generic",
            "status": "completed",
        })
        for sequence, receipt in enumerate(prebinding):
            receipt["sequence"] = sequence
        translated = translate_pipeline_receipts(prebinding)
        self.assertEqual(
            translated[0].payload["verification_contract_provenance"],
            "pre_binding",
        )
        for stage in (
            "dispatch", "deterministic_validation", "evaluation_gate",
            "browser_verification", "merge_disposition", "chunk_cleanup",
            "requirements_cross_check", "terminal_reconciliation", "run_summary",
        ):
            bypass = copy.deepcopy(prebinding)
            bypass[0]["stage"] = stage
            with self.subTest(prebinding_stage=stage), self.assertRaises(ValueError):
                translate_pipeline_receipts(bypass)

        for snake, camel in (
            ("schema_version", "schemaVersion"),
            ("revision", "contractRevision"),
        ):
            conflicting_type = copy.deepcopy(receipts)
            conflicting_type[0][camel] = True
            with self.subTest(alias=camel), self.assertRaises(ValueError):
                translate_pipeline_receipts(conflicting_type)

            calls = []

            class Hostile:
                def __eq__(self, _other):
                    calls.append("equality")
                    raise RuntimeError("sk-secret-equality")

            hostile = copy.deepcopy(receipts)
            hostile[0][snake] = Hostile()
            hostile[0][camel] = Hostile()
            with self.subTest(hostile_alias=camel), self.assertRaises(ValueError) as raised:
                translate_pipeline_receipts(hostile)
            self.assertEqual(calls, [])
            self.assertNotIn("sk-secret-equality", repr(raised.exception))

        for name, mutate in (
            ("revision_jump", lambda value: value[1].update({"revision": 3})),
            ("stale_previous", lambda value: value[1].update({
                "previous_contract_digest": "sha256:" + "c" * 64,
            })),
            ("stale_builder", lambda value: value[2].update({
                "contract_digest": first,
            })),
            ("malformed_digest", lambda value: value[0].update({
                "contract_digest": "sha256:not-a-digest",
            })),
            ("changed_contract_id", lambda value: value[1].update({
                "contract_id": "other-contract",
            })),
            ("missing_builder_digest", lambda value: value[2].pop("contract_digest")),
            ("unknown_contract_key", lambda value: value[0].update({
                "contract_secret": "must-not-echo",
            })),
            ("unknown_version", lambda value: value[0].update({
                "schema_version": 2,
            })),
        ):
            candidate = copy.deepcopy(receipts)
            mutate(candidate)
            with self.subTest(name=name), self.assertRaises(ValueError) as raised:
                translate_pipeline_receipts(candidate)
            self.assertNotIn("must-not-echo", repr(raised.exception))

    def test_contract_alias_conflicts_and_legacy_absence_fail_closed(self):
        legacy = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        events = translate_pipeline_receipts(legacy)
        self.assertTrue(all(
            event.payload["verification_contract_provenance"]
            == "legacy_default_absent"
            and not event.payload["verification_contract_bound"]
            and "verification_contract_bound" not in event.payload["evidence"]
            for event in events
        ))

        mixed = copy.deepcopy(legacy)
        mixed[0]["contractDigest"] = "sha256:" + "a" * 64
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(mixed)

        conflicting = copy.deepcopy(legacy)
        conflicting[0].update({
            "contractDigest": "sha256:" + "a" * 64,
            "contract_digest": "sha256:" + "b" * 64,
        })
        with self.assertRaises(ValueError):
            translate_pipeline_receipts(conflicting)


if __name__ == "__main__":
    unittest.main()
