from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from workflow_kernel.dm_review_adapter import (
    _document_digest,
    ReviewRequest,
    validate_optional_contribution_coverage,
)
from workflow_kernel.cli import _validated_existing_review_contributions
from workflow_kernel.owned_run import ExactOwnedRun
from workflow_kernel.review_closeout import (
    bind_review_source,
    preserve_review_evidence,
    source_identity,
)


class ReviewCloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "disposable-repository"
        self.repo.mkdir()
        subprocess.run(("git", "init", "--quiet", str(self.repo)), check=True)
        subprocess.run(("git", "-C", str(self.repo), "config", "user.name", "Fixture"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "config", "user.email", "fixture@example.test"), check=True)
        (self.repo / "source.txt").write_text("reviewed source\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "fixture"), check=True)
        self.state = self.root / "state"
        self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def make_run(self, workflow="dm-review", run_id="closeout"):
        run = ExactOwnedRun.start(workflow, run_id, base=self.state)
        source = run.create_path("raw-output", "review")
        run.create_path("raw-output", "receipts")
        run.create_path("raw-output", "receipts/private")
        router = run.create_path("raw-output", "receipts/private/router")
        (router / "terminal-receipt-index.json").write_text(
            json.dumps({"schemaVersion": 1, "receiptFiles": ["security.json"]}) + "\n", encoding="utf-8",
        )
        (router / "security.json").write_text(
            json.dumps({
                "schemaVersion": 1, "receiptId": "dispatch-" + "a" * 24,
                "requested": {}, "attempts": [], "served": None, "fallback": False,
            }) + "\n",
            encoding="utf-8",
        )
        repository, head = source_identity(self.repo)
        request = {
            "run_id": run_id,
            "requested_lanes": ["security"],
            "mode": "full",
            "source_repository": repository,
            "source_head": head,
        }
        output = {"reviewer": "security", "lane": "security", "findings": []}
        output_digest = _document_digest(output)
        lane_receipt = {
            "reviewer": "security", "lane": "security",
            "requested_provider": "openai", "attempted_provider": "openai",
            "implemented_by": "codex", "provider": "openai",
            "model": "gpt-6-sol", "evidence_refs": ["raw/security.md"],
            "implementer_family": "openai", "reviewer_family": "openai",
            "resolution_reason": "same-family-standard-review",
            "raw_output_ref": (
                "contribution-inputs/raw-lane-output-sha256-"
                + output_digest.removeprefix("sha256:") + ".json"
            ),
            "raw_output_digest": output_digest,
            "finding_count": 0,
        }
        receipts = [
            {
                "run_id": run_id, "sequence": 0, "stage": "review_request",
                "status": "accepted", "node_id": None,
                "occurred_at": "2026-09-01T00:00:00Z",
                "authoritative_receipt": "review/request.json", "host": "codex",
                "workflow_class": "feature", "requested_lanes": ["security"],
            },
            {
                "run_id": run_id, "sequence": 1, "stage": "coverage_matrix",
                "status": "complete", "node_id": None,
                "occurred_at": "2026-09-01T00:01:00Z",
                "authoritative_receipt": "review/coverage.json", "host": "codex",
                "expected_lanes": ["security"], "completed_lanes": ["security"],
                "degraded_lanes": [], "unavailable_lanes": [],
            },
        ]
        paths = {
            "request": source / "request.json",
            "receipts": source / "authoritative-receipts.json",
            "lane_receipts": source / "review-lane-receipts.json",
            "raw_lane_outputs": source / "raw-lane-outputs.json",
            "raw_findings": source / "raw-finding-inventory.json",
            "decisions": source / "synthesis-decisions.json",
            "router": router,
        }
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        (source / "coverage.json").write_text("{}\n", encoding="utf-8")
        referenced = self.repo / "raw" / "security.md"
        referenced.parent.mkdir(parents=True, exist_ok=True)
        referenced.write_text("Security lane evidence.\n", encoding="utf-8")
        receipts[0]["source_repository"] = repository
        receipts[0]["source_head"] = head
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[1]["required_browser_cases"] = []
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        paths["lane_receipts"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "review_lane_receipts",
            "run_id": run_id, "lanes": [lane_receipt],
        }) + "\n", encoding="utf-8")
        paths["raw_lane_outputs"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "review_lane_raw_outputs",
            "run_id": run_id, "outputs": [output],
        }) + "\n", encoding="utf-8")
        paths["raw_findings"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "raw_finding_inventory",
            "run_id": run_id, "findings": [],
        }) + "\n", encoding="utf-8")
        paths["decisions"].write_text(json.dumps({
            "schema_version": 1, "artifact_role": "synthesis_decisions",
            "run_id": run_id, "source_finding_count": 0,
            "occurred_at": "2026-09-01T00:01:30Z", "decisions": [],
        }) + "\n", encoding="utf-8")
        report = self.repo / ".claude" / "ux-review" / "report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "## CLEAN\n\nRequired review coverage is complete. "
            "[Lane outputs](review/raw-lane-outputs.json).\n",
            encoding="utf-8",
        )
        paths["report"] = report
        return run, paths

    def preserve(self, run, paths):
        return preserve_review_evidence(
            run_root=run.root,
            repository_root=self.repo,
            request_path=paths["request"],
            receipts_path=paths["receipts"],
            lane_receipts_path=paths["lane_receipts"],
            raw_lane_outputs_path=paths["raw_lane_outputs"],
            raw_findings_path=paths["raw_findings"],
            decisions_path=paths["decisions"],
            private_router_directory=paths["router"],
            report_path=paths.get("report"),
        )

    def test_required_evidence_survives_successful_closeout_and_worktree_removal(self):
        run, paths = self.make_run()
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained = run.finish(
            "succeeded", retain_diagnostics=True,
            reason="review evidence sealed", contains="coverage and lane source evidence",
        )
        self.assertEqual("retained", retained.status)
        evidence = Path(result["evidence_path"])
        shutil.rmtree(self.repo)
        self.assertTrue((evidence / "review/authoritative-receipts.json").is_file())
        self.assertTrue((evidence / "review/raw-lane-outputs.json").is_file())
        self.assertTrue((evidence / "receipts/private/router/security.json").is_file())
        self.assertTrue((evidence / "raw/security.md").is_file())
        self.assertEqual(
            "## CLEAN\n\nRequired review coverage is complete. "
            "[Lane outputs](review/raw-lane-outputs.json).\n",
            (evidence / "report.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(retained.to_dict(), ExactOwnedRun.open(run.root).finish("succeeded").to_dict())

    def test_premature_success_cleanup_cannot_delete_review_evidence(self):
        run, paths = self.make_run()
        original = paths["raw_lane_outputs"].read_bytes()
        with self.assertRaisesRegex(ValueError, "review evidence must be retained"):
            run.finish("succeeded")
        self.assertTrue(run.root.is_dir())
        self.assertEqual(original, paths["raw_lane_outputs"].read_bytes())

    def test_failed_required_finalization_can_be_retained_for_recovery(self):
        run, paths = self.make_run()
        raw = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        raw["outputs"] = []
        paths["raw_lane_outputs"].write_text(json.dumps(raw) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertTrue(result["missing"])
        retained = run.finish(
            "failed", retain_diagnostics=True,
            reason="required lane source is incomplete", contains="available lane receipts and retry inputs",
        )
        self.assertEqual("retained", retained.status)
        self.assertTrue(Path(retained.path, "CLEANUP.txt").is_file())
        self.assertTrue(Path(result["evidence_path"], "review/request.json").is_file())
        self.assertTrue(Path(result["recovery_path"]).is_dir())

    def test_incomplete_bound_coverage_is_retained_in_its_exact_head_scope(self):
        run, paths = self.make_run("dm-review", "bound-incomplete")
        raw = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        raw["outputs"] = []
        paths["raw_lane_outputs"].write_text(json.dumps(raw) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertIn("repo-", Path(result["evidence_path"]).name)
        self.assertIn("-head-", Path(result["evidence_path"]).name)
        self.assertNotEqual("unbound", Path(result["evidence_path"]).name)

    def test_verified_bound_copy_retires_only_superseded_owned_scopes(self):
        run, paths = self.make_run("dm-review", "scope-retry")
        first = self.preserve(run, paths)
        stale = Path(first["recovery_path"]) / "review" / "unbound"
        stale.mkdir(mode=0o700)
        (stale / "incomplete.json").write_text("{}\n", encoding="utf-8")
        second = self.preserve(run, paths)
        self.assertEqual("complete", second["status"])
        self.assertFalse(stale.exists())
        self.assertTrue(Path(second["evidence_path"], "review/request.json").is_file())

    def test_failed_evidence_relocation_leaves_source_intact(self):
        run, paths = self.make_run()
        originals = {key: value.read_bytes() for key, value in paths.items() if isinstance(value, Path) and value.is_file()}
        with mock.patch("workflow_kernel.review_closeout.os.replace", side_effect=OSError("injected relocation failure")):
            with self.assertRaises(OSError):
                self.preserve(run, paths)
        self.assertTrue(run.root.is_dir())
        for key, content in originals.items():
            self.assertEqual(content, paths[key].read_bytes())

    def test_closeout_retry_reuses_exact_evidence_without_duplicate_receipts(self):
        run, paths = self.make_run()
        first = self.preserve(run, paths)
        second = self.preserve(run, paths)
        self.assertEqual("complete", first["status"])
        self.assertEqual(first["evidence_path"], second["evidence_path"])
        receipts = json.loads((Path(second["evidence_path"]) / "review/authoritative-receipts.json").read_text())
        self.assertEqual(2, len(receipts))
        self.assertEqual(1, len(list((Path(second["evidence_path"]) / "receipts/private/router").glob("*.json"))) - 1)

    def test_changed_head_cannot_complete_closeout(self):
        run, paths = self.make_run()
        (self.repo / "source.txt").write_text("changed head\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "changed"), check=True)
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_missing_required_lane_evidence_reference_cannot_complete_closeout(self):
        run, paths = self.make_run("dm-review", "missing-evidence-ref")
        (self.repo / "raw/security.md").unlink()
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"])
        self.assertTrue(any("raw/security.md" in item for item in result["missing"]))

    def test_source_binding_rejects_changed_head_without_rewriting_the_request(self):
        run, paths = self.make_run("dm-review", "stale-source")
        before = paths["request"].read_bytes()
        (self.repo / "source.txt").write_text("new HEAD\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "new head"), check=True)
        with self.assertRaisesRegex(ValueError, "source scope is stale"):
            bind_review_source(
                run_root=run.root, repository_root=self.repo, request_path=paths["request"],
            )
        self.assertEqual(before, paths["request"].read_bytes())

    def test_bind_review_source_cli_persists_identity_before_dispatch(self):
        run, paths = self.make_run("dm-review", "bind-cli")
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request.pop("source_repository")
        request.pop("source_head")
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        environment = os.environ.copy()
        references = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references"
        environment["PYTHONPATH"] = str(references) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "bind-review-source",
                "--run-root", str(run.root), "--repository-root", str(self.repo),
                "--request", str(paths["request"]),
            ), env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        bound = json.loads(paths["request"].read_text(encoding="utf-8"))
        repository, head = source_identity(self.repo)
        self.assertEqual(repository, result["source_repository"])
        self.assertEqual(head, result["source_head"])
        self.assertEqual(repository, bound["source_repository"])
        self.assertEqual(head, bound["source_head"])

    def test_mismatched_browser_cases_cannot_complete_closeout(self):
        run, paths = self.make_run()
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["required_lanes"] = ["security", "visual"]
        request["requested_lanes"] = ["security", "visual"]
        request["required_browser_cases"] = ["home", "settings"]
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        repository, head = source_identity(self.repo)
        outputs = json.loads(paths["raw_lane_outputs"].read_text(encoding="utf-8"))
        visual_output = {"reviewer": "visual", "lane": "visual", "findings": []}
        visual_digest = _document_digest(visual_output)
        outputs["outputs"].append(visual_output)
        paths["raw_lane_outputs"].write_text(json.dumps(outputs) + "\n", encoding="utf-8")
        lane_document = json.loads(paths["lane_receipts"].read_text(encoding="utf-8"))
        visual_receipt = dict(lane_document["lanes"][0])
        visual_receipt.update({
            "reviewer": "visual", "lane": "visual",
            "raw_output_digest": visual_digest,
            "raw_output_ref": (
                "contribution-inputs/raw-lane-output-sha256-"
                + visual_digest.removeprefix("sha256:") + ".json"
            ),
        })
        lane_document["lanes"].append(visual_receipt)
        paths["lane_receipts"].write_text(json.dumps(lane_document) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[0]["requested_lanes"] = ["security", "visual"]
        receipts[0]["source_repository"] = repository
        receipts[0]["source_head"] = head
        receipts[1]["expected_lanes"] = ["security", "visual"]
        receipts[1]["completed_lanes"] = ["security", "visual"]
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[1]["required_browser_cases"] = ["home", "settings"]
        receipts.append({
            "run_id": request["run_id"], "sequence": 2,
            "stage": "browser_verification", "status": "completed",
            "node_id": "visual", "occurred_at": "2026-09-01T00:02:00Z",
            "authoritative_receipt": "review/browser.json", "host": "codex",
            "source_repository": repository, "source_head": head,
            "case_ids": ["home"], "evidence_refs": ["browser/case-home.json"],
        })
        (self.repo / "browser").mkdir(parents=True, exist_ok=True)
        (self.repo / "browser/case-home.json").write_text("{}\n", encoding="utf-8")
        review_directory = paths["request"].parent
        (review_directory / "browser.json").write_text("{}\n", encoding="utf-8")
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_completed_browser_case_after_coverage_matrix_is_accepted(self):
        run, paths = self.make_run("dm-review", "browser-after-coverage")
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["required_browser_cases"] = ["home"]
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[1]["required_browser_cases"] = ["home"]
        receipts.append({
            "run_id": request["run_id"], "sequence": 2,
            "stage": "browser_verification", "status": "completed",
            "node_id": "visual", "occurred_at": "2026-09-01T00:02:00Z",
            "authoritative_receipt": "review/browser.json", "host": "codex",
            "source_repository": request["source_repository"],
            "source_head": request["source_head"],
            "case_ids": ["home"], "evidence_refs": ["browser/case-home.json"],
        })
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        (paths["request"].parent / "browser.json").write_text("{}\n", encoding="utf-8")
        (self.repo / "browser").mkdir()
        (self.repo / "browser/case-home.json").write_text("{}\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertTrue(Path(result["evidence_path"], "browser/case-home.json").is_file())

    def test_optional_contribution_cost_and_observation_outputs_do_not_gate_coverage(self):
        run, paths = self.make_run()
        self.assertFalse(validate_optional_contribution_coverage([]))
        request = ReviewRequest.from_mapping(json.loads(paths["request"].read_text()))
        receipts = json.loads(paths["receipts"].read_text())
        self.assertIsNone(_validated_existing_review_contributions(request, receipts, self.state))
        # No cost summary, shadow comparison, or observation index is required
        # by the source coverage validator.
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_failed_optional_contribution_receipt_does_not_downgrade_coverage(self):
        run, paths = self.make_run()
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts.append({"sequence": 2, "stage": "finding_contribution", "status": "failed"})
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained_receipts = json.loads(
            (Path(result["evidence_path"]) / "review/authoritative-receipts.json").read_text(encoding="utf-8"),
        )
        self.assertEqual(receipts, retained_receipts)

    def test_unvalidated_later_coverage_cannot_override_incomplete_coverage(self):
        run, paths = self.make_run("dm-review", "malformed-recheck")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[1]["completed_lanes"] = []
        receipts[1]["unavailable_lanes"] = ["security"]
        receipts.append({"stage": "finding_contribution", "status": "failed"})
        receipts.append({
            "stage": "coverage_matrix", "expected_lanes": ["security"],
            "completed_lanes": ["security"], "degraded_lanes": [],
            "unavailable_lanes": [], "source_repository": receipts[1]["source_repository"],
            "source_head": receipts[1]["source_head"], "required_browser_cases": [],
        })
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])

    def test_valid_recheck_after_optional_contribution_can_complete(self):
        run, paths = self.make_run("dm-review", "valid-recheck")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[1]["completed_lanes"] = []
        receipts[1]["unavailable_lanes"] = ["security"]
        receipts.append({"stage": "finding_contribution", "status": "failed"})
        final = dict(receipts[1])
        final.update({
            "sequence": 3, "occurred_at": "2026-09-01T00:03:00Z",
            "completed_lanes": ["security"], "unavailable_lanes": [],
        })
        receipts.append(final)
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        self.assertEqual("complete", self.preserve(run, paths)["status"])

    def test_broken_report_link_blocks_successful_preservation_and_keeps_source(self):
        run, paths = self.make_run()
        paths["report"].write_text(
            "## CLEAN\n\n[Missing evidence](review/missing.md).\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "retained report"):
            self.preserve(run, paths)
        self.assertTrue(paths["report"].is_file())
        with self.assertRaisesRegex(ValueError, "durably validated"):
            run.finish("succeeded", retain_diagnostics=True)

    def test_corrected_source_report_can_be_preserved_after_link_failure(self):
        run, paths = self.make_run("dm-review", "corrected-report")
        paths["report"].write_text("[Missing](review/missing.md).\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "retained report link is missing"):
            self.preserve(run, paths)
        paths["report"].write_text("[Request](review/request.json).\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        self.assertEqual(paths["report"].read_bytes(), (Path(result["evidence_path"]) / "report.md").read_bytes())

    def test_indexed_router_receipt_must_survive_preservation_and_finish(self):
        run, paths = self.make_run("dm-review", "router-index")
        paths["router"].joinpath("security.json").unlink()
        paths["router"].joinpath("unrelated.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises((OSError, ValueError)):
            self.preserve(run, paths)
        self.assertTrue(run.root.is_dir())
        paths["router"].joinpath("unrelated.json").unlink()
        paths["router"].joinpath("security.json").write_text(json.dumps({
            "schemaVersion": 1, "receiptId": "dispatch-" + "a" * 24,
            "requested": {}, "attempts": [], "served": None, "fallback": False,
        }) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        Path(result["evidence_path"], "receipts/private/router/security.json").unlink()
        with self.assertRaisesRegex(ValueError, "not durably validated"):
            run.finish("succeeded", retain_diagnostics=True)

    def test_reference_style_report_link_must_resolve(self):
        run, paths = self.make_run("dm-review", "reference-link")
        paths["report"].write_text(
            "[Lane outputs][lane]\n\n[lane]: review/missing.json\n", encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "retained report link is missing"):
            self.preserve(run, paths)

    def test_retained_recovery_retry_reuses_exact_sources_without_lane_rerun(self):
        run, paths = self.make_run("dm-review", "report-retry")
        paths["report"].write_text(
            "## CLEAN\n\n[Missing evidence](review/missing.md).\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "retained report"):
            self.preserve(run, paths)
        evidence = next((run.root / "diagnostic/review").iterdir())
        retained = run.finish(
            "failed", retain_diagnostics=True,
            reason="report link validation failed", contains="required source evidence and retry report",
        )
        self.assertEqual("retained", retained.status)
        evidence_request = evidence / "review/request.json"
        paths.update({
            "request": evidence_request,
            "receipts": evidence / "review/authoritative-receipts.json",
            "lane_receipts": evidence / "review/review-lane-receipts.json",
            "raw_lane_outputs": evidence / "review/raw-lane-outputs.json",
            "raw_findings": evidence / "review/raw-finding-inventory.json",
            "decisions": evidence / "review/synthesis-decisions.json",
            "router": evidence / "receipts/private/router",
            "report": evidence / "report.md",
        })
        paths["report"].write_text(
            "## CLEAN\n\n[Lane outputs](review/raw-lane-outputs.json).\n",
            encoding="utf-8",
        )
        before = paths["raw_lane_outputs"].read_bytes()
        retry = self.preserve(run, paths)
        self.assertEqual("complete", retry["status"], retry)
        self.assertEqual(before, (evidence / "review/raw-lane-outputs.json").read_bytes())
        receipt_values = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        self.assertEqual(2, len(receipt_values))
        finished = ExactOwnedRun.open(run.root).finish("succeeded", retain_diagnostics=True)
        self.assertEqual("retained", finished.status)
        self.assertTrue((evidence / "report.md").is_file())

    def test_repaired_head_recheck_can_complete_with_the_new_exact_scope(self):
        run, paths = self.make_run("dm-review", "rechecked")
        (self.repo / "source.txt").write_text("repaired source\n", encoding="utf-8")
        subprocess.run(("git", "-C", str(self.repo), "add", "source.txt"), check=True)
        subprocess.run(("git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair"), check=True)
        repository, head = source_identity(self.repo)
        request = json.loads(paths["request"].read_text(encoding="utf-8"))
        request["source_repository"] = repository
        request["source_head"] = head
        paths["request"].write_text(json.dumps(request) + "\n", encoding="utf-8")
        receipts = json.loads(paths["receipts"].read_text(encoding="utf-8"))
        receipts[0]["source_repository"] = repository
        receipts[0]["source_head"] = head
        receipts[1]["source_repository"] = repository
        receipts[1]["source_head"] = head
        receipts[1]["required_browser_cases"] = []
        paths["receipts"].write_text(json.dumps(receipts) + "\n", encoding="utf-8")
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        run.finish(
            "succeeded", retain_diagnostics=True,
            reason="rechecked evidence sealed", contains="repaired head coverage",
        )

    def test_supported_cli_seals_and_reports_the_durable_evidence_path(self):
        run, paths = self.make_run("dm-review", "cli-closeout")
        environment = os.environ.copy()
        references = Path(__file__).resolve().parents[1] / "plugins/workflow-kernel/skills/workflow-kernel/references"
        environment["PYTHONPATH"] = str(references) + os.pathsep + environment.get("PYTHONPATH", "")
        completed = subprocess.run(
            (
                sys.executable, "-m", "workflow_kernel", "preserve-review-evidence",
                "--run-root", str(run.root), "--repository-root", str(self.repo),
                "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
                "--lane-receipts", str(paths["lane_receipts"]),
                "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
                "--raw-findings", str(paths["raw_findings"]),
                "--decisions", str(paths["decisions"]),
                "--private-router-directory", str(paths["router"]),
                "--report", str(paths["report"]),
            ), env=environment, capture_output=True, text=True, check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("complete", result["status"])
        self.assertTrue(Path(result["evidence_path"], "review/authoritative-receipts.json").is_file())

    def test_pipeline_and_loop_owners_use_the_same_single_closeout(self):
        for workflow in ("dm-review-loop", "pipeline"):
            with self.subTest(workflow=workflow):
                run, paths = self.make_run(workflow, "owner-" + workflow)
                result = self.preserve(run, paths)
                self.assertEqual("complete", result["status"])
                first = run.finish("succeeded", retain_diagnostics=True, reason="review evidence sealed", contains="required review evidence")
                second = ExactOwnedRun.open(run.root).finish("succeeded")
                self.assertEqual(first.to_dict(), second.to_dict())
                self.assertEqual(1, len(list((run.root / "diagnostic").glob("review/*"))))

    def test_unrelated_files_and_author_worktrees_survive_exact_review_cleanup(self):
        run, paths = self.make_run()
        unrelated = self.root / "unrelated.txt"
        author_worktree = self.root / "author-worktree"
        unrelated.write_text("preserve", encoding="utf-8")
        subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "add", "--quiet", "--detach", str(author_worktree), "HEAD"),
            check=True,
        )
        (author_worktree / "uncommitted.txt").write_text("author", encoding="utf-8")
        self.assertEqual("complete", self.preserve(run, paths)["status"])
        run.finish("succeeded", retain_diagnostics=True, reason="review evidence sealed", contains="required review evidence")
        self.assertEqual("preserve", unrelated.read_text(encoding="utf-8"))
        self.assertEqual("author", (author_worktree / "uncommitted.txt").read_text(encoding="utf-8"))
        worktrees = subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "list", "--porcelain"),
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn(str(author_worktree), worktrees)
        subprocess.run(
            ("git", "-C", str(self.repo), "worktree", "remove", "--force", str(author_worktree)),
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
