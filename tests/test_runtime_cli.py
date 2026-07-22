import json
import hashlib
import os
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
        "manual_requirements": [],
        "revision_justification": {
            "reason_code": "initial_binding", "summary": "Initial binding.",
            "added_obligation_ids": [
                "PROOF:CHK-001:REQ-001", "PROOF:CHK-001:REG-001",
                "REG-001", "REQ-001",
            ],
            "retained_obligation_ids": [], "removed_obligation_ids": [],
            "human_approval_evidence_ref": None,
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

    def test_decide_validation_retry_matches_canonical_policy_without_writes(self):
        from workflow_kernel.model import AttemptLedger, FailureReason
        from workflow_kernel.policies import RetryPolicy

        cases = (
            (
                "deterministic_validation_failure",
                {"counts": {}, "signatures": {}}, None,
                "retry_allowed",
            ),
            (
                "deterministic_validation_failure",
                {"counts": {"deterministic_validation_failure": 1},
                 "signatures": {}}, None,
                "retry_budget_exhausted",
            ),
            (
                "reviewer_finding",
                {"counts": {"reviewer_finding": 2},
                 "signatures": {"reviewer_finding": ["same", "same"]}},
                "same", "identical_failure_convergence",
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (reason, ledger, signature, expected) in enumerate(cases):
                path = root / f"ledger-{index}.json"
                path.write_text(json.dumps(ledger))
                before = path.read_bytes()
                arguments = [
                    "decide-validation-retry", "--reason", reason,
                    "--attempt-ledger", path,
                ]
                if signature is not None:
                    arguments.extend(("--signature", signature))
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                document = json.loads(result.stdout)
                self.assertEqual(set(document), {
                    "allowed", "reason_code", "budget", "attempt_count",
                    "prior_signature",
                })
                self.assertEqual(document["reason_code"], expected)
                direct = RetryPolicy().decide(
                    FailureReason(reason),
                    AttemptLedger(ledger["counts"], ledger["signatures"]),
                    signature,
                )
                self.assertEqual(document, {
                    "allowed": direct.allowed,
                    "reason_code": direct.reason_code,
                    "budget": direct.budget,
                    "attempt_count": direct.attempt_count,
                    "prior_signature": direct.prior_signature,
                })
                self.assertEqual(path.read_bytes(), before)

    def test_decide_validation_retry_rejects_hostile_ledgers_without_echo_or_writes(self):
        secret = "sk-secret-ledger-value"
        cases = (
            {"counts": {}, "signatures": {}, "unknown": secret},
            {"counts": {"unknown_reason": 1}, "signatures": {}},
            {"counts": {"cleanup": True}, "signatures": {}},
            {"counts": {"cleanup": 0}, "signatures": {"cleanup": [secret]}},
            {"counts": {"cleanup": 1}, "signatures": {"cleanup": [secret]}},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, ledger in enumerate(cases):
                path = root / f"hostile-{index}.json"
                path.write_text(json.dumps(ledger))
                before = path.read_bytes()
                result = self.run_cli(
                    "decide-validation-retry", "--reason", "cleanup",
                    "--attempt-ledger", path, "--signature", secret,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(secret, result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), before)

            reason = self.run_cli(
                "decide-validation-retry", "--reason", secret,
                "--attempt-ledger", root / "hostile-0.json",
            )
            self.assertNotEqual(reason.returncode, 0)
            self.assertNotIn(secret, reason.stdout + reason.stderr)

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
                "human_approval_evidence_ref": justification[
                    "human_approval_evidence_ref"
                ],
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
                "reason_code", "human_approval_evidence_ref",
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

    def test_verification_contract_revision_uses_replay_and_rejects_stale_digest(self):
        from workflow_kernel.behavioral_contract import contract_digest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            initial_value = verification_contract()
            initial = root / "contract-1.json"
            initial.write_text(json.dumps(initial_value))
            bound = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", initial,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)

            revision_value = json.loads(json.dumps(initial_value))
            revision_value["revision"] = 2
            revision_value["previous_contract_digest"] = contract_digest(initial_value)
            revision_value["prohibited_regressions"] = []
            revision_value["checks"][0]["proves_regression_ids"] = []
            revision_value["revision_justification"] = {
                "reason_code": "approved_scope_change", "summary": "Approved removal.",
                "added_obligation_ids": [],
                "retained_obligation_ids": ["PROOF:CHK-001:REQ-001", "REQ-001"],
                "removed_obligation_ids": ["REG-001", "PROOF:CHK-001:REG-001"],
                "human_approval_evidence_ref": "plans/contract/plan.html#approval",
            }
            revision = root / "contract-2.json"
            revision.write_text(json.dumps(revision_value))
            revised = self.run_cli(
                "revise-verification-contract", "--state-dir", run_dir,
                "--contract", revision,
            )
            self.assertEqual(revised.returncode, 0, revised.stderr)
            receipt = json.loads(revised.stdout)
            self.assertEqual(receipt["stage"], "verification_contract_revised")
            self.assertEqual(receipt["revision"], 2)
            self.assertEqual(
                receipt["previous_contract_digest"],
                json.loads(bound.stdout)["contract_digest"],
            )
            event = json.loads((run_dir / "events.jsonl").read_text().splitlines()[-1])
            self.assertEqual(
                event["payload"]["human_approval_evidence_ref"],
                "plans/contract/plan.html#approval",
            )
            artifact = run_dir / event["payload"]["contract_ref"]
            revision_record = json.loads(artifact.read_text())["revision_justification"]
            self.assertEqual(
                revision_record["removed_obligation_ids"],
                ["PROOF:CHK-001:REG-001", "REG-001"],
            )
            self.assertEqual(revision_record["summary"], "Approved removal.")

            stale = json.loads(json.dumps(revision_value))
            stale["revision"] = 3
            stale["previous_contract_digest"] = "sha256:" + "0" * 64
            stale["revision_justification"] = {
                "reason_code": "metadata_update", "summary": "Stale update.",
                "added_obligation_ids": [],
                "retained_obligation_ids": ["PROOF:CHK-001:REQ-001", "REQ-001"],
                "removed_obligation_ids": [],
                "human_approval_evidence_ref": None,
            }
            stale_path = root / "contract-stale.json"
            stale_path.write_text(json.dumps(stale))
            rejected = self.run_cli(
                "revise-verification-contract", "--state-dir", run_dir,
                "--contract", stale_path,
            )
            self.assertEqual(rejected.returncode, 2)
            self.assertNotIn("0000000000", rejected.stderr)

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

    def test_forged_unapproved_revision_cannot_reconcile_missing_artifact(self):
        from workflow_kernel.behavioral_contract import contract_digest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "contract-run")
            run_dir = root / ".workflow-kernel" / "runs" / "contract-run"
            initial_value = verification_contract()
            initial = root / "contract-1.json"
            initial.write_text(json.dumps(initial_value))
            bound = self.run_cli(
                "bind-verification-contract", "--state-dir", run_dir,
                "--contract", initial,
            )
            self.assertEqual(bound.returncode, 0, bound.stderr)

            forged = json.loads(json.dumps(initial_value))
            forged.update({
                "revision": 2,
                "previous_contract_digest": contract_digest(initial_value),
            })
            forged["prohibited_regressions"] = []
            forged["checks"][0]["proves_regression_ids"] = []
            forged["revision_justification"] = {
                "reason_code": "unapproved_removal", "summary": "Remove regression.",
                "added_obligation_ids": [],
                "retained_obligation_ids": ["PROOF:CHK-001:REQ-001", "REQ-001"],
                "removed_obligation_ids": ["REG-001", "PROOF:CHK-001:REG-001"],
                "human_approval_evidence_ref": None,
            }
            revision = root / "contract-2.json"
            revision.write_text(json.dumps(forged))
            _digest, reference = self.append_contract_binding(
                run_dir, forged, "verification_contract_revised",
            )

            result = self.run_cli(
                "revise-verification-contract", "--state-dir", run_dir,
                "--contract", revision,
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

    def test_review_boundary_launcher_contract_rejects_caller_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.init_lifecycle(root, "boundary-run")
            subprocess.run(("git", "config", "user.email", "boundary@example.test"), cwd=root, check=True)
            subprocess.run(("git", "config", "user.name", "Boundary Test"), cwd=root, check=True)
            (root / ".gitignore").write_text(".workflow-kernel/\n")
            product = root / "product.txt"; product.write_text("base\n")
            subprocess.run(("git", "add", ".gitignore", "product.txt"), cwd=root, check=True)
            subprocess.run(("git", "commit", "-qm", "base"), cwd=root, check=True)
            state = root / ".workflow-kernel" / "runs" / "boundary-run"
            receipt_path = root / "boundary-receipt.json"
            captured = self.run_cli(
                "review-boundary-capture", "--state-dir", state,
                "--repo-root", root, "--output", receipt_path,
            )
            self.assertEqual(captured.returncode, 0, captured.stderr)
            receipt = json.loads(receipt_path.read_text())
            compared = self.run_cli(
                "review-boundary-compare", "--state-dir", state,
                "--repo-root", root, "--before-ref", receipt["boundary_ref"],
                "--output", root / "boundary-compare.json",
            )
            self.assertEqual(compared.returncode, 3, compared.stderr)
            self.assertIn("provider_state_unavailable", json.loads(
                (root / "boundary-compare.json").read_text(),
            )["provider_state_reasons"])
            caller_exclusion = self.run_cli(
                "review-boundary-capture", "--state-dir", state,
                "--repo-root", root, "--artifact-root", root / "product.txt",
                "--output", root / "invalid-boundary.json",
            )
            self.assertEqual(caller_exclusion.returncode, 2)

    def test_cleanup_command_surface_and_plan_create(self):
        help_result = self.run_cli("--help")
        for command in (
            "bind-prediction", "bind-verification-contract", "revise-verification-contract",
            "plan-create", "plan-compose", "record-create", "plan-cleanup",
            "next-cleanup-step", "execute-cleanup-step", "record-cleanup", "plan-reconcile",
            "verification-plan", "verification-run", "verification-result",
            "evidence-match", "artifact-classify", "staging-allowlist",
            "browser-scenario-validate", "browser-bundle-record", "review-record",
            "review-boundary-capture", "review-boundary-compare",
            "ci-evidence-normalize", "closeout-audit", "improvement-index",
            "improvement-finalize", "improvement-render",
        ):
            self.assertIn(command, help_result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); argv = root / "argv.json"; output = root / "plan.json"
            self.init_lifecycle(root, "run-1")
            argv.write_text(json.dumps(["docker", "run", "--name", "review-box", "image:latest"]))
            result = self.run_cli("plan-create", "--state-dir", root / ".workflow-kernel" / "runs" / "run-1", "--run-id", "run-1", "--node-id", "chunk-1", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", argv, "--output", output)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text())
            self.assertTrue(plan["managed"])
            self.assertIn("com.designmachines.depot.run-id", plan["labels"])

    def test_release_matrix_executes_all_new_commands_through_real_launcher(self):
        from tests.test_release_validator import VALIDATOR
        launcher = KERNEL_REFERENCES / "workflow-kernel-launcher.sh"
        new_commands = {
            "verification-plan", "verification-run", "verification-result",
            "evidence-match", "artifact-classify", "staging-allowlist",
            "browser-scenario-validate", "browser-bundle-record", "review-record",
            "review-boundary-capture", "review-boundary-compare",
            "ci-evidence-normalize", "closeout-audit", "improvement-index",
            "improvement-finalize", "improvement-render",
        }
        invoked = []
        module_run = VALIDATOR.run

        def through_launcher(command):
            self.assertEqual(command[:3], [sys.executable, "-m", "workflow_kernel"])
            if command[3] not in new_commands:
                return module_run(command)
            invoked.append(command[3])
            return subprocess.run(
                [str(launcher), *command[3:]], cwd=VALIDATOR.ROOT,
                env=VALIDATOR.deterministic_env(), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )

        context = {}
        with mock.patch.object(VALIDATOR, "run", side_effect=through_launcher):
            VALIDATOR.check_cli(context, new_cli_only=True)
        self.assertTrue(new_commands <= set(invoked))
        self.assertTrue(all(
            context["cli_commands"][name] == (3 if name == "review-boundary-compare" else 0)
            for name in new_commands
        ))

    def test_runtime_resolver_ignores_cwd_and_rejects_symlink_escape(self):
        from workflow_kernel.cli import resolve_workflow_kernel_runtime
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); depot = root / "depot"; pipeline = depot / "plugins" / "pipeline"
            runtime = depot / "plugins" / "workflow-kernel"; refs = runtime / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
            refs.mkdir(parents=True); pipeline.mkdir(parents=True)
            (runtime / ".claude-plugin").mkdir(); (runtime / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name":"workflow-kernel","version":"0.1.0"}))
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
            for version in ("0.1.9", "0.1.10", "1.0.0"):
                runtime = cache / version
                refs = runtime / "skills" / "workflow-kernel" / "references" / "workflow_kernel"
                refs.mkdir(parents=True)
                (runtime / ".claude-plugin").mkdir()
                (runtime / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name":"workflow-kernel","version":version}))
                (refs / "__main__.py").write_text("")
            resolved = resolve_workflow_kernel_runtime(pipeline, home=root / "home")
            self.assertEqual(resolved, (cache / "0.1.10" / "skills" / "workflow-kernel" / "references").resolve())

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
