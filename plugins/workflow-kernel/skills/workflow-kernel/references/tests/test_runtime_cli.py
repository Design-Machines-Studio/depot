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


FIXTURES = Path(__file__).parent / "fixtures" / "receipts"


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
    return value


class RuntimeCliTests(unittest.TestCase):
    def run_cli(self, *args, env_extra=None):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).parents[1]))
        if env_extra:
            env.update(env_extra)
        return subprocess.run([sys.executable, "-m", "workflow_kernel", *map(str, args)], text=True, capture_output=True, env=env, check=False)

    def test_observe_pipeline_writes_shadow_artifact_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "feature": "pipeline-1", "workflowClass": "feature", "executionMode": "codex_native",
                "chunks": [{"id": "chunk-a", "dependsOn": []}], "executionPlan": {"levels": [{"level": 0, "strategy": "sequential", "chunks": ["chunk-a"]}]},
            }))
            result = self.run_cli("observe-pipeline", "--manifest", manifest, "--receipts", FIXTURES / "pipeline-codex.json", "--state-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads((root / "pipeline-shadow-observation.json").read_text())
            self.assertEqual(artifact["observation_type"], "pipeline")
            self.assertEqual(artifact["artifact_role"], "authoritative_observation")
            self.assertEqual(artifact["run_spec"]["workflow_class"], "feature")
            self.assertEqual(artifact["event_count"], 11)

    def test_independent_prediction_is_bound_once_and_terminal_observation_cannot_overwrite_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
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
                "observe-pipeline", "--manifest", manifest,
                "--receipts", FIXTURES / "pipeline-codex.json",
                "--prediction-receipts", predicted, "--state-dir", root,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            prediction_path = root / "pipeline-shadow-prediction.json"
            bound = prediction_path.read_bytes()
            document = json.loads(bound)
            self.assertEqual(document["artifact_role"], "independent_prediction")
            predicted.write_text((FIXTURES / "pipeline-codex.json").read_text())
            second = self.run_cli(
                "observe-pipeline", "--manifest", manifest,
                "--receipts", FIXTURES / "pipeline-codex.json",
                "--prediction-receipts", predicted, "--state-dir", root,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
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
            self.assertEqual(observed.returncode, 0, observed.stderr)
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
            run_spec = {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"claude_full"}
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
            run_spec = {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"claude_full"}
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
                "run_spec": {"run_id":"pipeline-1","workflow_class":"feature","workflow_class_defaulted":False,"execution_mode":"claude_full"},
                "run_state": {"schema_version":1,"revision":len(events),"run_id":"pipeline-1","mode":"shadow","status":"running","created_at":events[0].occurred_at,"updated_at":events[-1].occurred_at,"nodes":{},"evidence":refs,"cleanup_reconciled":False},
            }
            output = root / "parity.json"
            for mutation in ("missing_events", "runspec_mode"):
                artifact = json.loads(json.dumps(base))
                prediction = shadow_artifact(
                    "independent_prediction", artifact["run_spec"],
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
                    self.assertFalse(json.loads(output.read_text())["safe_to_promote"])

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

    def test_cleanup_command_surface_and_plan_create(self):
        help_result = self.run_cli("--help")
        for command in ("plan-create", "plan-compose", "record-create", "plan-cleanup", "next-cleanup-step", "execute-cleanup-step", "record-cleanup", "plan-reconcile"):
            self.assertIn(command, help_result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); argv = root / "argv.json"; output = root / "plan.json"
            argv.write_text(json.dumps(["docker", "run", "--name", "review-box", "image:latest"]))
            result = self.run_cli("plan-create", "--state-dir", root, "--run-id", "run-1", "--node-id", "chunk-1", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", argv, "--output", output)
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
        }
        inventory = DockerInventory((DockerResource(
            "container-1", ResourceKind.CONTAINER, labels, created,
        ),), source="managed_orphan_sweep")

        class Runner:
            def run(self, argv):
                return CommandResult(tuple(argv), 0, "", "")

        class InactiveLease:
            def read(self, run_id):
                return LeaseProof(run_id, False, True, now)

        proved = DockerAdapter(Runner(), now=lambda: now, lease_reader=InactiveLease())
        self.assertTrue(_stale_cleanup_plan(proved, inventory, 24).actions)
        retained = _stale_cleanup_plan(proved, inventory, 72)
        self.assertEqual(retained.dispositions[0].reason, "ttl_not_expired")
        blocked = _stale_cleanup_plan(DockerAdapter(Runner(), now=lambda: now), inventory, 24)
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
            plan = DockerAdapter(type("Runner", (), {"run": lambda _self, argv: None})()).plan_reconcile_run(
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

            run_dir = root / "runs" / "old-run"; run_dir.mkdir(parents=True)
            state = {
                "schema_version":1,"revision":1,"run_id":"old-run","mode":"shadow","status":"succeeded",
                "created_at":now.isoformat(),"updated_at":now.isoformat(),"nodes":{},"evidence":[],"cleanup_reconciled":True,
            }
            (run_dir / "run-state.json").write_text(json.dumps(state))
            proof = StateDirectoryLeaseReader(root, now=lambda: now).read("old-run")
            self.assertFalse(proof.active)
            self.assertTrue(proof.readable)
            self.assertIsNone(StateDirectoryLeaseReader(root, now=lambda: now).read("missing"))

    def test_stale_state_reader_treats_live_os_lease_as_active_and_guard_is_nonblocking(self):
        from workflow_kernel.cli import StateDirectoryLeaseReader
        from workflow_kernel.schema import LeaseConflictError
        from workflow_kernel.state import RunLease
        now = datetime.now(timezone.utc).replace(microsecond=0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run_dir = root / "runs" / "old-run"
            run_dir.mkdir(parents=True)
            state_path = run_dir / "run-state.json"
            state_path.write_text(json.dumps({
                "schema_version":1,"revision":1,"run_id":"old-run",
                "mode":"shadow","status":"succeeded",
                "created_at":now.isoformat(),"updated_at":now.isoformat(),
                "nodes":{},"evidence":[],"cleanup_reconciled":True,
            }))
            reader = StateDirectoryLeaseReader(root, now=lambda: now)
            with RunLease(state_path):
                self.assertTrue(reader.read("old-run").active)
                with self.assertRaises(LeaseConflictError):
                    with reader.inactive_guard("old-run"):
                        self.fail("live run lease must not yield an inactive guard")
            with reader.inactive_guard("old-run") as proof:
                self.assertFalse(proof.active)

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
            "com.designmachines.depot.run-id":"old-run",
            "com.designmachines.depot.node-id":"old-node",
            "com.designmachines.depot.created-at":created.isoformat().replace("+00:00","Z"),
            "com.designmachines.depot.lifecycle":"run",
            "com.designmachines.depot.cleanup-policy":"remove-when-stopped",
        }
        container_list = ("docker","ps","-a","--filter","label=com.designmachines.depot.managed=true","--format","{{.ID}}")
        network_list = ("docker","network","ls","--filter","label=com.designmachines.depot.managed=true","--format","{{.ID}}")
        volume_list = ("docker","volume","ls","--filter","label=com.designmachines.depot.managed=true","--format","{{.Name}}")
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
            root = Path(directory); run_dir = root / "runs" / "old-run"
            run_dir.mkdir(parents=True)
            (run_dir / "run-state.json").write_text(json.dumps({
                "schema_version":1,"revision":1,"run_id":"old-run",
                "mode":"shadow","status":"succeeded",
                "created_at":created.isoformat(),"updated_at":now.isoformat(),
                "nodes":{},"evidence":[],"cleanup_reconciled":True,
            }))
            runner = Runner()
            adapter = DockerAdapter(
                runner, now=lambda: now,
                lease_reader=StateDirectoryLeaseReader(root, now=lambda: now),
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
            root = Path(directory)
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
            adapter = DockerAdapter(PlanningRunner())
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
