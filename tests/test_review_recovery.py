"""Host and retained-companion recovery fixtures; no external execution."""
import copy
import hashlib
import json
import subprocess
import unittest
from unittest import mock

from tests import test_review_closeout as fixtures
from workflow_kernel.review_closeout import (
    assemble_review_evidence, recover_review_evidence, EvidenceAssemblyError,
)
from workflow_kernel.verification_contract import digest


class ReviewRecoveryTests(unittest.TestCase):
    setUp = fixtures.ReviewCloseoutTests.setUp
    tearDown = fixtures.ReviewCloseoutTests.tearDown
    make_run = fixtures.ReviewCloseoutTests.make_run
    preserve = fixtures.ReviewCloseoutTests.preserve

    def write(self, run, name, value):
        path = run.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n")
        return path

    def recover(self, run, value):
        path = self.write(run, "review/recovery-input.json", value)
        return recover_review_evidence(run_root=run.root, repository_root=self.repo, input_path=path)

    def assemble(self, run, paths, value):
        path = self.write(run, "review/new-lane.json", value)
        return assemble_review_evidence(run_root=run.root, repository_root=self.repo,
            request_path=paths["request"], receipts_path=paths["receipts"], input_path=path)

    def source(self, run, paths):
        request = json.loads(paths["request"].read_text())
        head = request["source_head"]
        result = self.recover(run, {"schema_version": 1, "operation": "source", "base": head,
            "heads": [head], "recovered_at": "2026-10-12T00:00:00Z"})
        return head, result["sources"][0]["source_snapshot_ref"]

    def host(self):
        run, paths = self.make_run()
        lane = json.loads(paths["input"].read_text())
        head, source_ref = self.source(run, paths)
        lane["lane"] = "go-build-verifier"
        request = json.loads(paths["request"].read_text())
        request["required_lanes"] = [lane["lane"]]
        self.write(run, "review/request.json", request)
        coverage = json.loads(paths["coverage_input"].read_text())
        coverage["selection"][0]["lane"] = lane["lane"]
        self.write(run, "review/coverage-input.json", coverage)
        receipt = {"schemaVersion": 1, "lane": "check", "commandArgv": ["./tools/verify"],
            "exitStatus": 0, "result": "passed", "stdoutTail": "passed", "stderrTail": "",
            "sourceRepository": lane["source"]["repository"], "sourceHead": head, "sourcePaths": ["source.txt"]}
        self.write(run, "review/host-command.json", receipt)
        envelope = {"schema_version": 1, "lane": lane["lane"], "source": {
            "repository": lane["source"]["repository"], "head": head, "paths": ["source.txt"]},
            "source_snapshots": {head: source_ref},
            "commands": [{"receipt_ref": "review/host-command.json", "plan_ref": None, "lane_id": "check"}],
            "artifacts": {}, "limitations": ["Execution only; no code judgment."]}
        self.write(run, "review/host.json", envelope)
        lane["pass_id"] = "host"
        lane["reviewer"] = "host-verification"
        lane["literal"] = {"output_ref": "raw/security.md", "host_receipt_ref": "review/host.json"}
        lane["inspected"]["basis"] = "host_evidence"
        lane["inspected"]["limitations"] = envelope["limitations"]
        lane["provenance"]["executed_at"] = None
        return run, paths, lane, envelope, receipt

    def coverage(self, run, paths, lane_ref, resolutions=()):
        value = json.loads(paths["coverage_input"].read_text())
        value["pass_id"] = "recovered"
        value["selection"][0]["record_ref"] = lane_ref
        value["resolutions"] = list(resolutions)
        path = self.write(run, "review/new-coverage.json", value)
        # Existing fixed companions describe the earlier fixture pass. A new
        # pass normally lives in a new owned replay, not over those files.
        for name in ("review-lane-receipts.json", "raw-lane-outputs.json", "raw-finding-inventory.json", "synthesis-decisions.json"):
            (run.root / "review" / name).unlink()
        return assemble_review_evidence(run_root=run.root, repository_root=self.repo,
            request_path=paths["request"], receipts_path=paths["receipts"], input_path=path)

    def test_host_success_preserves_without_model_and_terminal_revalidates(self):
        run, paths, lane, _, _ = self.host()
        with mock.patch("workflow_kernel.review_recovery.public_completion", side_effect=AssertionError("model path")):
            result = self.assemble(run, paths, lane)
            self.assertEqual("complete", result["status"])
            self.coverage(run, paths, result["record_ref"])
            self.assertEqual("complete", self.preserve(run, paths)["status"])
            run.finish("succeeded", retain_diagnostics=True)

    def test_host_failure_missing_result_wrong_source_and_altered_artifact_fail(self):
        for mutation in ("failure", "missing", "source", "artifact", "unknown", "identity"):
            with self.subTest(mutation=mutation):
                run, paths, lane, envelope, receipt = self.host()
                original_output = (run.root / "raw/security.md").read_bytes()
                if mutation == "failure":
                    receipt["exitStatus"], receipt["result"] = 1, "failed"
                elif mutation == "source":
                    receipt["sourceHead"] = "a" * 40
                elif mutation == "artifact":
                    envelope["artifacts"] = {"raw/security.md": "sha256:" + "0" * 64}
                elif mutation == "unknown":
                    envelope["source_snapshots"] = {}
                elif mutation == "identity":
                    lane["reviewer"] = "imaginary-model"
                self.write(run, "review/host-command.json", receipt)
                self.write(run, "review/host.json", envelope)
                if mutation == "missing":
                    (run.root / "review/host-command.json").unlink()
                    self.assertEqual("incomplete", self.assemble(run, paths, lane)["status"])
                else:
                    with self.assertRaises(EvidenceAssemblyError):
                        self.assemble(run, paths, lane)
                self.assertEqual(original_output, (run.root / "raw/security.md").read_bytes())

    def test_existing_plan_result_import_checks_command_and_receipt(self):
        run, paths, lane, envelope, _ = self.host()
        head = lane["source"]["head"]
        planned = {"id": "check", "argv": ["docker", "exec", "retained-id", "go", "test", "./pkg"],
                   "command_digest": None, "input_digest": "sha256:" + "b" * 64, "disposition": "run"}
        planned["command_digest"] = digest(planned["argv"])
        plan = {"schema_version": 1, "artifact_role": "repository_verification_plan", "request": {"head_commit": head, "include_worktree": False},
            "lanes": [planned], **{key: "sha256:" + "a" * 64 for key in ("profile_digest", "repository_scope_digest", "execution_closure_digest")}}
        result = {"schema_version": 1, "artifact_role": "repository_verification_result", "request": plan["request"], "head_commit": head,
            "plan_digest": digest(plan), "lanes": [{"lane_id": "check", "exit_code": 0, "status": "passed", "reason": "command_completed",
                "command_digest": planned["command_digest"], "input_digest": planned["input_digest"]}],
            **{key: plan[key] for key in ("profile_digest", "repository_scope_digest", "execution_closure_digest")}}
        self.write(run, "review/plan.json", plan)
        self.write(run, "review/result.json", result)
        envelope["commands"] = [{"receipt_ref": "review/result.json", "plan_ref": "review/plan.json", "lane_id": "check"}]
        self.write(run, "review/host.json", envelope)
        self.assertEqual("complete", self.assemble(run, paths, lane)["status"])
        for change in ("command", "head", "exit", "plan", "missing-lane"):
            bad = copy.deepcopy(result)
            if change == "command": bad["lanes"][0]["command_digest"] = "sha256:" + "0" * 64
            elif change == "head": bad["head_commit"] = "a" * 40
            elif change == "exit": bad["lanes"][0]["exit_code"] = 2
            elif change == "plan": bad["plan_digest"] = "sha256:" + "0" * 64
            else: bad["lanes"] = []
            self.write(run, "review/result.json", bad)
            lane["pass_id"] = change
            with self.assertRaises(EvidenceAssemblyError): self.assemble(run, paths, lane)

    def test_host_cannot_complete_judgment_lanes(self):
        for judgment in ("security", "security-auditor", "pattern-recognition-specialist", "code-simplicity-reviewer"):
            run, paths, lane, envelope, _ = self.host()
            lane["lane"], envelope["lane"] = judgment, judgment
            request = json.loads(paths["request"].read_text())
            request["required_lanes"] = [judgment]
            self.write(run, "review/request.json", request)
            self.write(run, "review/host.json", envelope)
            with self.assertRaises(EvidenceAssemblyError): self.assemble(run, paths, lane)

    def router(self):
        run, paths = self.make_run()
        dispatch_ref = "receipts/private/router/recovered.json"
        dispatch = {"schemaVersion": 1, "receiptId": "dispatch-" + "b" * 24, "participantId": "reviewer-" + "b" * 8,
            "publication": {"output": "published"}, "transportStub": False, "probeSource": "live", "fallback": False,
            "requested": {"role": "review-deep", "effort": "high", "capabilities": ["read-repository", "structured-output"], "humanAuthored": False},
            "served": {"model": "gpt-6.1-sol", "provider": "openai", "transport": "codex-cli", "family": "openai"},
            "attempts": [{"model": "gpt-6.1-sol", "provider": "openai", "transport": "codex-cli", "outcome": "served", "requestedEffort": "high", "normalizedEffort": "high",
                "effortStatus": "transmitted", "transmittedEffort": "high"}],
            "normalizedEffort": "high", "effectiveEffort": "high", "transmittedEffort": "high",
            "effortTransmission": {"status": "transmitted"},
            "familyIndependence": {"passed": True, "humanAuthored": False, "excludedFamilies": []}}
        self.write(run, dispatch_ref, dispatch)
        value = {"schema_version": 1, "operation": "companions", "lane": "security", "dispatch_receipt_ref": dispatch_ref,
            "output_ref": "raw/security.md", "findings": [], "source_witness_ref": None, "recovered_at": "2026-10-12T00:00:00Z"}
        return run, paths, value, dispatch

    def test_legacy_recovery_repeatable_private_identity_and_unknown_source(self):
        run, paths, value, _ = self.router()
        originals = {ref: (run.root / ref).read_bytes() for ref in (value["output_ref"], value["dispatch_receipt_ref"])}
        result = self.recover(run, value)
        self.assertEqual(result, self.recover(run, value))
        companion = json.loads((run.root / result["companion_ref"]).read_text())
        self.assertNotIn("gpt-6.1-sol", json.dumps(companion))
        lane = json.loads(paths["input"].read_text())
        lane.update(pass_id="legacy-recovery", reviewer=result["participant_id"])
        lane["literal"] = {"output_ref": value["output_ref"], "dispatch_receipt_ref": value["dispatch_receipt_ref"],
            "companion_ref": result["companion_ref"], "recovery_ref": result["record_ref"]}
        lane["provenance"]["kind"], lane["provenance"]["executed_at"] = "recovery", None
        produced = self.assemble(run, paths, lane)
        self.assertEqual("incomplete", produced["status"])
        self.assertIn("historical_source_witness", produced["missing"])
        self.assertEqual(lane["requested"]["paths"], produced["fresh_verification_request"]["paths"])
        self.assertEqual(lane["source"]["head"], produced["fresh_verification_request"]["head"])
        self.assertTrue(produced["fresh_verification_request"]["reuse_prior_findings_and_decisions"])
        retry = self.assemble(run, paths, lane)
        self.assertTrue(retry["reused"])
        self.assertEqual(produced["missing"], retry["missing"])
        self.assertEqual(produced["fresh_verification_request"], retry["fresh_verification_request"])
        for ref, data in originals.items(): self.assertEqual(data, (run.root / ref).read_bytes())
        (run.root / value["output_ref"]).write_text("altered output\n")
        lane["pass_id"] = "altered"
        with self.assertRaises(EvidenceAssemblyError): self.assemble(run, paths, lane)

    def test_forged_or_contradictory_dispatch_fails_without_changing_inputs(self):
        for change in ("participant", "served", "family", "effort", "stub", "publication", "legacy-identity", "requested-effort", "normalized-effort", "excluded-family", "independence-required"):
            with self.subTest(change=change):
                run, _, value, dispatch = self.router()
                if change == "participant": dispatch["participantId"] = "security"
                elif change == "served": dispatch["served"]["model"] = "gpt-forged"
                elif change == "family": dispatch["served"]["family"] = "anthropic"
                elif change == "effort": dispatch["transmittedEffort"] = "low"
                elif change == "stub": dispatch["transportStub"] = True
                elif change == "legacy-identity": dispatch["served"]["provider"] = "not_reported"
                elif change == "requested-effort": dispatch["attempts"][0]["requestedEffort"] = "low"
                elif change == "normalized-effort": dispatch["attempts"][0]["normalizedEffort"] = "low"
                elif change == "excluded-family": dispatch["familyIndependence"]["excludedFamilies"] = ["openai"]
                elif change == "independence-required":
                    dispatch["familyIndependence"]["required"] = True
                    dispatch["requested"]["independenceReceiptIds"] = []
                else: dispatch["publication"]["output"] = "pending"
                path = self.write(run, value["dispatch_receipt_ref"], dispatch)
                before = path.read_bytes()
                with self.assertRaises(EvidenceAssemblyError): self.recover(run, value)
                self.assertEqual(before, path.read_bytes())

    def test_recovery_retries_reject_altered_output_and_dispatch(self):
        for target in ("output_ref", "dispatch_receipt_ref"):
            run, _, value, dispatch = self.router()
            first = self.recover(run, value)
            original_record = (run.root / first["record_ref"]).read_bytes()
            if target == "output_ref": (run.root / value[target]).write_text("altered output\n")
            else:
                dispatch["served"]["durationSeconds"] = 999
                self.write(run, value[target], dispatch)
            for timestamp in (value["recovered_at"], "2026-10-12T00:01:00Z"):
                value["recovered_at"] = timestamp
                with self.assertRaises(EvidenceAssemblyError): self.recover(run, value)
            self.assertEqual(original_record, (run.root / first["record_ref"]).read_bytes())

    def test_legacy_absent_effort_fields_remain_unavailable(self):
        run, _, value, dispatch = self.router()
        dispatch.pop("effortTransmission")
        dispatch.pop("transmittedEffort")
        for key in ("requestedEffort", "normalizedEffort", "transmittedEffort", "effortStatus"):
            dispatch["attempts"][0].pop(key)
        self.write(run, value["dispatch_receipt_ref"], dispatch)
        result = self.recover(run, value)
        public = json.loads((run.root / result["companion_ref"]).read_text())
        self.assertIsNone(public["transmittedEffort"])
        self.assertEqual("unavailable", public["effortStatus"])

    def test_legacy_lane_name_cannot_override_reported_dispatch_identity(self):
        run, paths = self.make_run()
        lane = json.loads(paths["input"].read_text())
        dispatch_ref = lane["literal"]["dispatch_receipt_ref"]
        dispatch = json.loads((run.root / dispatch_ref).read_text())
        dispatch["participantId"] = "reviewer-" + "a" * 8
        self.write(run, dispatch_ref, dispatch)
        lane["pass_id"] = "known-identity"
        with self.assertRaises(EvidenceAssemblyError): self.assemble(run, paths, lane)

    def test_authentic_source_witness_preserves_recovered_lane(self):
        run, paths, value, _ = self.router()
        original = json.loads(paths["input"].read_text())
        witness = {"schema_version": 1, "repository": original["source"]["repository"], "head": original["source"]["head"],
            "paths": original["requested"]["paths"], "assignment_ref": "review/prompt.md",
            "head_ref": "review/observed-head.txt", "status_ref": "review/observed-status.txt"}
        (run.root / witness["head_ref"]).write_text(witness["head"] + "\n")
        (run.root / witness["status_ref"]).write_text("")
        self.write(run, "review/witness.json", witness)
        value["source_witness_ref"] = "review/witness.json"
        result = self.recover(run, value)
        original.update(pass_id="witness", reviewer=result["participant_id"])
        original["literal"] = {"output_ref": value["output_ref"], "dispatch_receipt_ref": value["dispatch_receipt_ref"],
            "companion_ref": result["companion_ref"], "recovery_ref": result["record_ref"]}
        original["provenance"] = {"kind": "recovery", "executed_at": None, "source_refs": ["review/prompt.md"]}
        lane = self.assemble(run, paths, original)
        self.assertEqual("complete", lane["status"])
        self.coverage(run, paths, lane["record_ref"])
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        run.finish("succeeded", retain_diagnostics=True)

    def test_interruption_preserves_originals_and_retry(self):
        run, _, value, _ = self.router()
        before = (run.root / value["dispatch_receipt_ref"]).read_bytes()
        with mock.patch("workflow_kernel.review_closeout._seal_record", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.recover(run, value)
        self.assertEqual(before, (run.root / value["dispatch_receipt_ref"]).read_bytes())
        self.assertEqual("derived", self.recover(run, value)["status"])

    def test_reconstruction_keeps_historical_source_unknown(self):
        run, paths = self.make_run()
        head = json.loads(paths["request"].read_text())["source_head"]
        (self.repo / "source.txt").write_text("current dirty source\n")
        result = self.recover(run, {"schema_version": 1, "operation": "source", "base": head, "heads": [head], "recovered_at": "2026-10-12T00:00:00Z"})
        self.assertFalse(result["coverage_proof"])
        self.assertEqual("unknown", result["historical_worktree_state"])
        self.assertEqual("current dirty source\n", (self.repo / "source.txt").read_text())

    def test_fresh_confirmation_resolves_diagnostic_history_without_relabelling(self):
        for mutation in (None, "unknown-source", "missing-resolution", "no-resolutions", "missing-decisions", "wrong-path", "wrong-decision", "discarded-only"):
            with self.subTest(mutation=mutation):
                run, paths = self.make_run()
                lane = json.loads(paths["input"].read_text())
                lane["pass_id"] = "fresh-confirmation"
                finding = {"source_finding_id": "historical-1", "reviewer": "old-lane-name", "lane": "security",
                    "source_severity": "P2", "evidence_ref": "raw/security.md", "finding_path": "source.txt",
                    "finding_anchor": "1", "finding_category": "correctness", "finding_root_cause": "historical defect"}
                if mutation == "wrong-path": finding["finding_path"] = "uninspected.txt"
                second = dict(finding, source_finding_id="historical-2")
                findings = [finding, second]
                decisions = [dict(row, finding_disposition="retained") for row in findings]
                if mutation == "discarded-only":
                    decisions = [dict(row, finding_disposition="discarded") for row in findings]
                if mutation == "wrong-decision": decisions[0]["finding_root_cause"] = "contradictory"
                self.write(run, "history/findings.json", {"schema_version": 1, "artifact_role": "raw_finding_inventory", "run_id": "historical", "findings": findings})
                self.write(run, "history/decisions.json", {"schema_version": 1, "artifact_role": "synthesis_decisions", "source_finding_count": len(findings), "run_id": "historical", "decisions": decisions})
                (run.root / "review/repairs.md").write_text("Current source confirms historical repairs.\n")
                lane["provenance"]["source_refs"] += ["history/findings.json", "history/decisions.json"]
                if mutation == "missing-decisions": lane["provenance"]["source_refs"].remove("history/decisions.json")
                lane["recheck"]["repair_refs"] = ["review/repairs.md"]
                if mutation == "unknown-source": lane["provenance"]["kind"] = "recovery"
                result = self.assemble(run, paths, lane)
                resolutions = [{"source_finding_id": row["source_finding_id"], "repair_ref": "review/repairs.md", "verification_record_ref": result["record_ref"],
                    "historical_findings_ref": "history/findings.json", "historical_decisions_ref": "history/decisions.json"} for row in findings]
                if mutation == "missing-resolution": resolutions.pop()
                if mutation in {"no-resolutions", "missing-decisions", "discarded-only"}: resolutions = []
                before = (run.root / "history/findings.json").read_bytes()
                if mutation not in {None, "discarded-only"}:
                    with self.assertRaises(EvidenceAssemblyError): self.coverage(run, paths, result["record_ref"], resolutions)
                else:
                    self.assertEqual("complete", self.coverage(run, paths, result["record_ref"], resolutions)["status"])
                    self.assertEqual("complete", self.preserve(run, paths)["status"])
                    run.finish("succeeded", retain_diagnostics=True)
                    # The immutable retained copy holds old rows as diagnostics.
                    continue
                self.assertEqual(before, (run.root / "history/findings.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
