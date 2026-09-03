import copy
import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests import KERNEL_REFERENCES


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"
SCOPE_ID = "a" * 64



def shadow_artifact(role, run_spec, events=None):
    value = {
        "schema_version":1, "artifact_role":role,
        "observation_type":"pipeline", "run_spec":run_spec,
        "event_count":0 if events is None else len(events),
        "observation_only":True,
    }
    if events is not None:
        value["events"] = events
    if role == "independent_prediction":
        encoded = json.dumps(
            run_spec, sort_keys=True, separators=(",", ":"),
        ).encode()
        value["run_spec_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
        event_documents = [] if events is None else events
        encoded_events = json.dumps(
            event_documents, sort_keys=True, separators=(",", ":"),
        ).encode()
        value["event_digest"] = "sha256:" + hashlib.sha256(encoded_events).hexdigest()
        value["source_digest"] = "sha256:" + "0" * 64
    return value


def verification_contract(*, marker=None):
    argv = ["python3.12", "-m", "unittest", "tests.test_example"]
    if marker is not None:
        argv = ["python3.12", "-c", f"open({str(marker)!r}, 'w').write('ran')"]
    return {
        "schema_version": 1, "contract_id": "adaptive-fusion-verification",
        "revision": 1, "previous_contract_digest": None,
        "requirements": [{
            "id": "REQ-001", "source_ref": "original-prompt.md#key-requirements",
            "statement": "The requested behavior is verified.",
        }],
        "prohibited_regressions": [{
            "id": "REG-001", "source_ref": "assessment.html#current-state",
            "statement": "Existing behavior remains available.",
        }],
        "checks": [{
            "id": "CHK-001", "argv": argv,
            "proves_requirement_ids": ["REQ-001"],
            "proves_regression_ids": ["REG-001"],
            "baseline_expectation": "must_fail",
        }],
        "persona_case_ids": [], "browser_case_ids": [],
        "verification_profile_id": None, "verification_profile_digest": None,
        "manual_requirements": [],
        "revision_justification": {
            "reason_code": "initial_binding", "summary": "Initial binding.",
            "added_obligation_ids": [
                "PROOF:CHK-001:REQ-001", "PROOF:CHK-001:REG-001",
                "REG-001", "REQ-001",
            ],
            "retained_obligation_ids": [], "removed_obligation_ids": [],
        },
    }


class RuntimeCliTests(unittest.TestCase):
    def run_cli(self, *args, env_extra=None):
        env = dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES))
        if env_extra:
            env.update(env_extra)
        return subprocess.run([sys.executable, "-m", "workflow_kernel", *map(str, args)], text=True, capture_output=True, env=env, check=False)

    def init_repository_scope(self, root):
        subprocess.run(["git", "init", "-q", root], check=True)
        lease_root = root / ".workflow-kernel"
        lease_root.mkdir(exist_ok=True)
        repo_stat = root.stat()
        lease_stat = lease_root.stat()
        (lease_root / "repository-scope.json").write_text(json.dumps({
            "schema_version": 1,
            "scope_id": SCOPE_ID,
            "repo_root": {
                "path": str(root.resolve()), "device": repo_stat.st_dev,
                "inode": repo_stat.st_ino,
            },
            "lease_root": {
                "path": str(lease_root.resolve()), "device": lease_stat.st_dev,
                "inode": lease_stat.st_ino,
            },
        }))
        return lease_root

    def test_export_review_contributions_is_launcher_owned_and_cardinality_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            decisions = root / "decisions.json"
            raw_findings = root / "raw-findings.json"
            lane_receipts = root / "lane-receipts.json"
            raw_lane_outputs = root / "raw-lane-outputs.json"
            receipts = root / "receipts.json"
            output = root / "output.json"
            state_dir = root / "state"
            state_dir.mkdir()
            request.write_text(json.dumps({
                "run_id": "review-export", "requested_lanes": ["security"],
                "mode": "full", "execution_mode": "generic",
            }), encoding="utf-8")
            decisions.write_text(json.dumps({
                "schema_version": 1, "artifact_role": "synthesis_decisions",
                "run_id": "review-export", "source_finding_count": 1,
                "occurred_at": "2026-07-14T00:01:00Z",
                "decisions": [{
                    "source_finding_id": "source-1",
                    "finding_path": "internal/review.py",
                    "finding_anchor": "review.finding",
                    "finding_category": "trust boundary",
                    "finding_root_cause": "caller supplied identity",
                    "finding_disposition": "retained", "agreement": "unique",
                    "decision_reason_code": "retained-unique",
                    "reviewer": "security", "lane": "security",
                    "source_severity": "P2",
                    "requested_provider": "openai", "attempted_provider": "openai",
                    "implemented_by": "codex", "provider": "openai",
                    "model": "gpt-5.6-sol", "evidence_ref": "raw/security.md",
                    "implementer_family": "openai", "reviewer_family": "openai",
                    "resolution_reason": "same-family-standard-review",
                    "attempt": 1, "occurred_at": "2026-07-14T00:00:00Z",
                }],
            }), encoding="utf-8")
            raw_findings.write_text(json.dumps({
                "schema_version": 1, "artifact_role": "raw_finding_inventory",
                "run_id": "review-export", "findings": [{
                    "source_finding_id": "source-1", "reviewer": "security",
                    "lane": "security", "source_severity": "P2",
                    "evidence_ref": "raw/security.md",
                    "finding_path": "internal/review.py",
                    "finding_anchor": "review.finding",
                    "finding_category": "trust boundary",
                    "finding_root_cause": "caller supplied identity",
                }],
            }), encoding="utf-8")
            raw_value = json.loads(raw_findings.read_text(encoding="utf-8"))
            lane_output = {
                "reviewer": "security", "lane": "security",
                "findings": raw_value["findings"],
            }
            lane_output_digest = hashlib.sha256(json.dumps(
                lane_output, sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest()
            raw_lane_outputs.write_text(json.dumps({
                "schema_version": 1,
                "artifact_role": "review_lane_raw_outputs",
                "run_id": "review-export", "outputs": [lane_output],
            }), encoding="utf-8")
            lane_receipts.write_text(json.dumps({
                "schema_version": 1, "artifact_role": "review_lane_receipts",
                "run_id": "review-export", "lanes": [{
                    "reviewer": "security", "lane": "security",
                    "requested_provider": "openai", "attempted_provider": "openai",
                    "implemented_by": "codex", "provider": "openai",
                    "model": "gpt-5.6-sol", "evidence_refs": ["raw/security.md"],
                    "implementer_family": "openai", "reviewer_family": "openai",
                    "resolution_reason": "same-family-standard-review",
                    "raw_output_ref": (
                        "contribution-inputs/raw-lane-output-sha256-"
                        + lane_output_digest + ".json"
                    ),
                    "raw_output_digest": "sha256:" + lane_output_digest,
                    "finding_count": 1,
                }],
            }), encoding="utf-8")
            receipts.write_text("[]\n", encoding="utf-8")
            result = self.run_cli(
                "export-review-contributions", "--request", request,
                "--decisions", decisions, "--raw-findings", raw_findings,
                "--lane-receipts", lane_receipts,
                "--raw-lane-outputs", raw_lane_outputs, "--receipts", receipts,
                "--state-dir", state_dir, "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(exported), 2)
            self.assertRegex(
                exported[0]["canonical_finding_id"],
                r"^finding-v1:sha256\([0-9a-f]{64}\)$",
            )
            self.assertEqual(exported[1]["stage"], "finding_contribution_coverage")
            self.assertEqual(
                len(list((state_dir / "contribution-inputs").glob("*.json"))), 5,
            )

            for name, raw in (
                ("duplicate", '[{"sequence":0,"sequence":1}]'),
                ("non-finite", '[{"sequence":NaN}]'),
            ):
                with self.subTest(name=name):
                    ambiguous = root / (name + "-review-receipts.json")
                    ambiguous.write_text(raw, encoding="utf-8")
                    observe_state = root / (name + "-observe-state")
                    observe_state.mkdir()
                    observed = self.run_cli(
                        "observe-review", "--request", request,
                        "--receipts", ambiguous, "--state-dir", observe_state,
                    )
                    self.assertEqual(observed.returncode, 2)
                    self.assertFalse(
                        (observe_state / "review-shadow-observation.json").exists(),
                    )

                    export_state = root / (name + "-export-state")
                    export_state.mkdir()
                    export_output = root / (name + "-export.json")
                    exported_ambiguous = self.run_cli(
                        "export-review-contributions", "--request", request,
                        "--decisions", decisions,
                        "--raw-findings", raw_findings,
                        "--lane-receipts", lane_receipts,
                        "--raw-lane-outputs", raw_lane_outputs,
                        "--receipts", ambiguous,
                        "--state-dir", export_state, "--output", export_output,
                    )
                    self.assertEqual(exported_ambiguous.returncode, 2)
                    self.assertFalse(export_output.exists())
                    self.assertFalse(
                        (export_state / "contribution-inputs").exists(),
                    )

            unsafe_state = root / "unsafe-state"
            unsafe_state.mkdir()
            unsafe_decisions = json.loads(decisions.read_text(encoding="utf-8"))
            unsafe_decisions["decisions"][0]["model"] = (
                "https://user:password@example.invalid/review?token=secret"
            )
            decisions.write_text(json.dumps(unsafe_decisions), encoding="utf-8")
            rejected = self.run_cli(
                "export-review-contributions", "--request", request,
                "--decisions", decisions, "--raw-findings", raw_findings,
                "--lane-receipts", lane_receipts,
                "--raw-lane-outputs", raw_lane_outputs, "--receipts", receipts,
                "--state-dir", unsafe_state, "--output", root / "unsafe.json",
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertFalse((unsafe_state / "contribution-inputs").exists())
            self.assertFalse((root / "unsafe.json").exists())

    def test_contribution_artifact_store_rejects_symlink_and_directory_swap(self):
        from workflow_kernel.cli import _seal_contribution_artifacts

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            victim = root / "victim"
            victim.mkdir()
            (state / "contribution-inputs").symlink_to(victim, target_is_directory=True)
            reference = "contribution-inputs/synthesis-decisions-sha256-" + "a" * 64 + ".json"
            with self.assertRaises(OSError):
                _seal_contribution_artifacts(state, {reference: {"safe": True}})
            self.assertEqual(list(victim.iterdir()), [])

            (state / "contribution-inputs").unlink()
            real_write = os.write
            swapped = False

            def swap_directory(descriptor, value):
                nonlocal swapped
                count = real_write(descriptor, value)
                if not swapped:
                    swapped = True
                    (state / "contribution-inputs").rename(state / "stale-inputs")
                    (state / "contribution-inputs").mkdir()
                return count

            with mock.patch("workflow_kernel.cli.os.write", side_effect=swap_directory):
                with self.assertRaises(OSError):
                    _seal_contribution_artifacts(state, {reference: {"safe": True}})
            self.assertEqual(list((state / "contribution-inputs").iterdir()), [])
            self.assertEqual(list((state / "stale-inputs").iterdir()), [])

    def init_lifecycle(self, root, run_id="pipeline-1"):
        self.init_repository_scope(root)
        result = self.run_cli(
            "init", root / ".workflow-kernel" / "runs" / run_id,
            "--run-id", run_id, "--mode", "shadow",
            "--occurred-at", "2026-07-15T00:00:00Z",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def start_lifecycle(self, root, run_id="pipeline-1"):
        event = json.dumps({
            "schema_version": 1, "sequence": 2, "run_id": run_id,
            "node_id": None, "kind": "run.started",
            "occurred_at": "2026-07-15T00:00:02Z", "payload": {},
        })
        result = self.run_cli(
            "append", root / ".workflow-kernel" / "runs" / run_id,
            "--event", event,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_decide_validation_retry_uses_and_updates_authoritative_run_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "retry-run")
            run_dir = root / ".workflow-kernel" / "runs" / "retry-run"
            first = self.run_cli(
                "decide-validation-retry", "--state-dir", run_dir,
                "--reason", "deterministic_validation_failure",
                "--signature", "failure-a",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(first.stdout)["reason_code"], "retry_allowed")
            second = self.run_cli(
                "decide-validation-retry", "--state-dir", run_dir,
                "--reason", "deterministic_validation_failure",
                "--signature", "failure-b",
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                json.loads(second.stdout)["reason_code"], "retry_budget_exhausted",
            )
            events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text().splitlines()]
            self.assertEqual(
                [event["payload"]["stage"] for event in events[1:]],
                ["validation_retry_decided", "validation_retry_decided"],
            )

    def test_decide_validation_retry_rejects_hostile_signature_without_write(self):
        secret = "sk-secret-ledger-value"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "retry-run")
            run_dir = root / ".workflow-kernel" / "runs" / "retry-run"
            before = (run_dir / "events.jsonl").read_bytes()
            result = self.run_cli(
                "decide-validation-retry", "--state-dir", run_dir,
                "--reason", "cleanup", "--signature", secret,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual((run_dir / "events.jsonl").read_bytes(), before)

    def append_contract_binding(self, run_dir, contract, stage):
        from workflow_kernel.behavioral_contract import contract_digest

        digest = contract_digest(contract)
        reference = (
            "verification-contracts/sha256-"
            + digest.removeprefix("sha256:") + ".json"
        )
        justification = contract["revision_justification"]
        sequence = len((run_dir / "events.jsonl").read_text().splitlines())
        occurred_at = (
            datetime.now(timezone.utc) + timedelta(seconds=1)
        ).isoformat().replace("+00:00", "Z")
        event = json.dumps({
            "schema_version": 1, "sequence": sequence,
            "run_id": run_dir.name, "node_id": None,
            "kind": "evidence.recorded", "occurred_at": occurred_at,
            "payload": {
                "stage": stage, "contract_id": contract["contract_id"],
                "schema_version": contract["schema_version"],
                "revision": contract["revision"], "contract_digest": digest,
                "contract_ref": reference,
                "previous_contract_digest": contract["previous_contract_digest"],
                "reason_code": justification["reason_code"],
                "verification_profile_id": contract["verification_profile_id"],
                "verification_profile_digest": contract["verification_profile_digest"],
                "verification_profile_ref": None,
                "evidence": [reference],
            },
        })
        result = self.run_cli("append", run_dir, "--event", event)
        self.assertEqual(result.returncode, 0, result.stderr)
        return digest, reference

    def test_observe_pipeline_writes_shadow_artifact_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature", "executionMode": "codex_native",
                "chunks": [{"id": "chunk-a", "dependsOn": []}], "executionPlan": {"levels": [{"level": 0, "strategy": "sequential", "chunks": ["chunk-a"]}]},
            }))
            prediction = root / "prediction.json"
            predicted = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            predicted[0]["prediction_basis"] = "pre-action"
            prediction.write_text(json.dumps(predicted))
            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest,
                "--prediction-receipts", prediction,
                "--state-dir", root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.start_lifecycle(root)
            result = self.run_cli("observe-pipeline", "--manifest", manifest, "--receipts", FIXTURES / "pipeline-codex.json", "--state-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads((root / "pipeline-shadow-observation.json").read_text())
            self.assertEqual(artifact["observation_type"], "pipeline")
            self.assertEqual(artifact["artifact_role"], "authoritative_observation")
            self.assertEqual(artifact["run_spec"]["workflow_class"], "feature")
            self.assertEqual(artifact["event_count"], 11)

    def test_device_renumbered_schema_one_scope_keeps_old_and_new_runs_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id = "portable-run"
            self.init_lifecycle(root, run_id)
            run_dir = root / ".workflow-kernel" / "runs" / run_id
            scope_path = root / ".workflow-kernel" / "repository-scope.json"
            stored = json.loads(scope_path.read_text(encoding="utf-8"))
            scope_id = stored["scope_id"]
            stored["repo_root"]["device"] += 1000
            stored["lease_root"]["device"] += 1000
            scope_path.write_text(json.dumps(stored, sort_keys=True), encoding="utf-8")
            scope_before = scope_path.read_bytes()

            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": run_id, "workflowClass": "feature",
                "executionMode": "codex_native",
                "chunks": [{"id": "chunk-a", "dependsOn": []}],
                "executionPlan": {"levels": [{
                    "level": 0, "strategy": "sequential", "chunks": ["chunk-a"],
                }]},
            }), encoding="utf-8")
            prediction = root / "prediction.json"
            predicted = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            predicted[0]["run_id"] = run_id
            predicted[0]["prediction_basis"] = "pre-action"
            for receipt in predicted[1:]:
                receipt["run_id"] = run_id
            prediction.write_text(json.dumps(predicted), encoding="utf-8")

            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline", "--manifest", manifest,
                "--prediction-receipts", prediction, "--state-dir", root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.start_lifecycle(root, run_id)
            validated = self.run_cli("validate", run_dir)
            self.assertEqual(validated.returncode, 0, validated.stderr)

            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", prediction, "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            comparison = root / "shadow-report.json"
            compared = self.run_cli(
                "compare", "--state-dir", root,
                "--authoritative-receipts", prediction, "--output", comparison,
            )
            self.assertEqual(compared.returncode, 0, compared.stderr)
            self.assertTrue(json.loads(comparison.read_text())["semantic_match"])

            new_run_id = "portable-new-run"
            initialized = self.run_cli(
                "init", root / ".workflow-kernel" / "runs" / new_run_id,
                "--run-id", new_run_id, "--mode", "shadow",
                "--occurred-at", "2026-07-15T00:10:00Z",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            new_event = json.loads((
                root / ".workflow-kernel" / "runs" / new_run_id / "events.jsonl"
            ).read_text().splitlines()[0])
            self.assertEqual(new_event["payload"]["repository_scope_id"], scope_id)
            self.assertEqual(new_event["payload"]["repository_root_device"], root.stat().st_dev)
            self.assertEqual(
                new_event["payload"]["lease_root_device"],
                (root / ".workflow-kernel").stat().st_dev,
            )

            argv = root / "argv.json"
            argv.write_text(json.dumps(["docker", "run", "alpine"]), encoding="utf-8")
            creation_path = root / "creation-plan.json"
            planned = self.run_cli(
                "plan-create", "--state-dir", run_dir, "--run-id", run_id,
                "--node-id", "chunk-a", "--lifecycle", "chunk",
                "--cleanup-policy", "stop-remove", "--argv-json", argv,
                "--output", creation_path,
            )
            self.assertEqual(planned.returncode, 0, planned.stderr)
            creation = json.loads(creation_path.read_text())
            self.assertEqual(
                creation["labels"]["com.designmachines.depot.repository-scope-id"],
                scope_id,
            )
            cleanup_path = root / "cleanup-plan.json"
            cleanup = self.run_cli(
                "plan-cleanup", "--state-dir", run_dir, "--run-id", run_id,
                "--node-id", "chunk-a", "--output", cleanup_path,
            )
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            self.assertEqual(
                json.loads(cleanup_path.read_text())["scope"]["repository_scope_id"],
                scope_id,
            )

            index_fixture = (
                Path(__file__).parent / "fixtures" / "observation-index" /
                "pipeline-complete-v1.json"
            )
            index_path = root / "observation-index.json"
            emitted = self.run_cli(
                "emit-observation-index", "--input", index_fixture,
                "--output", index_path,
            )
            self.assertEqual(emitted.returncode, 0, emitted.stderr)
            self.assertTrue(index_path.is_file())
            self.assertEqual(scope_path.read_bytes(), scope_before)

    def test_legacy_browser_reconciliation_writer_and_processing_paths_are_atomic(self):
        from workflow_kernel.cost_summary import validate_run_cost_summary

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads(
                (FIXTURES / "pipeline-legacy-browser-recovery.json").read_text()
            )
            self.assertRegex(
                source[1]["human_intervention_id"],
                r"\Abrowser-help-sha256:[0-9a-f]{64}\Z",
            )
            self.assertEqual(len(source[1]["missing_case_ids"]), 3)
            self.assertTrue(all(
                re.fullmatch(r"case-sha256:[0-9a-f]{64}", case_id)
                for case_id in source[1]["missing_case_ids"]
            ))
            ledger = root / "authoritative-receipts.json"
            ledger.write_text(json.dumps(source))
            appended = self.run_cli(
                "reconcile-legacy-browser",
                "--events", ledger,
                "--target-sequence", "1",
                "--occurred-at", "2026-01-01T00:09:00Z",
                "--authoritative-receipt", "receipts/reconciliation.json",
            )
            self.assertEqual(appended.returncode, 0, appended.stderr)
            reconciled = json.loads(ledger.read_text())
            self.assertEqual(reconciled[:-1], source)
            self.assertEqual(reconciled[-1]["sequence"], 9)

            before_duplicate = ledger.read_bytes()
            duplicate = self.run_cli(
                "reconcile-legacy-browser",
                "--events", ledger,
                "--target-sequence", "1",
                "--occurred-at", "2026-01-01T00:10:00Z",
                "--authoritative-receipt", "receipts/duplicate.json",
            )
            self.assertEqual(duplicate.returncode, 2)
            self.assertEqual(ledger.read_bytes(), before_duplicate)

            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "compat-run", "workflowClass": "feature",
                "executionMode": "generic", "chunks": [],
            }))
            self.init_lifecycle(root, "compat-run")
            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", ledger,
                "--state-dir", root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.start_lifecycle(root, "compat-run")

            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", ledger, "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            observation = root / "pipeline-shadow-observation.json"
            observation_events = json.loads(observation.read_text())["events"]
            self.assertEqual(observation_events[1]["payload"]["status"], "blocked")
            self.assertEqual(
                [event["payload"]["stage"] for event in observation_events[3:9]],
                [
                    "chunk", "run", "shadow_observation", "shadow_comparison",
                    "metrics", "cost_summary",
                ],
            )
            self.assertEqual(observation_events[3]["payload"]["status"], "failed")
            self.assertEqual(observation_events[4]["payload"]["status"], "skipped")

            comparison = root / "comparison.json"
            compared = self.run_cli(
                "compare", "--state-dir", root,
                "--authoritative-receipts", ledger,
                "--output", comparison,
            )
            self.assertEqual(compared.returncode, 0, compared.stderr)
            self.assertTrue(json.loads(comparison.read_text())["semantic_match"])

            metrics = root / "metrics.json"
            measured = self.run_cli(
                "metrics", "--events", ledger, "--output", metrics,
            )
            self.assertEqual(measured.returncode, 0, measured.stderr)
            self.assertEqual(json.loads(metrics.read_text())["event_count"], 10)

            cost = root / "run-cost-summary.json"
            costed = self.run_cli(
                "run-cost-summary", "--events", ledger, "--output", cost,
            )
            self.assertEqual(costed.returncode, 0, costed.stderr)
            validate_run_cost_summary(json.loads(cost.read_text()))

            invalid = copy.deepcopy(reconciled)
            invalid[-1]["target_receipt_digest"] = "sha256:" + "d" * 64
            invalid_ledger = root / "invalid-receipts.json"
            invalid_ledger.write_text(json.dumps(invalid))
            invalid_outputs = {
                "observation": root / "invalid-observation.json",
                "comparison": root / "invalid-comparison.json",
                "metrics": root / "invalid-metrics.json",
                "cost": root / "invalid-cost.json",
            }
            rejected_observation = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", invalid_ledger,
                "--state-dir", invalid_outputs["observation"],
            )
            self.assertEqual(rejected_observation.returncode, 2)
            rejected_comparison = self.run_cli(
                "compare", "--state-dir", root,
                "--authoritative-receipts", invalid_ledger,
                "--output", invalid_outputs["comparison"],
            )
            self.assertEqual(rejected_comparison.returncode, 2)
            rejected_metrics = self.run_cli(
                "metrics", "--events", invalid_ledger,
                "--output", invalid_outputs["metrics"],
            )
            self.assertEqual(rejected_metrics.returncode, 2)
            rejected_cost = self.run_cli(
                "run-cost-summary", "--events", invalid_ledger,
                "--output", invalid_outputs["cost"],
            )
            self.assertEqual(rejected_cost.returncode, 2)
            self.assertFalse(any(path.exists() for path in invalid_outputs.values()))

            malformed = root / "malformed.json"
            malformed.write_text("{not-json")
            malformed_before = malformed.read_bytes()
            rejected_writer = self.run_cli(
                "reconcile-legacy-browser", "--events", malformed,
                "--target-sequence", "1",
                "--occurred-at", "2026-01-01T00:04:00Z",
                "--authoritative-receipt", "receipts/reconciliation.json",
            )
            self.assertEqual(rejected_writer.returncode, 2)
            self.assertEqual(malformed.read_bytes(), malformed_before)
            error = json.loads(rejected_writer.stderr)
            self.assertEqual(error["error"]["code"], "invalid_schema")

            for name, ambiguous_value in (
                (
                    "duplicate-member",
                    b'[{"run_id":"first","run_id":"second"}]\n',
                ),
                ("non-finite", b'[{"sequence":NaN}]\n'),
            ):
                with self.subTest(name=name):
                    ambiguous = root / (name + ".json")
                    ambiguous.write_bytes(ambiguous_value)
                    ambiguous_before = ambiguous.read_bytes()
                    rejected_ambiguous = self.run_cli(
                        "reconcile-legacy-browser", "--events", ambiguous,
                        "--target-sequence", "0",
                        "--occurred-at", "2026-01-01T00:04:00Z",
                        "--authoritative-receipt", "receipts/reconciliation.json",
                    )
                    self.assertEqual(rejected_ambiguous.returncode, 2)
                    self.assertEqual(ambiguous.read_bytes(), ambiguous_before)
                    ambiguous_error = json.loads(rejected_ambiguous.stderr)
                    self.assertEqual(
                        ambiguous_error["error"]["code"], "invalid_schema",
                    )
                    self.assertNotIn(str(ambiguous), rejected_ambiguous.stderr)

            serialized = json.dumps(reconciled, separators=(",", ":"))
            for name, ambiguous_value in (
                (
                    "duplicate-target-member",
                    serialized.replace(
                        '"stage":"browser_recovery"',
                        '"stage":"wrong","stage":"browser_recovery"',
                        1,
                    ),
                ),
                (
                    "duplicate-claim-member",
                    serialized.replace(
                        '"target_stage":"browser_recovery"',
                        '"target_stage":"wrong","target_stage":"browser_recovery"',
                        1,
                    ),
                ),
            ):
                with self.subTest(name=name):
                    ambiguous = root / (name + ".json")
                    ambiguous.write_text(ambiguous_value)
                    observation_before = observation.read_bytes()
                    prediction_before = (
                        root / "pipeline-shadow-prediction.json"
                    ).read_bytes()
                    commands = {
                        "prediction": (
                            "bind-prediction", "--type", "pipeline",
                            "--manifest", manifest,
                            "--prediction-receipts", ambiguous,
                            "--state-dir", root,
                        ),
                        "observation": (
                            "observe-pipeline", "--manifest", manifest,
                            "--receipts", ambiguous, "--state-dir", root,
                        ),
                        "comparison": (
                            "compare", "--state-dir", root,
                            "--authoritative-receipts", ambiguous,
                            "--output", root / (name + "-comparison.json"),
                        ),
                        "metrics": (
                            "metrics", "--events", ambiguous,
                            "--output", root / (name + "-metrics.json"),
                        ),
                        "cost": (
                            "run-cost-summary", "--events", ambiguous,
                            "--output", root / (name + "-cost.json"),
                        ),
                    }
                    for command_name, argv in commands.items():
                        with self.subTest(command=command_name):
                            rejected = self.run_cli(*argv)
                            self.assertEqual(rejected.returncode, 2)
                            error = json.loads(rejected.stderr)
                            self.assertEqual(error["error"]["code"], "invalid_schema")
                    self.assertEqual(observation.read_bytes(), observation_before)
                    self.assertEqual(
                        (root / "pipeline-shadow-prediction.json").read_bytes(),
                        prediction_before,
                    )
                    self.assertFalse(any(
                        (root / (name + suffix)).exists()
                        for suffix in (
                            "-comparison.json", "-metrics.json", "-cost.json",
                        )
                    ))

    def test_prediction_and_observation_reject_decision_profile_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            high_profile = {
                "uncertainty": "high", "consequence": "high",
                "rationale": "Use bounded synthesis and stronger verification.",
            }
            low_profile = {
                "uncertainty": "low", "consequence": "low",
                "rationale": "Use the standard path.",
            }
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature",
                "decisionProfile": high_profile,
                "executionMode": "codex_native", "chunks": [],
            }))
            source = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            low = json.loads(json.dumps(source)); low[0]["decisionProfile"] = low_profile
            low_path = root / "low.json"; low_path.write_text(json.dumps(low))
            rejected = self.run_cli(
                "bind-prediction", "--type", "pipeline", "--manifest", manifest,
                "--prediction-receipts", low_path, "--state-dir", root,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertFalse((root / "pipeline-shadow-prediction.json").exists())

            high = json.loads(json.dumps(source)); high[0]["decisionProfile"] = high_profile
            high_path = root / "high.json"; high_path.write_text(json.dumps(high))
            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline", "--manifest", manifest,
                "--prediction-receipts", high_path, "--state-dir", root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.start_lifecycle(root)
            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", low_path, "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 2)
            self.assertFalse((root / "pipeline-shadow-observation.json").exists())

    def test_observe_accepts_identical_source_after_prestart_lifecycle_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature":"pipeline-1", "workflowClass":"feature",
                "executionMode":"codex_native", "chunks":[],
            }))
            prediction = root / "prediction.json"
            authoritative = root / "authoritative-at-different-path.json"
            document = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            prediction.write_text(json.dumps(document))
            authoritative.write_text(json.dumps(document))
            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", prediction,
                "--state-dir", root,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.start_lifecycle(root)
            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", authoritative, "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertTrue((root / "pipeline-shadow-observation.json").exists())

    def test_prediction_binding_rebuilds_missing_materialized_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature",
                "executionMode": "codex_native", "chunks": [],
            }))
            prediction = root / "prediction.json"
            prediction.write_text((FIXTURES / "pipeline-codex.json").read_text())
            state_path = (
                root / ".workflow-kernel" / "runs" / "pipeline-1" /
                "run-state.json"
            )
            state_path.unlink()

            bound = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", prediction,
                "--state-dir", root,
            )

            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.assertEqual(json.loads(state_path.read_text())["revision"], 2)

    def test_prediction_binding_retry_reconciles_publish_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature",
                "executionMode": "codex_native", "chunks": [],
            }))
            prediction = root / "prediction.json"
            prediction.write_text((FIXTURES / "pipeline-codex.json").read_text())
            args = SimpleNamespace(
                type="pipeline", manifest=manifest, request=None,
                prediction_receipts=prediction, state_dir=root,
            )
            from workflow_kernel.cli import command_bind_prediction
            from workflow_kernel.state import StateStore

            with mock.patch.object(
                    StateStore, "publish", side_effect=RuntimeError("interrupted")), \
                    mock.patch("workflow_kernel.cli._emit"), \
                    self.assertRaises(RuntimeError):
                command_bind_prediction(args)

            state_path = (
                root / ".workflow-kernel" / "runs" / "pipeline-1" /
                "run-state.json"
            )
            self.assertEqual(json.loads(state_path.read_text())["revision"], 1)
            retried = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", prediction,
                "--state-dir", root,
            )
            self.assertEqual(retried.returncode, 0, retried.stderr)
            self.assertEqual(json.loads(state_path.read_text())["revision"], 2)

    def test_independent_prediction_is_bound_once_and_terminal_observation_cannot_overwrite_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature":"pipeline-1","workflowClass":"feature",
                "executionMode":"codex_native","chunks":[],
            }))
            predicted = root / "prediction.json"
            values = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            values[2]["status"] = "failed"
            predicted.write_text(json.dumps(values))
            first = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", predicted,
                "--state-dir", root,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            prediction_path = root / "pipeline-shadow-prediction.json"
            bound = prediction_path.read_bytes()
            document = json.loads(bound)
            self.assertEqual(document["artifact_role"], "independent_prediction")
            self.assertTrue(document["event_digest"].startswith("sha256:"))
            self.start_lifecycle(root)
            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", FIXTURES / "pipeline-codex.json",
                "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            predicted.write_text((FIXTURES / "pipeline-codex.json").read_text())
            second = self.run_cli(
                "bind-prediction", "--type", "pipeline",
                "--manifest", manifest, "--prediction-receipts", predicted,
                "--state-dir", root,
            )
            self.assertEqual(second.returncode, 2, second.stderr)
            self.assertEqual(prediction_path.read_bytes(), bound)
            output = root / "parity.json"
            compared = self.run_cli(
                "compare", "--state-dir", root,
                "--authoritative-receipts", FIXTURES / "pipeline-codex.json",
                "--output", output,
            )
            self.assertEqual(compared.returncode, 5, compared.stderr)
            self.assertEqual(json.loads(output.read_text())["reason"], "kernel_prediction_gap")

    def test_compare_without_independent_prediction_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature":"pipeline-1","workflowClass":"feature",
                "executionMode":"codex_native","chunks":[],
            }))
            observed = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", FIXTURES / "pipeline-codex.json",
                "--state-dir", root,
            )
            self.assertEqual(observed.returncode, 2, observed.stderr)
            from workflow_kernel.model import HostCapabilities
            from workflow_kernel.pipeline_adapter import translate_manifest, translate_pipeline_receipts
            receipts = json.loads((FIXTURES / "pipeline-codex.json").read_text())
            spec = translate_manifest(
                json.loads(manifest.read_text()),
                HostCapabilities("codex", frozenset()),
            )
            events = translate_pipeline_receipts(receipts)
            observation = shadow_artifact(
                "authoritative_observation", spec.to_dict(),
                [event.to_dict() for event in events],
            )
            observation["run_state"] = {
                "schema_version": 1, "revision": len(events), "run_id": spec.run_id,
                "mode": "shadow", "status": "running", "created_at": events[0].occurred_at,
                "updated_at": events[-1].occurred_at, "nodes": {},
                "evidence": [event.payload["authoritative_receipt"] for event in events],
                "cleanup_reconciled": False,
            }
            (root / "pipeline-shadow-observation.json").write_text(json.dumps(observation))
            output = root / "parity.json"
            compared = self.run_cli(
                "compare", "--state-dir", root,
                "--authoritative-receipts", FIXTURES / "pipeline-codex.json",
                "--output", output,
            )
            self.assertEqual(compared.returncode, 5, compared.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["reason"], "missing_authoritative_evidence")
            self.assertIn("missing_independent_prediction", report["differences"])

    def test_metrics_and_invalid_input_exit_codes_are_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "metrics.json"
            good = self.run_cli("metrics", "--events", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(output.read_text())["tokens"], 1200)
            bad_input = Path(directory) / "bad.json"
            bad_input.write_text("not-json")
            bad = self.run_cli("metrics", "--events", bad_input, "--output", output)
            self.assertEqual(bad.returncode, 2)

    def test_compare_returns_five_for_parity_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_spec = {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"full_cli"}
            observation = shadow_artifact("authoritative_observation", run_spec)
            observation["run_state"] = {
                "schema_version": 1, "revision": 0, "run_id": "pipeline-1", "mode": "shadow", "status": "planned",
                "created_at": "2026-07-14T00:00:00Z", "updated_at": "2026-07-14T00:00:00Z", "nodes": {}, "evidence": [], "cleanup_reconciled": False,
            }
            (root / "pipeline-shadow-observation.json").write_text(json.dumps(observation))
            (root / "pipeline-shadow-prediction.json").write_text(json.dumps(
                shadow_artifact("independent_prediction", run_spec),
            ))
            output = root / "parity.json"
            result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(result.returncode, 5)
            self.assertFalse(json.loads(output.read_text())["safe_to_promote"])

    def test_compare_uses_predicted_receipt_semantics_not_evidence_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
            predicted = json.loads(json.dumps(receipts)); predicted[2]["status"] = "failed"
            from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
            events = translate_pipeline_receipts(predicted)
            run_spec = {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"full_cli"}
            (root / "pipeline-shadow-observation.json").write_text(json.dumps(
                shadow_artifact("authoritative_observation", run_spec, []),
            ))
            (root / "pipeline-shadow-prediction.json").write_text(json.dumps(
                shadow_artifact(
                    "independent_prediction", run_spec,
                    [event.to_dict() for event in events],
                ),
            ))
            output = root / "parity.json"
            result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertEqual(result.returncode, 5)
            self.assertFalse(json.loads(output.read_text())["semantic_match"])

    def test_compare_fails_closed_without_events_and_on_runspec_context_drift(self):
        from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
            events = translate_pipeline_receipts(receipts)
            refs = [event.payload["authoritative_receipt"] for event in events]
            base = {
                "schema_version":1,"artifact_role":"authoritative_observation",
                "observation_type": "pipeline", "observation_only":True,
                "run_spec": {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"full_cli"},
                "run_state": {"schema_version":1,"revision":len(events),"run_id":"pipeline-1","mode":"shadow","status":"running","created_at":events[0].occurred_at,"updated_at":events[-1].occurred_at,"nodes":{},"evidence":refs,"cleanup_reconciled":False},
            }
            output = root / "parity.json"
            for mutation in ("missing_events", "empty_events", "runspec_mode"):
                artifact = json.loads(json.dumps(base))
                prediction = shadow_artifact(
                    "independent_prediction", artifact["run_spec"],
                )
                if mutation == "empty_events":
                    prediction = shadow_artifact(
                        "independent_prediction", artifact["run_spec"], [],
                    )
                if mutation == "runspec_mode":
                    artifact["run_spec"]["execution_mode"] = "codex_native"
                    prediction = shadow_artifact(
                        "independent_prediction", artifact["run_spec"],
                        [event.to_dict() for event in events],
                    )
                (root / "pipeline-shadow-observation.json").write_text(json.dumps(artifact))
                (root / "pipeline-shadow-prediction.json").write_text(json.dumps(prediction))
                result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "pipeline-claude.json", "--output", output)
                with self.subTest(mutation=mutation):
                    self.assertEqual(result.returncode, 5, result.stderr)
                    report = json.loads(output.read_text())
                    self.assertFalse(report["safe_to_promote"])
                    if mutation in {"missing_events", "empty_events"}:
                        self.assertEqual(report["reason"], "missing_authoritative_evidence")
                        if mutation == "missing_events":
                            self.assertIn("semantic_receipts_required", report["differences"])
                    else:
                        self.assertEqual(report["reason"], "missing_authoritative_evidence")
                        self.assertIn("prediction_lifecycle_authority_invalid", report["differences"])

    def test_compare_selects_translator_from_observation_type(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pipeline-shadow-observation.json").write_text(json.dumps({
                "artifact_role":"authoritative_observation",
                "observation_type":"pipeline", "run_spec":{}, "events":[],
            }))
            result = self.run_cli("compare", "--state-dir", root, "--authoritative-receipts", FIXTURES / "dm-review.json", "--output", root / "out.json")
            self.assertEqual(result.returncode, 2)

    def test_json_output_rejects_symlink_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); victim = root / "victim"; victim.write_text("safe")
            output = root / "metrics.json"; output.symlink_to(victim)
            result = self.run_cli("metrics", "--events", FIXTURES / "pipeline-claude.json", "--output", output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(victim.read_text(), "safe")

    def test_verification_contract_bind_is_content_addressed_audited_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            marker = root / "executed"
            contract = root / "contract.json"
            contract.write_text(json.dumps(verification_contract(marker=marker)))

            first = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = json.loads(first.stdout)
            self.assertEqual(set(receipt), {
                "stage", "contract_id", "schema_version", "revision",
                "contract_digest", "contract_ref", "previous_contract_digest",
                "reason_code",
                "verification_profile_id", "verification_profile_digest",
                "verification_profile_ref",
            })
            self.assertEqual(receipt["stage"], "verification_contract_bound")
            self.assertEqual(receipt["revision"], 1)
            self.assertIsNone(receipt["previous_contract_digest"])
            self.assertRegex(receipt["contract_digest"], r"^sha256:[0-9a-f]{64}$")
            artifact = run_dir / receipt["contract_ref"]
            self.assertEqual(
                artifact.name,
                "sha256-" + receipt["contract_digest"].removeprefix("sha256:") + ".json",
            )
            self.assertTrue(artifact.is_file())
            self.assertFalse(marker.exists(), "binding must never execute contract argv")
            events_before = (run_dir / "events.jsonl").read_bytes()

            second = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout), receipt)
            self.assertEqual((run_dir / "events.jsonl").read_bytes(), events_before)
            event = json.loads(events_before.splitlines()[-1])
            self.assertEqual(event["kind"], "evidence.recorded")
            self.assertEqual(event["payload"]["stage"], "verification_contract_bound")

    def test_verification_contract_binding_seals_exact_authoritative_profile_cases(self):
        from workflow_kernel.behavioral_contract import obligations, verification_profile_digest
        from workflow_kernel.verification import PersonaCase, VerificationProfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "profile-run")
            run_dir = root / ".workflow-kernel" / "runs" / "profile-run"
            case = PersonaCase(
                "editor", "edit", "member", "/edit", "chromium", "1280x720", True,
            )
            profile_value = VerificationProfile(
                1, "project_declaration", (case,), (),
                configured_engines=("chromium",),
            ).to_dict()
            profile = root / "verification-profile.json"
            profile.write_text(json.dumps(profile_value))
            value = verification_contract()
            value["persona_case_ids"] = [case.case_id]
            value["browser_case_ids"] = [case.case_id]
            value["verification_profile_id"] = profile_value["profile_id"]
            value["verification_profile_digest"] = verification_profile_digest(profile_value)
            value["revision_justification"]["added_obligation_ids"] = sorted(
                obligations(value)
            )
            contract = root / "contract.json"
            contract.write_text(json.dumps(value))
            bound = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract, "--verification-profile", profile,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)
            receipt = json.loads(bound.stdout)
            self.assertEqual(receipt["verification_profile_id"], profile_value["profile_id"])
            self.assertTrue((run_dir / receipt["verification_profile_ref"]).is_file())

            invented = json.loads(json.dumps(value))
            invented["contract_id"] = "different-contract"
            invented_path = root / "invented.json"
            invented_path.write_text(json.dumps(invented))
            rejected = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", invented_path, "--verification-profile", profile,
            )
            self.assertEqual(rejected.returncode, 2)

    def test_forged_initial_binding_cannot_be_materialized_by_idempotent_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            candidate = verification_contract()
            contract = root / "contract.json"
            contract.write_text(json.dumps(candidate))
            _digest, reference = self.append_contract_binding(
                run_dir, candidate, "verification_contract_bound",
            )

            result = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse((run_dir / reference).exists())

    def test_verification_contract_malformed_input_is_redacted_and_has_no_partial_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            contract = root / "bad-contract.json"
            contract.write_text('{"secret-value-that-must-not-leak":')
            result = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract,
            )
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("secret-value-that-must-not-leak", result.stderr)
            self.assertFalse((run_dir / "verification-contracts").exists())
            self.assertEqual(len((run_dir / "events.jsonl").read_text().splitlines()), 1)

    def test_verification_contract_secret_argv_is_rejected_before_artifact_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            value = verification_contract()
            for index, argv in enumerate((
                ["tool", "--api-key", "sk-live-credential"],
                ["tool", "--api-key=opaque-credential-value"],
                ["tool", "gho_abcdefghijk"],
                ["tool", "AKIAIOSFODNN7EXAMPLE"],
                ["tool", "sk_live_1234567890abcdef"],
                ["tool", "--client-secret", "opaque-credential-value"],
                ["tool", "--apikey", "opaque-credential-value"],
                ["tool", "--clientauth=opaque-credential-value"],
                ["tool", "--githubtoken", "opaque-credential-value"],
                ["tool", "--oauth-token", "opaque-credential-value"],
                ["tool", "--session-token=opaque-credential-value"],
                ["tool.exe", "/password", "opaque-credential-value"],
                ["tool.exe", "/api-key", "opaque-credential-value"],
                ["tool.exe", "/client-secret=opaque-credential-value"],
                ["tool", "--credentials", "opaque-credential-value"],
                ["tool", "--creds=opaque-credential-value"],
                ["tool", "--passphrase", "opaque-credential-value"],
                ["tool", "--bearer", "opaque-credential-value"],
                ["curl", "--oauth2-bearer", "opaque-credential-value"],
                ["tool", "ASIAIOSFODNN7EXAMPLE"],
                ["bash.exe", "-c", "echo should-not-run"],
                ["bash", "--rcfile", "/dev/null", "-c", "echo should-not-run"],
                ["pwsh", "-ep", "Bypass", "-c", "echo should-not-run"],
                ["pwsh", "-o", "text", "-c", "echo should-not-run"],
                ["pwsh", "-ec", "ZgBvAG8A"],
                ["pwsh", "-cwa", "echo should-not-run"],
                ["pwsh", "-ConfigurationFile", "config.ps1", "-c", "echo should-not-run"],
                ["env.exe", "-S", "bash -c echo should-not-run"],
                ["env.exe", "--split-string=bash -c echo should-not-run"],
                ["env", "-uNAME", "bash", "-c", "echo should-not-run"],
                ["env", "-C/tmp", "bash", "-c", "echo should-not-run"],
                ["env", "-iS", "bash -c echo should-not-run"],
                ["env", "-iu", "NAME", "bash", "-c", "echo should-not-run"],
                ["env", "-", "bash", "-c", "echo should-not-run"],
                ["mksh", "-c", "echo should-not-run"],
                ["yash", "-c", "echo should-not-run"],
                ["fish", "--init-command=echo should-not-run"],
                ["fish", "--init-command", "echo should-not-run"],
                ["fish", "-C", "echo should-not-run"],
                ["cmd.exe", "/c", "echo should-not-run"],
                ["cmd.exe", "/d", "/q", "/s", "/c", "echo should-not-run"],
            )):
                candidate = json.loads(json.dumps(value))
                candidate["checks"][0]["argv"] = argv
                contract = root / f"secret-contract-{index}.json"
                contract.write_text(json.dumps(candidate))
                result = self.run_cli(
                    "bind-verification-contract", "--state-dir", run_dir,
                    "--contract", contract,
                )
                self.assertEqual(result.returncode, 2)
                self.assertFalse((run_dir / "verification-contracts").exists())
                self.assertEqual(
                    len((run_dir / "events.jsonl").read_text().splitlines()), 1,
                )

    def test_verification_contract_rejects_symlink_input_and_artifact_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            contract = root / "contract.json"
            contract.write_text(json.dumps(verification_contract()))
            linked_input = root / "linked-contract.json"
            linked_input.symlink_to(contract)
            rejected_input = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", linked_input,
            )
            self.assertEqual(rejected_input.returncode, 2)

            victim = root / "victim"
            victim.mkdir()
            (run_dir / "verification-contracts").symlink_to(
                victim, target_is_directory=True,
            )
            rejected_output = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", contract,
            )
            self.assertEqual(rejected_output.returncode, 2)
            self.assertEqual(list(victim.iterdir()), [])
            self.assertEqual(len((run_dir / "events.jsonl").read_text().splitlines()), 1)

    def test_cleanup_command_surface_and_plan_create(self):
        help_result = self.run_cli("--help")
        for command in ("bind-prediction", "bind-verification-contract", "plan-create", "plan-compose", "record-create", "plan-cleanup", "next-cleanup-step", "execute-cleanup-step", "record-cleanup", "plan-reconcile"):
            self.assertIn(command, help_result.stdout)
        self.assertNotIn("revise-verification-contract", help_result.stdout)
        self.assertNotIn(
            "authorize-verification-contract-revision", help_result.stdout,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); argv = root / "argv.json"; output = root / "plan.json"
            self.init_lifecycle(root, "run-1")
            argv.write_text(json.dumps(["docker", "run", "--name", "review-box", "image:latest"]))
            result = self.run_cli("plan-create", "--state-dir", root / ".workflow-kernel" / "runs" / "run-1", "--run-id", "run-1", "--node-id", "chunk-1", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", argv, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text())
            self.assertTrue(plan["managed"])
            self.assertIn("com.designmachines.depot.run-id", plan["labels"])

    def test_runtime_resolver_ignores_cwd_and_rejects_symlink_escape(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); depot = root / "depot"; pipeline = depot / "plugins" / "pipeline"
            runtime = depot / "plugins" / "workflow-kernel"; refs = runtime / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
            refs.mkdir(parents=True); pipeline.mkdir(parents=True)
            (runtime / ".claude-plugin").mkdir(); (runtime / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name":"workflow-kernel","version":"0.5.0"}))
            (refs / "__main__.py").write_text("")
            forged = root / "target" / "workflow_kernel"; forged.mkdir(parents=True); (forged / "__main__.py").write_text("")
            self.assertEqual(resolve_workflow_kernel_runtime(pipeline, home=root / "home"), refs.parent.resolve())
            escaped = depot / "plugins" / "workflow-kernel-escape"; escaped.symlink_to(root / "target", target_is_directory=True)
            self.assertNotEqual(resolve_workflow_kernel_runtime(pipeline, home=root / "home"), escaped)

    def test_runtime_resolver_semantically_sorts_only_compatible_cache_versions(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); pipeline = root / "depot" / "plugins" / "pipeline"
            pipeline.mkdir(parents=True)
            cache = root / "home" / ".claude" / "plugins" / "cache" / "depot" / "workflow-kernel"
            for version in ("0.5.9", "0.5.10", "1.0.0"):
                runtime = cache / version
                refs = runtime / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
                refs.mkdir(parents=True)
                (runtime / ".claude-plugin").mkdir()
                (runtime / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name":"workflow-kernel","version":version}))
                (refs / "__main__.py").write_text("")
            resolved = resolve_workflow_kernel_runtime(pipeline, home=root / "home")
            self.assertEqual(resolved, (cache / "0.5.10" / "skills" / "workflow-kernel" / "references").resolve())

    def test_plugin_bundle_resolver_is_semver_coherent_and_active_host_only_breaks_ties(self):
        from workflow_kernel.runtime_resolution import resolve_plugin_bundle

        def install(home, host, version, *, manifest_version=None, assets=("skills/sample/SKILL.md",)):
            root = home / f".{host}" / "plugins" / "cache" / "depot" / "sample" / version
            marker = ".claude-plugin" if host == "claude" else ".codex-plugin"
            (root / marker).mkdir(parents=True)
            (root / marker / "plugin.json").write_text(json.dumps({
                "name": "sample", "version": manifest_version or version,
            }))
            for asset in assets:
                path = root / asset
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n")
            return root

        with self.subTest("newer Codex beats stale active Claude"):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                install(home, "claude", "1.9.0")
                highest = install(home, "codex", "1.10.0")
                malformed = install(
                    home, "claude", "1.11.0", manifest_version="1.10.0",
                )
                selected = resolve_plugin_bundle(
                    "sample", ["skills/sample/SKILL.md"], home=home,
                    minimum_version="1.0.0", active_host="claude",
                )
                self.assertEqual(selected.root, highest.resolve())
                self.assertEqual(selected.reason, "highest_compatible_semver")
                self.assertNotEqual(selected.root, malformed.resolve())

        with self.subTest("newer Claude beats stale active Codex"):
            with tempfile.TemporaryDirectory() as directory:
                home = Path(directory)
                install(home, "codex", "1.9.0")
                highest = install(home, "claude", "1.10.0")
                selected = resolve_plugin_bundle(
                    "sample", ["skills/sample/SKILL.md"], home=home,
                    minimum_version="1.0.0", active_host="codex",
                )
                self.assertEqual(selected.root, highest.resolve())
                self.assertEqual(selected.reason, "highest_compatible_semver")

        for active_host in ("claude", "codex"):
            with self.subTest(
                "equal version prefers active host", active_host=active_host,
            ):
                with tempfile.TemporaryDirectory() as directory:
                    home = Path(directory)
                    expected = install(home, active_host, "1.10.0")
                    other_host = "codex" if active_host == "claude" else "claude"
                    install(home, other_host, "1.10.0")
                    selected = resolve_plugin_bundle(
                        "sample", ["skills/sample/SKILL.md"], home=home,
                        minimum_version="1.0.0", active_host=active_host,
                    )
                    self.assertEqual(selected.root, expected.resolve())
                    self.assertEqual(
                        selected.reason, "active_host_equal_version_tiebreak",
                    )
                    durable = selected.to_dict()
                    self.assertEqual(durable["cache_class"], active_host)
                    self.assertTrue(
                        durable["selected_root"].startswith(f"~/.{active_host}/"),
                    )
                    self.assertNotIn(str(home), json.dumps(durable))

    def test_plugin_bundle_resolver_never_combines_assets_across_roots(self):
        from workflow_kernel.runtime_resolution import resolve_plugin_bundle

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for host, asset in (
                ("claude", "skills/sample/SKILL.md"),
                ("codex", "references/runtime.py"),
            ):
                root = (
                    home / f".{host}" / "plugins" / "cache" / "depot"
                    / "sample" / "2.0.0"
                )
                marker = ".claude-plugin" if host == "claude" else ".codex-plugin"
                (root / marker).mkdir(parents=True)
                (root / marker / "plugin.json").write_text(json.dumps({
                    "name": "sample", "version": "2.0.0",
                }))
                path = root / asset
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n")
            with self.assertRaises(FileNotFoundError):
                resolve_plugin_bundle(
                    "sample",
                    ["skills/sample/SKILL.md", "references/runtime.py"],
                    home=home,
                )

    def test_plugin_bundle_resolver_rejects_unreadable_assets(self):
        from workflow_kernel.runtime_resolution import resolve_plugin_bundle

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            root = (
                home / ".codex" / "plugins" / "cache" / "depot"
                / "sample" / "1.6.0"
            )
            (root / ".codex-plugin").mkdir(parents=True)
            (root / ".codex-plugin" / "plugin.json").write_text(json.dumps({
                "name": "sample", "version": "1.6.0",
            }))
            asset = root / "references" / "policy.json"
            asset.parent.mkdir(parents=True)
            asset.write_text("{}\n")
            asset.chmod(0)
            with self.assertRaises(FileNotFoundError):
                resolve_plugin_bundle(
                    "sample", ["references/policy.json"], home=home,
                    minimum_version="1.6.0",
                )

    def test_plugin_bundle_resolver_skips_non_executable_higher_bundle(self):
        from workflow_kernel.runtime_resolution import resolve_plugin_bundle

        def install(home, version, *, executable):
            root = (
                home / ".codex" / "plugins" / "cache" / "depot"
                / "sample" / version
            )
            (root / ".codex-plugin").mkdir(parents=True)
            (root / ".codex-plugin" / "plugin.json").write_text(json.dumps({
                "name": "sample", "version": version,
            }))
            policy = root / "references" / "policy.json"
            wrapper = root / "references" / "wrapper.sh"
            policy.parent.mkdir(parents=True)
            policy.write_text("{}\n")
            wrapper.write_text("#!/bin/sh\nexit 0\n")
            wrapper.chmod(0o755 if executable else 0o644)
            return root

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            lower = install(home, "1.6.0", executable=True)
            install(home, "1.7.0", executable=False)
            selected = resolve_plugin_bundle(
                "sample", ["references/policy.json"], home=home,
                minimum_version="1.6.0",
                required_executables=["references/wrapper.sh"],
            )
            self.assertEqual(selected.root, lower.resolve())
            self.assertEqual(selected.version, "1.6.0")

    def test_inspection_and_bundle_cli_surfaces_coexist_and_dispatch(self):
        from workflow_kernel import cli
        from workflow_kernel.runtime_resolution import PluginBundle

        choices = next(
            action.choices for action in cli.parser()._actions
            if getattr(action, "choices", None)
        )
        for command in (
            "inspection-validate", "inspection-classify", "inspection-trend",
            "inspection-finalize", "inspection-render", "inspection-run",
            "resolve-plugin-bundle",
            "init", "plan-create",
        ):
            self.assertIn(command, choices)
        self.assertIn(
            "--required-executable",
            choices["resolve-plugin-bundle"].format_help(),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "sample" / "1.0.0"
            emitted = []
            with mock.patch(
                "workflow_kernel.cli.resolve_plugin_bundle",
                return_value=PluginBundle(
                    root, "codex", "1.0.0", "highest_compatible_semver",
                ),
            ) as resolver, mock.patch(
                "workflow_kernel.cli._emit", side_effect=emitted.append,
            ):
                result = cli.command_resolve_plugin_bundle(SimpleNamespace(
                    plugin="sample",
                    required_asset=["skills/sample/SKILL.md"],
                    required_executable=["references/wrapper.sh"],
                    minimum_version=None, active_host=None,
                ))
            self.assertEqual(result, 0)
            self.assertEqual(emitted[0]["version"], "1.0.0")
            self.assertEqual(emitted[0]["cache_class"], "codex")
            resolver.assert_called_once_with(
                "sample", ["skills/sample/SKILL.md"],
                active_host=None, minimum_version=None,
                required_executables=["references/wrapper.sh"],
            )
        parsed = cli.parser().parse_args([
            "resolve-plugin-bundle", "--plugin", "sample",
            "--required-executable", "references/wrapper.sh",
        ])
        self.assertEqual(parsed.required_asset, [])
        self.assertEqual(
            parsed.required_executable, ["references/wrapper.sh"],
        )

    def test_security_artifact_codecs_require_exact_versioned_shapes(self):
        from workflow_kernel.cli import _command_result, _creation_plan
        valid_result = {"schema_version":1,"argv":["docker","ps"],"exit_code":0,"stdout":"","stderr":""}
        self.assertEqual(_command_result(valid_result).exit_code, 0)
        for mutation in (
            {**valid_result, "extra": True},
            {key:value for key,value in valid_result.items() if key != "schema_version"},
            {**valid_result, "schema_version":2},
        ):
            with self.assertRaises(ValueError):
                _command_result(mutation)
        with self.assertRaises(ValueError):
            _creation_plan({"argv":["docker","run","alpine"],"labels":{},"lifecycle":"chunk","registration_intents":[]})

    def test_node_status_proof_comes_only_from_verified_state_dir_and_is_omitted_when_unneeded(self):
        from workflow_kernel.cli import _incomplete_node_proof
        from workflow_kernel.resources import ResourceKind, ResourceRecord
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {
                "schema_version":1,"revision":1,"run_id":"run-1","mode":"shadow","status":"running",
                "created_at":now.isoformat(),"updated_at":now.isoformat(),
                "nodes":{"dependent":{"node_id":"dependent","status":"running","dependencies":[],"evidence":[]}},
                "evidence":[],"cleanup_reconciled":False,
            }
            (root / "run-state.json").write_text(json.dumps(state))
            labels = {"safe":"value"}
            ordinary = ResourceRecord("ctr-1",ResourceKind.CONTAINER,"run-1","node-1","chunk","stop-remove",now,(),labels)
            dependent = ResourceRecord("ctr-2",ResourceKind.CONTAINER,"run-1","node-1","chunk","stop-remove",now,("dependent",),labels)
            self.assertIsNone(_incomplete_node_proof(root, "run-1", (ordinary,)))
            witness = root / "node-statuses.json"
            witness.write_text(json.dumps({
                "schema_version":1,"run_id":"run-1","revision":1,
                "updated_at":now.isoformat(),
                "node_statuses":{"dependent":"running"},
            }))
            self.assertIsNone(_incomplete_node_proof(
                root, "run-1", (ordinary,), witness,
            ))
            invalid = json.loads(witness.read_text())
            invalid["revision"] = 0
            witness.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                _incomplete_node_proof(root, "run-1", (ordinary,), witness)
            proof = _incomplete_node_proof(root, "run-1", (dependent,))
            self.assertEqual(proof.incomplete_node_ids, ("dependent",))

    def test_stale_reconcile_ttl_is_effective_and_missing_lease_proof_blocks(self):
        from workflow_kernel.adapters.docker import (
            CREATED_LABEL, LIFECYCLE_LABEL, MANAGED_LABEL, NODE_LABEL,
            POLICY_LABEL, RUN_LABEL, DockerAdapter, DockerInventory,
            DockerResource, LeaseProof,
        )
        from workflow_kernel.cli import _stale_cleanup_plan
        from workflow_kernel.resources import CommandResult, ResourceKind

        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        created = now - timedelta(hours=48)
        labels = {
            MANAGED_LABEL: "true", RUN_LABEL: "old-run", NODE_LABEL: "chunk-1",
            CREATED_LABEL: created.isoformat().replace("+00:00", "Z"),
            LIFECYCLE_LABEL: "run", POLICY_LABEL: "remove-when-stopped",
            "com.designmachines.depot.repository-scope-id": SCOPE_ID,
        }
        inventory = DockerInventory((DockerResource(
            "container-1", ResourceKind.CONTAINER, labels, created,
        ),), source="managed_orphan_sweep")

        class Runner:
            def run(self, argv):
                return CommandResult(tuple(argv), 0, "", "")

        class InactiveLease:
            def read(self, run_id):
                return LeaseProof(run_id, False, True, now, SCOPE_ID)

        proved = DockerAdapter(
            Runner(), now=lambda: now, lease_reader=InactiveLease(),
            repository_scope_id=SCOPE_ID,
        )
        self.assertTrue(_stale_cleanup_plan(proved, inventory, 24).actions)
        retained = _stale_cleanup_plan(proved, inventory, 72)
        self.assertEqual(retained.dispositions[0].reason, "ttl_not_expired")
        blocked = _stale_cleanup_plan(DockerAdapter(
            Runner(), now=lambda: now, repository_scope_id=SCOPE_ID,
        ), inventory, 24)
        self.assertFalse(blocked.actions)
        self.assertEqual(blocked.dispositions[0].reason, "lease_reader_unavailable")

    def test_reconcile_uses_separate_exact_plan_artifacts_and_trusted_lease_state(self):
        from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory
        from workflow_kernel.cli import (
            StateDirectoryLeaseReader, _cleanup_artifact,
            _cleanup_artifact_document, _reconcile_output_paths,
        )
        from workflow_kernel.resources import ResourceRegistry
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); registry = ResourceRegistry(root / "resources.jsonl")
            plan = DockerAdapter(
                type("Runner", (), {"run": lambda _self, argv: None})(),
                repository_scope_id=SCOPE_ID,
            ).plan_reconcile_run(
                registry, DockerInventory(()), "run-1", terminal=True,
            )
            document = _cleanup_artifact_document(plan, DockerInventory(()))
            self.assertEqual(_cleanup_artifact(document)[0], plan)
            with self.assertRaises(ValueError):
                _cleanup_artifact({**document, "unexpected": True})
            descriptor, current, stale = _reconcile_output_paths(root / "reconcile.json")
            self.assertEqual(descriptor.name, "reconcile.json")
            self.assertEqual(current.name, "reconcile.current-run.json")
            self.assertEqual(stale.name, "reconcile.stale-sweep.json")

            repo = root / "repo"
            self.init_lifecycle(repo, "old-run")
            lease_root = repo / ".workflow-kernel"
            run_dir = lease_root / "runs" / "old-run"
            for sequence, kind, payload in (
                (1, "run.started", {}),
                (2, "run.succeeded", {"evidence": ["receipt.json"]}),
            ):
                result = self.run_cli("append", run_dir, "--event", json.dumps({
                    "schema_version": 1, "sequence": sequence,
                    "run_id": "old-run", "node_id": None, "kind": kind,
                    "occurred_at": now.isoformat(), "payload": payload,
                }))
                self.assertEqual(result.returncode, 0, result.stderr)
            proof = StateDirectoryLeaseReader(lease_root, SCOPE_ID, now=lambda: now).read("old-run")
            self.assertFalse(proof.active)
            self.assertTrue(proof.readable)
            self.assertIsNone(StateDirectoryLeaseReader(lease_root, SCOPE_ID, now=lambda: now).read("missing"))

    def test_stale_state_reader_treats_live_os_lease_as_active_and_guard_is_nonblocking(self):
        from workflow_kernel.cli import StateDirectoryLeaseReader
        from workflow_kernel.schema import LeaseConflictError
        from workflow_kernel.state import RunLease
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            self.init_lifecycle(repo, "old-run")
            root = repo / ".workflow-kernel"; run_dir = root / "runs" / "old-run"
            state_path = run_dir / "run-state.json"
            reader = StateDirectoryLeaseReader(root, SCOPE_ID, now=lambda: now)
            with RunLease(state_path):
                self.assertTrue(reader.read("old-run").active)
                with self.assertRaises(LeaseConflictError):
                    with reader.inactive_guard("old-run"):
                        self.fail("live run lease must not yield an inactive guard")
            with self.assertRaises(ValueError):
                with reader.inactive_guard("old-run"):
                    self.fail("planned run must remain active")

    def test_canonical_run_init_is_reachable_from_shared_lease_root(self):
        from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory
        from workflow_kernel.cli import command_plan_reconcile
        from workflow_kernel.cli import StateDirectoryLeaseReader
        now = "2026-07-15T00:00:00Z"
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            root = self.init_repository_scope(repo)
            run_dir = root / "runs" / "old-run"
            initialized = self.run_cli(
                "init", run_dir, "--run-id", "old-run",
                "--occurred-at", now,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            for sequence, kind, occurred_at, payload in (
                (1,"run.started","2026-07-15T00:00:01Z",{}),
                (2,"run.succeeded","2026-07-15T00:00:02Z",{"evidence":["receipt.json"]}),
            ):
                event = json.dumps({
                    "schema_version":1,"sequence":sequence,"run_id":"old-run",
                    "node_id":None,"kind":kind,"occurred_at":occurred_at,
                    "payload":payload,
                })
                appended = self.run_cli("append", run_dir, "--event", event)
                self.assertEqual(appended.returncode, 0, appended.stderr)
            proof = StateDirectoryLeaseReader(root, SCOPE_ID).read("old-run")
            self.assertFalse(proof.active)
            state_dir = repo / "plans" / "feature"
            state_dir.mkdir(parents=True)
            output = state_dir / "reconcile.json"
            args = SimpleNamespace(
                state_dir=state_dir, run_id="current-run",
                ttl_hours=24, node_statuses=None, output=output,
            )
            with (
                mock.patch.object(DockerAdapter, "inventory_registered", return_value=DockerInventory(())),
                mock.patch.object(DockerAdapter, "inventory", return_value=DockerInventory(())),
            ):
                self.assertEqual(command_plan_reconcile(args), 0)
            stale = output.with_name("reconcile.stale-sweep.json")
            self.assertTrue(stale.is_file())

    def test_stale_cli_action_executes_under_old_run_guard_without_current_run_node_witness(self):
        from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory, DockerResource
        from workflow_kernel.cli import (
            StateDirectoryLeaseReader, _cleanup_artifact_document,
            _inventory_dict, command_execute_cleanup_step,
        )
        from workflow_kernel.resources import CommandResult, ResourceKind, ResourceRegistry
        from workflow_kernel.schema import LeaseConflictError
        from workflow_kernel.state import RunLease

        now = datetime.now(timezone.utc).replace(microsecond=0)
        created = now - timedelta(hours=48)
        labels = {
            "com.designmachines.depot.managed":"true",
            "com.designmachines.depot.repository-scope-id":SCOPE_ID,
            "com.designmachines.depot.run-id":"old-run",
            "com.designmachines.depot.node-id":"old-node",
            "com.designmachines.depot.created-at":created.isoformat().replace("+00:00","Z"),
            "com.designmachines.depot.lifecycle":"run",
            "com.designmachines.depot.cleanup-policy":"remove-when-stopped",
        }
        scope_filter = "label=com.designmachines.depot.repository-scope-id=" + SCOPE_ID
        container_list = ("docker","ps","-a","--filter","label=com.designmachines.depot.managed=true","--filter",scope_filter,"--format","{{.ID}}")
        network_list = ("docker","network","ls","--filter","label=com.designmachines.depot.managed=true","--filter",scope_filter,"--format","{{.ID}}")
        volume_list = ("docker","volume","ls","--filter","label=com.designmachines.depot.managed=true","--filter",scope_filter,"--format","{{.Name}}")
        inspect = ("docker","container","inspect","ctr-old")
        remove = ("docker","rm","ctr-old")
        inspected = json.dumps([{
            "Name":"/ctr-old","Config":{"Labels":labels},
            "Created":created.isoformat(),"State":{"Running":False},
        }])

        class Runner:
            calls = []
            results = {
                container_list:CommandResult(container_list,0,"ctr-old\n",""),
                network_list:CommandResult(network_list,0,"",""),
                volume_list:CommandResult(volume_list,0,"",""),
                inspect:CommandResult(inspect,0,inspected,""),
                remove:CommandResult(remove,0,"",""),
            }
            def run(self, argv):
                argv = tuple(argv); self.calls.append(argv)
                return self.results[argv]

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            self.init_lifecycle(repo, "old-run")
            root = repo / ".workflow-kernel"; run_dir = root / "runs" / "old-run"
            for sequence, kind, payload in (
                (1, "run.started", {}),
                (2, "run.succeeded", {"evidence": ["receipt.json"]}),
            ):
                result = self.run_cli("append", run_dir, "--event", json.dumps({
                    "schema_version": 1, "sequence": sequence,
                    "run_id": "old-run", "node_id": None, "kind": kind,
                    "occurred_at": now.isoformat(), "payload": payload,
                }))
                self.assertEqual(result.returncode, 0, result.stderr)
            runner = Runner()
            adapter = DockerAdapter(
                runner, now=lambda: now,
                lease_reader=StateDirectoryLeaseReader(root, SCOPE_ID, now=lambda: now),
                repository_scope_id=SCOPE_ID,
            )
            inventory = adapter.inventory()
            plan = adapter.plan_stale_sweep(inventory, timedelta(hours=24))
            self.assertEqual(len(plan.actions), 1)
            plan_path = root / "stale.json"
            inventory_path = root / "inventory.json"
            outcomes = root / "outcomes.json"
            output = root / "authority.json"
            plan_path.write_text(json.dumps(_cleanup_artifact_document(plan, inventory)))
            inventory_path.write_text(json.dumps(_inventory_dict(inventory)))
            outcomes.write_text("[]")
            args = SimpleNamespace(
                plan=plan_path, step_index=0, state_dir=root,
                outcomes=outcomes, inventory=inventory_path,
                node_statuses=root / "must-not-be-read.json", output=output,
            )
            Runner.calls.clear()
            with RunLease(run_dir / "run-state.json"):
                with mock.patch("workflow_kernel.cli._SubprocessRunner", Runner):
                    with self.assertRaises(LeaseConflictError):
                        command_execute_cleanup_step(args)
                self.assertNotIn(remove, Runner.calls)
            Runner.calls.clear()
            with mock.patch("workflow_kernel.cli._SubprocessRunner", Runner):
                self.assertEqual(command_execute_cleanup_step(args), 0)
            self.assertIn(remove, Runner.calls)
            self.assertTrue(output.is_file())

    def test_forged_cli_authority_prefix_is_rejected_before_runner_use(self):
        from workflow_kernel.adapters.docker import DockerAdapter, DockerInventory, DockerResource
        from workflow_kernel.cli import (
            _authority_dict, _cleanup_artifact_document,
            _inventory_dict, command_execute_cleanup_step,
        )
        from workflow_kernel.resources import (
            CommandResult, ResourceKind, ResourceRecord, ResourceRegistry,
        )
        from workflow_kernel.schema import InvalidSchemaError

        now = datetime.now(timezone.utc).replace(microsecond=0)
        labels = {
            "com.designmachines.depot.managed":"true",
            "com.designmachines.depot.repository-scope-id":SCOPE_ID,
            "com.designmachines.depot.run-id":"run-1",
            "com.designmachines.depot.node-id":"node-1",
            "com.designmachines.depot.created-at":now.isoformat().replace("+00:00","Z"),
            "com.designmachines.depot.lifecycle":"chunk",
            "com.designmachines.depot.cleanup-policy":"stop-remove",
        }

        class PlanningRunner:
            def run(self, argv):
                return CommandResult(tuple(argv), 0, "", "")

        class BombRunner:
            calls = []
            def run(self, argv):
                self.calls.append(tuple(argv))
                raise AssertionError("runner must not be called")

        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            self.init_lifecycle(repo, "run-1")
            root = repo / ".workflow-kernel" / "runs" / "run-1"
            registry = ResourceRegistry(root / "resources.jsonl")
            record = ResourceRecord(
                "ctr-1", ResourceKind.CONTAINER, "run-1", "node-1",
                "chunk", "stop-remove", now, labels=labels,
            )
            registry.register(record)
            resource = DockerResource(
                "ctr-1", ResourceKind.CONTAINER, labels, now, running=True,
            )
            inventory = DockerInventory((resource,))
            adapter = DockerAdapter(
                PlanningRunner(), repository_scope_id=SCOPE_ID,
            )
            plan = adapter.plan_chunk_cleanup(
                registry, inventory, "run-1", "node-1",
            )
            first = registry.execute_guarded_action(
                adapter, plan, 0, resource, PlanningRunner().run,
            )
            forged = _authority_dict(first)
            forged["authority_id"] = "sha256:" + "f" * 64
            plan_path = root / "plan.json"
            outcomes = root / "outcomes.json"
            witness = root / "inventory.json"
            output = root / "authority.json"
            plan_path.write_text(json.dumps(_cleanup_artifact_document(plan, inventory)))
            outcomes.write_text(json.dumps([forged]))
            witness.write_text(json.dumps(_inventory_dict(inventory)))
            args = SimpleNamespace(
                plan=plan_path, step_index=1, state_dir=root,
                outcomes=outcomes, inventory=witness,
                node_statuses=None, output=output,
            )
            with mock.patch("workflow_kernel.cli._SubprocessRunner", BombRunner):
                with self.assertRaises(InvalidSchemaError):
                    command_execute_cleanup_step(args)
            self.assertEqual(BombRunner.calls, [])

    def test_cleanup_receipt_blocked_or_retained_is_exit_three(self):
        from workflow_kernel.cli import _cleanup_receipt_status
        from workflow_kernel.resources import (
            CleanupDisposition, CleanupReceipt, CleanupScope,
            ResourceDisposition, ResourceKind,
        )
        for disposition in (
            CleanupDisposition.BLOCKED,
            CleanupDisposition.RETAINED_FOR_DEPENDENCY,
        ):
            receipt = CleanupReceipt(
                CleanupScope("run-1"), (), (),
                (ResourceDisposition(
                    "ctr-1", ResourceKind.CONTAINER, "run-1", "node-1",
                    "chunk", disposition, "none", "proof_unavailable",
                ),),
            )
            with self.subTest(disposition=disposition):
                self.assertEqual(_cleanup_receipt_status(receipt), 3)


if __name__ == "__main__":
    unittest.main()
