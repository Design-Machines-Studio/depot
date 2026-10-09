"""Sanitized upgrade fixtures; production historical trust is never changed."""
from __future__ import annotations

import hashlib
import json
import os
import unittest
import sys
from pathlib import Path
from unittest import mock

from tests import test_review_closeout as fixture
from workflow_kernel import review_closeout as closeout
from workflow_kernel.cli import main
from workflow_kernel.owned_run import ExactOwnedRun


class HistoricalReviewCloseoutTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve

    @staticmethod
    def original_contract(*documents, **kwargs):
        kwargs.pop("evidence_root", None)
        kwargs.pop("repository_root", None)
        return closeout._validate_review_common_contract(*documents, **kwargs)

    @staticmethod
    def bytes_of(root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*") if path.is_file()}

    def saved_inventory(self, run):
        inventory = self.root / (run.run_id + "-digests.json")
        inventory.write_text(json.dumps({name: hashlib.sha256(data).hexdigest()
            for name, data in self.bytes_of(run.root).items()}, sort_keys=True) + "\n")
        return inventory

    def pinned_fixture(self, run, inventory):
        repository, head = closeout.source_identity(self.repo)
        return mock.patch.object(closeout, "_HISTORICAL_REVIEW", (
            hashlib.sha256(inventory.read_bytes()).hexdigest(), run.workflow, run.run_id, repository, head))

    def historical(self, *, retained=True, browser=False):
        run, paths = self.make_run("pipeline", "historical", legacy=True)
        if browser:
            request = json.loads(paths["request"].read_text())
            request["required_browser_cases"] = ["home"]
            paths["request"].write_text(json.dumps(request))
            receipts = json.loads(paths["receipts"].read_text())
            receipts[1]["required_browser_cases"] = ["home"]
            receipts.append({"run_id": run.run_id, "sequence": 2, "stage": "browser_verification",
                "status": "completed", "node_id": "visual", "occurred_at": "2026-09-01T00:02:00Z",
                "authoritative_receipt": "review/browser.json", "host": "codex",
                "source_repository": request["source_repository"], "source_head": request["source_head"],
                "case_ids": ["home"], "evidence_refs": ["review/browser.json"]})
            paths["receipts"].write_text(json.dumps(receipts))
            (paths["request"].parent / "browser.json").write_text("{}\n")
        # Simulate preservation and successful retention under the original
        # supported validator, then remove the patch to model an upgrade.
        with mock.patch.object(closeout, "validate_review_source_coverage", side_effect=self.original_contract):
            result = self.preserve(run, paths)
            self.assertEqual("complete", result["status"])
            if retained:
                run.finish("succeeded", retain_diagnostics=True)
        return run, Path(result["evidence_path"]), self.saved_inventory(run)

    def assert_reason(self, reason, callback):
        with self.assertRaises(closeout.RetainedReviewValidationError) as caught:
            callback()
        self.assertEqual(reason, caught.exception.reason)
        self.assertIn(caught.exception.role, closeout.RetainedReviewValidationError.ROLES)
        self.assertTrue(caught.exception.next_action)
        return caught.exception

    def test_upgrade_historical_finish_repeat_and_unchanged_original_bytes(self):
        run, scope, inventory = self.historical(browser=True)
        original = self.bytes_of(run.root)
        self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded"))
        with self.pinned_fixture(run, inventory):
            first = run.finish("succeeded", historical_review_digests=inventory)
            second = ExactOwnedRun.open(run.root).finish("succeeded", historical_review_digests=inventory)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual("historical_compatibility", first.review_validation["validation"])
        self.assertEqual(closeout.source_identity(self.repo)[1], first.review_validation["source_head"])
        self.assertEqual(original, self.bytes_of(run.root))
        self.assertFalse(closeout.has_preserved_review_evidence(scope.parent.parent))

    def test_prior_retention_and_terminal_success_are_mandatory(self):
        run, scope, inventory = self.historical(retained=False)
        with self.pinned_fixture(run, inventory):
            self.assert_reason("historical_retention_required", lambda: run.finish("succeeded", retain_diagnostics=True, historical_review_digests=inventory))
        run.finish("failed", retain_diagnostics=True)
        inventory = self.saved_inventory(run)
        with self.pinned_fixture(run, inventory):
            self.assert_reason("historical_retention_required", lambda: run.finish("failed", historical_review_digests=inventory))

    def test_unknown_fresh_failure_retained_snapshot_cannot_manufacture_authority(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                run, paths = self.make_run("pipeline", "fresh-" + str(legacy).lower(), legacy=legacy)
                if not legacy:
                    lane = json.loads(paths["lane_receipts"].read_text())
                    lane["schema_version"] = 1
                    for row in lane["lanes"]:
                        for key in ("evidence_record_ref", "evidence_history", "transition_refs"):
                            row.pop(key)
                    paths["lane_receipts"].write_text(json.dumps(lane))
                self.assertEqual("incomplete", self.preserve(run, paths)["status"])
                run.finish("failed", retain_diagnostics=True)
                inventory = self.saved_inventory(run)
                self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded", historical_review_digests=inventory))
                self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded"))

    def test_snapshot_file_changes_are_rejected_before_original_contract(self):
        for mutation in ("output", "metadata", "cleanup", "missing", "symlink", "hardlink", "inventory"):
            with self.subTest(mutation=mutation):
                run, scope, inventory = self.historical()
                with self.pinned_fixture(run, inventory):
                    target = scope / "review/raw-lane-outputs.json"
                    if mutation == "output":
                        target.write_text("{}")
                    elif mutation == "metadata":
                        (run.root / ".depot-owned-run.json").write_bytes((run.root / ".depot-owned-run.json").read_bytes() + b" ")
                    elif mutation == "cleanup":
                        cleanup = run.root / "CLEANUP.txt"
                        cleanup.write_text(cleanup.read_text().replace("Reason: succeeded", "Reason: changed"))
                    elif mutation == "missing":
                        target.unlink()
                    elif mutation in ("symlink", "hardlink"):
                        external = self.root / "external.json"
                        external.write_bytes(target.read_bytes())
                        target.unlink()
                        target.symlink_to(external) if mutation == "symlink" else os.link(external, target)
                    else:
                        inventory.write_bytes(inventory.read_bytes() + b" ")
                    reason = {"missing": "missing_evidence", "symlink": "unsafe_path", "hardlink": "unsafe_path", "inventory": "historical_baseline_missing"}.get(mutation, "digest_mismatch")
                    self.assert_reason(reason, lambda: run.finish("succeeded", historical_review_digests=inventory))

    def test_unsafe_cleanup_identity_keeps_its_terminal_category(self):
        for historical in (True, False):
            for kind in ("symlink", "dangling-symlink", "hardlink"):
                with self.subTest(historical=historical, kind=kind):
                    if historical:
                        run, _scope, inventory = self.historical()
                    else:
                        run, paths = self.make_run("pipeline", "cleanup-" + kind)
                        self.assertEqual("complete", self.preserve(run, paths)["status"])
                        run.finish("blocked", retain_diagnostics=True)
                        inventory = self.saved_inventory(run)
                    cleanup = run.root / "CLEANUP.txt"
                    external = self.root / ("cleanup-target-" + str(historical) + kind)
                    external.write_bytes(cleanup.read_bytes())
                    cleanup.unlink()
                    if kind == "hardlink":
                        os.link(external, cleanup)
                    else:
                        cleanup.symlink_to(external)
                        if kind == "dangling-symlink":
                            external.unlink()
                    with self.pinned_fixture(run, inventory):
                        arguments = {"historical_review_digests": inventory} if historical else {}
                        error = self.assert_reason("unsafe_path", lambda: run.finish("succeeded", **arguments))
                        self.assertEqual(3, error.exit_code)
                        self.assertEqual("cleanup-receipt", error.role)
                    self.assertTrue(os.path.lexists(cleanup))
                    if kind != "hardlink":
                        self.assertTrue(cleanup.is_symlink())

    def test_original_contract_still_rejects_bad_digest_scope_coverage_and_browser(self):
        # Pin deliberately invalid SANITIZED snapshots to prove the common
        # contract still checks semantics after inventory continuity succeeds.
        for mutation in ("output", "digest", "run", "repository", "head", "coverage", "browser", "path"):
            with self.subTest(mutation=mutation):
                run, scope, inventory = self.historical(browser=True)
                name = {"output": "raw-lane-outputs", "digest": "review-lane-receipts",
                    "run": "request", "repository": "request", "head": "request",
                    "coverage": "authoritative-receipts", "browser": "authoritative-receipts", "path": "review-lane-receipts"}[mutation]
                target = scope / "review" / (name + ".json")
                doc = json.loads(target.read_text())
                if mutation == "output":
                    doc["outputs"] = []
                elif mutation == "digest":
                    doc["lanes"][0]["raw_output_digest"] = "sha256:" + "0" * 64
                elif mutation == "run":
                    doc["run_id"] = "different"
                elif mutation == "repository":
                    doc["source_repository"] = "github.com/other/repository"
                elif mutation == "head":
                    doc["source_head"] = "a" * 40
                elif mutation == "coverage":
                    doc[1]["completed_lanes"] = []
                elif mutation == "browser":
                    doc[2]["case_ids"] = []
                else:
                    doc["lanes"][0]["evidence_refs"] = ["../escape"]
                target.write_text(json.dumps(doc))
                inventory = self.saved_inventory(run)
                with self.pinned_fixture(run, inventory):
                    self.assert_reason("source_scope_mismatch" if mutation in ("run", "repository", "head") else "corrupt_evidence",
                        lambda: run.finish("succeeded", historical_review_digests=inventory))

    def test_diagnostic_additions_only_outside_saved_scope(self):
        run, scope, inventory = self.historical()
        with self.pinned_fixture(run, inventory):
            (run.root / "diagnostic/terminal-attempt.json").write_text("{}")
            (run.root / "diagnostic/review/terminal-attempt.json").write_text("{}")
            run.finish("succeeded", historical_review_digests=inventory)
            extra = scope / "invented-inspection.json"
            extra.write_text("{}")
            self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded", historical_review_digests=inventory))
            extra.unlink()
            (scope / "invented-inspection").mkdir()
            self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded", historical_review_digests=inventory))
            (scope / "invented-inspection").rmdir()
            outside = self.root / "external"
            outside.write_text("{}")
            os.link(outside, run.root / "diagnostic/hardlink")
            self.assert_reason("unsafe_path", lambda: run.finish("succeeded", historical_review_digests=inventory))

    def test_wrong_owner_identity_rejects_even_matching_snapshot(self):
        run, scope, inventory = self.historical()
        repository, head = closeout.source_identity(self.repo)
        fingerprint = hashlib.sha256(inventory.read_bytes()).hexdigest()
        for identity in (("dm-review", run.run_id, repository, head), (run.workflow, "other", repository, head),
                         (run.workflow, run.run_id, "github.com/other/repo", head), (run.workflow, run.run_id, repository, "a" * 40)):
            with self.subTest(identity=identity), mock.patch.object(closeout, "_HISTORICAL_REVIEW", (fingerprint, *identity)):
                self.assert_reason("source_scope_mismatch", lambda: run.finish("succeeded", historical_review_digests=inventory))

    def test_cli_closed_reasons_exits_safe_artifact_and_next_action(self):
        run, scope, inventory = self.historical()
        def cli(*extra):
            output, errors = [], []
            def emit(value, stream=None):
                (errors if stream is sys.stderr else output).append(value)
            with mock.patch("workflow_kernel.cli._emit", side_effect=emit):
                status = main(["owned-run-finish", "--run-root", str(run.root), "--outcome", "succeeded", *extra])
            return status, "" if not output else json.dumps(output[0]), "" if not errors else json.dumps(errors[0])
        with self.pinned_fixture(run, inventory):
            status, _, error = cli()
            self.assertEqual(3, status)
            self.assertEqual("missing_source_provenance", json.loads(error)["error"]["details"]["reason"])
            status, out, error = cli("--historical-review-digests", str(inventory))
            self.assertEqual(0, status, error)
            self.assertEqual("historical_compatibility", json.loads(out)["review_validation"]["validation"])
            target = scope / "review/raw-lane-outputs.json"
            original = target.read_bytes()
            for mutation, reason, expected_exit in (("missing", "missing_evidence", 3), ("corrupt", "digest_mismatch", 3)):
                target.unlink() if mutation == "missing" else target.write_text("private supplied text")
                status, out, error = cli("--historical-review-digests", str(inventory))
                self.assertEqual(expected_exit, status)
                detail = json.loads(error)["error"]["details"]
                self.assertEqual(reason, detail["reason"])
                self.assertTrue(detail["next_action"])
                self.assertEqual("lane-outputs", detail["artifact_role"])
                self.assertNotIn(str(self.root), error)
                self.assertNotIn("private supplied text", error)
                target.write_bytes(original)
        target.write_text("{")
        status, _, error = cli()
        self.assertEqual(2, status)
        self.assertEqual("corrupt_evidence", json.loads(error)["error"]["details"]["reason"])
        self.assertNotIn(str(self.root), error)

    def test_inventory_paths_and_required_scope_closure_are_fail_closed(self):
        run, scope, inventory = self.historical()
        original = inventory.read_bytes()
        outside = self.root / "outside-inventory"
        outside.write_bytes(original)
        inventory.unlink()
        inventory.symlink_to(outside)
        self.assert_reason("unsafe_path", lambda: run.finish("succeeded", historical_review_digests=inventory))
        inventory.unlink()
        inventory.write_bytes(original)
        mapping = json.loads(original)
        mapping["../outside"] = "0" * 64
        inventory.write_text(json.dumps(mapping))
        with self.pinned_fixture(run, inventory):
            self.assert_reason("unsafe_path", lambda: run.finish("succeeded", historical_review_digests=inventory))
        mapping.pop("../outside")
        mapping.pop((scope / "raw/security.md").relative_to(run.root).as_posix())
        inventory.write_text(json.dumps(mapping))
        with self.pinned_fixture(run, inventory):
            self.assert_reason("historical_baseline_missing", lambda: run.finish("succeeded", historical_review_digests=inventory))

    def test_real_cli_reports_closed_failure_without_supplied_paths(self):
        import subprocess
        from tests import KERNEL_REFERENCES
        run, scope, inventory = self.historical()
        result = subprocess.run([sys.executable, "-m", "workflow_kernel", "owned-run-finish",
            "--run-root", str(run.root), "--outcome", "succeeded",
            "--historical-review-digests", str(inventory)],
            env=dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES)), capture_output=True, text=True)
        self.assertEqual(3, result.returncode)
        error = json.loads(result.stderr)["error"]
        self.assertEqual("historical_baseline_missing", error["details"]["reason"])
        self.assertEqual("retention-inventory", error["details"]["artifact_role"])
        self.assertTrue(error["details"]["next_action"])
        self.assertNotIn(str(self.root), result.stderr)

    def cli_finish(self, root, *extra):
        output, errors = [], []
        def emit(value, stream=None):
            (errors if stream is sys.stderr else output).append(value)
        with mock.patch("workflow_kernel.cli._emit", side_effect=emit):
            status = main(["owned-run-finish", "--run-root", str(root), "--outcome", "succeeded", *extra])
        return status, output, "" if not errors else json.dumps(errors[0])

    def test_missing_retained_lock_is_never_recreated(self):
        run, scope, inventory = self.historical()
        lock = run.root / ".depot-owned-run.lock"
        lock.unlink()
        original = self.bytes_of(run.root)
        with self.pinned_fixture(run, inventory):
            for finish in (lambda: run.finish("succeeded", historical_review_digests=inventory),
                           lambda: run.finish("succeeded")):
                error = self.assert_reason("missing_evidence", finish)
                self.assertEqual("owner-metadata", error.role)
                self.assertFalse(os.path.lexists(lock))
            status, _, error = self.cli_finish(run.root, "--historical-review-digests", str(inventory))
        self.assertEqual(3, status)
        detail = json.loads(error)["error"]["details"]
        self.assertEqual(("missing_evidence", "owner-metadata"), (detail["reason"], detail["artifact_role"]))
        self.assertTrue(detail["next_action"])
        self.assertNotIn(str(self.root), error)
        self.assertFalse(os.path.lexists(lock))
        self.assertEqual(original, self.bytes_of(run.root))

    def test_unsafe_retained_lock_reports_closed_reason(self):
        for mutation in ("symlink", "hardlink"):
            with self.subTest(mutation=mutation):
                run, scope, inventory = self.historical()
                lock = run.root / ".depot-owned-run.lock"
                external = self.root / ("external-" + mutation + ".lock")
                external.write_bytes(b"")
                lock.unlink()
                lock.symlink_to(external) if mutation == "symlink" else os.link(external, lock)
                original = self.bytes_of(run.root)
                with self.pinned_fixture(run, inventory):
                    error = self.assert_reason("unsafe_path",
                        lambda: run.finish("succeeded", historical_review_digests=inventory))
                    self.assertEqual("owner-metadata", error.role)
                    status, _, error = self.cli_finish(run.root, "--historical-review-digests", str(inventory))
                self.assertEqual(3, status)
                detail = json.loads(error)["error"]["details"]
                self.assertEqual(("unsafe_path", "owner-metadata"), (detail["reason"], detail["artifact_role"]))
                self.assertTrue(detail["next_action"])
                self.assertNotIn(str(self.root), error)
                self.assertEqual(original, self.bytes_of(run.root))
                self.assertEqual(b"", external.read_bytes())

    def test_retained_lock_contention_remains_a_state_conflict(self):
        from workflow_kernel._files import LockContentionError, LockHandle, bind_durable_path
        run, scope, inventory = self.historical()
        held = LockHandle.acquire_bound(bind_durable_path(run.root / ".depot-owned-run.lock"), create=False)
        try:
            with self.pinned_fixture(run, inventory), self.assertRaises(LockContentionError):
                run.finish("succeeded", historical_review_digests=inventory)
        finally:
            held.release()
        with self.pinned_fixture(run, inventory):
            self.assertEqual("retained", run.finish("succeeded", historical_review_digests=inventory).status)

    def test_cli_owner_metadata_missing_corrupt_and_unsafe_are_distinct(self):
        cases = (("missing", "missing_evidence", 3), ("json", "corrupt_evidence", 2),
                 ("schema", "corrupt_evidence", 2), ("unhashable", "corrupt_evidence", 2),
                 ("symlink", "unsafe_path", 3), ("hardlink", "unsafe_path", 3))
        for mutation, reason, expected_exit in cases:
            with self.subTest(mutation=mutation):
                run, scope, inventory = self.historical()
                metadata = run.root / ".depot-owned-run.json"
                value = json.loads(metadata.read_text())
                if mutation == "missing":
                    metadata.unlink()
                elif mutation == "json":
                    metadata.write_text("{")
                elif mutation == "schema":
                    value["version"] = 99
                    metadata.write_text(json.dumps(value))
                elif mutation == "unhashable":
                    value["resources"][0]["kind"] = ["diagnostic"]
                    metadata.write_text(json.dumps(value))
                else:
                    external = self.root / ("metadata-" + mutation + ".json")
                    external.write_bytes(metadata.read_bytes())
                    metadata.unlink()
                    metadata.symlink_to(external) if mutation == "symlink" else os.link(external, metadata)
                original = self.bytes_of(run.root)
                status, output, error = self.cli_finish(run.root, "--historical-review-digests", str(inventory))
                self.assertEqual(expected_exit, status)
                self.assertEqual([], output)
                detail = json.loads(error)["error"]["details"]
                self.assertEqual((reason, "owner-metadata"), (detail["reason"], detail["artifact_role"]))
                self.assertTrue(detail["next_action"])
                self.assertNotIn(str(self.root), error)
                self.assertEqual(original, self.bytes_of(run.root))
                self.assertTrue(os.path.lexists(run.root / ".depot-owned-run.lock"))

    def test_ordinary_lock_creation_defaults_are_unchanged(self):
        from workflow_kernel._files import LockHandle, bind_durable_path
        path = self.root / "ordinary.lock"
        with self.assertRaises(FileNotFoundError):
            LockHandle.acquire_bound(bind_durable_path(path), create=False)
        self.assertFalse(os.path.lexists(path))
        LockHandle.acquire_bound(bind_durable_path(path)).release()
        self.assertTrue(path.is_file())
        run = ExactOwnedRun.start("ordinary", "lock-default", base=self.root / "runs")
        (run.root / ".depot-owned-run.lock").unlink()
        self.assertEqual("removed", run.finish("succeeded").status)
        self.assertFalse(run.root.exists())

    def test_current_source_bound_run_and_boolean_wrapper_bind_run_id(self):
        run, paths = self.make_run()
        result = self.preserve(run, paths)
        diagnostic = Path(result["recovery_path"])
        self.assertTrue(closeout.has_preserved_review_evidence(diagnostic))
        scope = Path(result["evidence_path"])
        request = json.loads((scope / "review/request.json").read_text())
        request["run_id"] = "other"
        (scope / "review/request.json").write_text(json.dumps(request))
        self.assert_reason("source_scope_mismatch", lambda: run.finish("succeeded", retain_diagnostics=True))
