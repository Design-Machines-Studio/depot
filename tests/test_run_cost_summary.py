"""Tests for the run-cost-summary artifact."""

import json
import unittest

from workflow_kernel.cost_summary import (
    COST_SUMMARY_SCHEMA_VERSION,
    build_run_cost_summary,
    compute_cost_summary_digest,
    validate_run_cost_summary,
    _remove_volatile,
)
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.redaction import sanitize_durable_payload

FIXTURES = __import__("pathlib").Path(__file__).parent / "fixtures" / "receipts"


def _usage_receipt(sequence, attempt, **measurements):
    receipt = {
        "run_id": "economics-1", "sequence": sequence,
        "stage": "attempt_usage", "status": "observed",
        "node_id": "chunk-a", "chunk_id": "chunk-a",
        "occurred_at": f"2026-07-14T00:0{sequence}:00Z",
        "authoritative_receipt": f"receipts/attempt-{sequence}.json",
        "host": "codex", "provider": "openai", "model": "gpt-5.6-sol",
        "requested_provider": "openrouter", "attempted_provider": "openai",
        "implemented_by": "codex", "attempt": attempt,
        "duration_seconds": 1.0,
        "usage_scope": "attempt", "measurement_source": "provider_receipt",
        "usage_estimated": False,
    }
    receipt.update(measurements)
    return receipt


class RunCostSummaryTests(unittest.TestCase):
    def _fixture_events(self):
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        return translate_pipeline_receipts(receipts)

    # -- 1. Schema validation and unknown-version rejection --

    def test_emitted_summary_passes_validation(self):
        summary = build_run_cost_summary(self._fixture_events())
        validate_run_cost_summary(summary)  # must not raise

    def test_unknown_schema_version_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["schema_version"] = 999
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_missing_top_level_field_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        del bad["totals"]
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_schema_version_is_one(self):
        summary = build_run_cost_summary(self._fixture_events())
        self.assertEqual(summary["schema_version"], COST_SUMMARY_SCHEMA_VERSION)

    # -- 2. Byte-stable replay --

    def test_byte_stable_replay_excluding_volatile_fields(self):
        events = self._fixture_events()
        s1 = build_run_cost_summary(events, repository_commit="abc123")
        s2 = build_run_cost_summary(events, repository_commit="abc123")
        # emitted_at must differ (wall-clock)
        self.assertNotEqual(
            s1["invocation"]["emitted_at"], s2["invocation"]["emitted_at"],
        )
        # After removing volatile fields, bytes must be identical
        nv1 = _remove_volatile(s1)
        nv2 = _remove_volatile(s2)
        b1 = json.dumps(nv1, sort_keys=True, separators=(",", ":"))
        b2 = json.dumps(nv2, sort_keys=True, separators=(",", ":"))
        self.assertEqual(b1, b2)

    def test_digest_is_stable_across_emissions(self):
        events = self._fixture_events()
        s1 = sanitize_durable_payload(build_run_cost_summary(events))
        s2 = sanitize_durable_payload(build_run_cost_summary(events))
        s1["digest"] = compute_cost_summary_digest(s1)
        s2["digest"] = compute_cost_summary_digest(s2)
        self.assertEqual(s1["digest"], s2["digest"])

    def test_sanitized_output_is_byte_stable(self):
        events = self._fixture_events()
        s1 = sanitize_durable_payload(build_run_cost_summary(events))
        s2 = sanitize_durable_payload(build_run_cost_summary(events))
        s1["digest"] = compute_cost_summary_digest(s1)
        s2["digest"] = compute_cost_summary_digest(s2)
        nv1 = _remove_volatile(s1)
        nv2 = _remove_volatile(s2)
        self.assertEqual(
            json.dumps(nv1, sort_keys=True, separators=(",", ":")),
            json.dumps(nv2, sort_keys=True, separators=(",", ":")),
        )

    # -- 3. Deterministic row ordering and path normalization --

    def test_phases_are_sorted_by_name(self):
        summary = build_run_cost_summary(self._fixture_events())
        names = [row["phase"] for row in summary["phases"]]
        self.assertEqual(names, sorted(names))

    def test_lanes_are_sorted_by_lane_chunk_attempt(self):
        receipts = [
            _usage_receipt(0, 1, usage_count=10, reviewer="security", lane="security"),
            _usage_receipt(1, 1, usage_count=20, reviewer="architecture", lane="architecture"),
            _usage_receipt(2, 2, usage_count=30, reviewer="security", lane="security"),
        ]
        events = translate_pipeline_receipts(receipts)
        summary = build_run_cost_summary(events)
        keys = [
            (row["lane"], row["chunk_id"] or "", row["attempt"] or 0)
            for row in summary["lanes"]
        ]
        self.assertEqual(keys, sorted(keys))

    def test_output_uses_sorted_keys(self):
        summary = build_run_cost_summary(self._fixture_events())
        text = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        # Verify the JSON is deterministic by re-parsing and re-serializing
        reparsed = json.loads(text)
        self.assertEqual(
            json.dumps(reparsed, sort_keys=True, separators=(",", ":")), text,
        )

    # -- 4. Redaction of sensitive values --

    def test_secret_shaped_model_is_redacted(self):
        receipts = [
            _usage_receipt(0, 1, usage_count=10, cost_usd=0.1,
                           model="sk-test-key-1234567890abcdef"),
        ]
        events = translate_pipeline_receipts(receipts)
        summary = build_run_cost_summary(events)
        sanitized = sanitize_durable_payload(summary)
        output = json.dumps(sanitized, sort_keys=True)
        self.assertNotIn("sk-test-key-1234567890abcdef", output)
        self.assertTrue(
            sanitized["lanes"][0]["model"].startswith("value-sha256:"),
            "secret-shaped model must be redacted to a value digest",
        )

    # -- 5. Partial-coverage runs report unavailable provenance --

    def test_phases_without_usage_report_unavailable(self):
        summary = build_run_cost_summary(self._fixture_events())
        for row in summary["phases"]:
            if row["usage_count"] is None:
                self.assertEqual(row["measurement_source"], "unavailable")

    def test_partial_coverage_does_not_zero_fill(self):
        # The pipeline-claude fixture has no attempt_usage events.
        summary = build_run_cost_summary(self._fixture_events())
        for row in summary["phases"]:
            if row["measurement_source"] == "unavailable":
                for field in (
                    "usage_count", "input_usage_count", "output_usage_count",
                    "cache_read_usage_count", "cache_write_usage_count",
                    "reasoning_usage_count",
                ):
                    self.assertIsNone(row[field])
        self.assertGreater(summary["measurement_coverage"]["usage"]["missing"], 0)

    def test_lanes_without_usage_report_unavailable(self):
        # Construct events directly to test a lane with usage_scope='attempt'
        # but without measurement_source or USAGE_FIELDS.
        from workflow_kernel.schema import WorkflowEvent

        events = (
            WorkflowEvent(
                1, 0, "partial-1", "chunk-a", "evidence.recorded",
                "2026-07-14T00:00:00Z",
                {
                    "stage": "attempt_usage", "status": "observed",
                    "chunk_id": "chunk-a", "attempt": 1,
                    "duration_seconds": 2.0,
                    "usage_scope": "attempt",
                    "host": "codex", "provider": "openai",
                    "model": "gpt-5.6-sol",
                    "requested_provider": "openrouter",
                    "attempted_provider": "openai",
                    "implemented_by": "codex",
                },
            ),
            WorkflowEvent(
                1, 1, "partial-1", None, "evidence.recorded",
                "2026-07-14T00:01:00Z",
                {"stage": "run_summary", "status": "succeeded"},
            ),
        )
        summary = build_run_cost_summary(events)
        self.assertGreater(len(summary["lanes"]), 0)
        for lane in summary["lanes"]:
            self.assertEqual(lane["measurement_source"], "unavailable")
            for field in ("usage_count", "input_usage_count", "cost_usd"):
                self.assertIsNone(lane[field])

    # -- 6. CLI surface --

    def test_cli_command_emits_valid_summary(self):
        import os
        import sys
        import tempfile

        events = self._fixture_events()
        # Write a temporary receipts file
        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            self.assertTrue(os.path.exists(output_path))
            with open(output_path) as f:
                summary = json.load(f)
            validate_run_cost_summary(summary)
            self.assertEqual(summary["schema_version"], 1)
            self.assertIsNotNone(summary["digest"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 7. Empty events and edge cases (sprint contract addendum) --

    def test_empty_events_produce_valid_summary(self):
        summary = build_run_cost_summary(())
        validate_run_cost_summary(summary)
        self.assertEqual(summary["phases"], [])
        self.assertEqual(summary["lanes"], [])
        self.assertIsNone(summary["totals"]["usage_count"])
        self.assertIsNone(summary["totals"]["cost_usd"])

    # -- 8. Round-trip conformance: emitted output validates --

    def test_cli_output_round_trips_through_validator(self):
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(output_path) as f:
                summary = json.load(f)
            # Round-trip: the emitted file must pass validation
            validate_run_cost_summary(summary)
            # Digest is recomputed from the emitted (sanitized) content
            recomputed = compute_cost_summary_digest(summary)
            self.assertEqual(recomputed, summary["digest"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 9. CLI negative case: malformed events --

    def test_cli_malformed_events_exits_nonzero(self):
        import os
        import sys
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            f.write("{not valid json}")
            events_path = f.name
        output_path = events_path + ".summary.json"
        old_argv = sys.argv
        try:
            from workflow_kernel.cli import main
            exit_code = main([
                "run-cost-summary",
                "--events", events_path,
                "--output", output_path,
            ])
            self.assertNotEqual(exit_code, 0)
            self.assertFalse(os.path.exists(output_path))
        finally:
            sys.argv = old_argv
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 10. Digest verification with redaction active (CLI end-to-end) --

    def test_cli_digest_verifies_after_redaction_with_secret(self):
        """The CLI must emit a digest that independently verifies against the
        redacted emitted file.  A secret-shaped model must not appear in the
        output.  This replaces the tautological in-process version that set
        and recomputed the digest from the same object."""
        import os
        import sys
        import tempfile

        receipts = [
            _usage_receipt(0, 1, usage_count=10, cost_usd=0.1,
                           model="sk-test-key-1234567890abcdef"),
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(output_path) as f:
                emitted = json.load(f)
            output_text = json.dumps(emitted, sort_keys=True)
            self.assertNotIn("sk-test-key-1234567890abcdef", output_text)
            recomputed = compute_cost_summary_digest(emitted)
            self.assertEqual(recomputed, emitted["digest"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 11. CLI --repository-commit and --dirty-state provenance --

    def test_cli_passes_repository_commit_and_dirty_state(self):
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
                "--repository-commit", "abc123def456",
                "--dirty-state",
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(output_path) as f:
                summary = json.load(f)
            identity = summary["run_identity"]
            self.assertEqual(identity["repository_commit"], "abc123def456")
            self.assertTrue(identity["dirty_state"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_cli_receipt_line_records_the_artifact_after_writing_it(self):
        """The success half of the emission obligation is deterministic.

        Before this flag, whether a run receipt gained its cost-summary line
        depended on a model reading prose and acting on it. Now the same
        command that writes the artifact records that it did -- and only after
        the write succeeded, so a receipt can never cite an artifact that is
        not there.
        """
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        receipt_path = events_path + ".receipt.md"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
                "--receipt-line", receipt_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            self.assertTrue(os.path.exists(output_path))
            with open(receipt_path) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines, ["run-cost-summary: " + output_path])
        finally:
            for path in (events_path, output_path, receipt_path):
                if os.path.exists(path):
                    os.unlink(path)

    def test_cli_receipt_line_appends_rather_than_truncating(self):
        """A run receipt is append-only; the flag must not clobber it."""
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        receipt_path = events_path + ".receipt.md"
        with open(receipt_path, "w") as f:
            f.write("# Receipt\nprior line\n")
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
                "--receipt-line", receipt_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(receipt_path) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[:2], ["# Receipt", "prior line"])
            self.assertEqual(lines[-1], "run-cost-summary: " + output_path)
        finally:
            for path in (events_path, output_path, receipt_path):
                if os.path.exists(path):
                    os.unlink(path)

    def test_cli_without_receipt_line_writes_no_receipt(self):
        """The flag is opt-in; omitting it leaves the old behavior exactly."""
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            self.assertTrue(os.path.exists(output_path))
        finally:
            for path in (events_path, output_path):
                if os.path.exists(path):
                    os.unlink(path)

    def test_cli_defaults_repository_commit_null_dirty_false(self):
        import os
        import sys
        import tempfile

        receipts = json.loads((FIXTURES / "pipeline-claude.json").read_text())
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False,
        ) as f:
            json.dump(receipts, f)
            events_path = f.name
        output_path = events_path + ".summary.json"
        try:
            old_argv = sys.argv
            sys.argv = [
                "workflow_kernel", "run-cost-summary",
                "--events", events_path, "--output", output_path,
            ]
            from workflow_kernel.cli import main
            try:
                main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            finally:
                sys.argv = old_argv
            with open(output_path) as f:
                summary = json.load(f)
            identity = summary["run_identity"]
            self.assertIsNone(identity["repository_commit"])
            self.assertFalse(identity["dirty_state"])
        finally:
            os.unlink(events_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    # -- 12. build_run_cost_summary leaves digest None (CLI finalizes) --

    def test_every_committed_cost_baseline_validates(self):
        """Committed baselines are the reference for phase exit gates.

        Adding `input_bytes` to the row and totals contracts silently
        invalidated the baseline this branch committed: it declared
        schema_version 1 and had no such field, and nothing checked. A
        reference artifact that its own validator rejects is not a reference.
        Every file in docs/cost-baselines/ is now validated on every run.
        """
        import pathlib
        directory = pathlib.Path(__file__).parent.parent / "docs" / "cost-baselines"
        baselines = sorted(directory.glob("*.json"))
        self.assertTrue(baselines, "no committed cost baselines found")
        for path in baselines:
            with self.subTest(baseline=path.name):
                validate_run_cost_summary(json.loads(path.read_text()))

    def test_post_v1_fields_are_optional_but_emitted(self):
        """New emissions carry input_bytes; older artifacts without it stay
        valid. Requiring it would change what schema_version 1 means rather
        than add to it."""
        summary = build_run_cost_summary(self._fixture_events())
        self.assertIn("input_bytes", summary["totals"])
        stripped = json.loads(json.dumps(summary))
        del stripped["totals"]["input_bytes"]
        del stripped["totals"]["usage_provenance"]["input_bytes"]
        for row in stripped["phases"] + stripped["lanes"]:
            row.pop("input_bytes", None)
        stripped["digest"] = compute_cost_summary_digest(stripped)
        validate_run_cost_summary(stripped)

    # ---- emit-cost-summary: the whole obligation as one transaction ----

    def _emit(self, **paths):
        import sys
        argv = ["workflow_kernel", "emit-cost-summary"]
        for flag, value in paths.items():
            argv += ["--" + flag.replace("_", "-"), str(value)]
        old = sys.argv
        sys.argv = argv
        try:
            from workflow_kernel.cli import main
            try:
                return main() or 0
            except SystemExit as exc:
                return exc.code or 0
        finally:
            sys.argv = old

    def _events_file(self, directory):
        import os
        path = os.path.join(directory, "authoritative-receipts.json")
        with open(path, "w") as f:
            json.dump(json.loads((FIXTURES / "pipeline-claude.json").read_text()), f)
        return path

    def test_emit_writes_artifact_and_records_exactly_one_line(self):
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        try:
            events = self._events_file(directory)
            output = os.path.join(directory, "run-cost-summary.json")
            receipt = os.path.join(directory, "run-receipt.md")
            self.assertEqual(
                self._emit(events=events, output=output, receipt=receipt), 0,
            )
            validate_run_cost_summary(json.load(open(output)))
            with open(receipt) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines, ["run-cost-summary: " + output])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_emit_clears_a_stale_artifact_before_writing(self):
        """A stale file at the fixed path must never be recorded as this run's."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        try:
            events = self._events_file(directory)
            output = os.path.join(directory, "run-cost-summary.json")
            receipt = os.path.join(directory, "run-receipt.md")
            with open(output, "w") as f:
                f.write('{"stale": true}')
            self._emit(events=events, output=output, receipt=receipt)
            summary = json.load(open(output))
            self.assertNotIn("stale", summary)
            validate_run_cost_summary(summary)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_emit_records_a_skip_line_and_still_exits_zero_on_failure(self):
        """Measurement failure is never workflow failure -- and it is never
        silence either. The command records its own skip reason."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        try:
            events = os.path.join(directory, "not-an-array.json")
            with open(events, "w") as f:
                f.write('{"not": "an array"}')
            output = os.path.join(directory, "run-cost-summary.json")
            receipt = os.path.join(directory, "run-receipt.md")
            self.assertEqual(
                self._emit(events=events, output=output, receipt=receipt), 0,
            )
            self.assertFalse(os.path.exists(output))
            with open(receipt) as f:
                lines = f.read().splitlines()
            self.assertEqual(lines, ["run-cost-summary: skipped (summary-failed)"])
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_emit_never_records_both_an_artifact_and_a_skip(self):
        """The retired shell chain could append a skip line after appending the
        artifact line. One command, one line, always."""
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        try:
            events = self._events_file(directory)
            output = os.path.join(directory, "run-cost-summary.json")
            receipt = os.path.join(directory, "run-receipt.md")
            self._emit(events=events, output=output, receipt=receipt)
            self._emit(events=events, output=output, receipt=receipt)
            with open(receipt) as f:
                lines = [l for l in f.read().splitlines() if l.strip()]
            self.assertEqual(len(lines), 2)
            for line in lines:
                self.assertTrue(line.startswith("run-cost-summary: "))
                self.assertNotIn("skipped", line)
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_emit_refuses_a_symlinked_receipt(self):
        import os
        import shutil
        import tempfile

        directory = tempfile.mkdtemp()
        try:
            events = self._events_file(directory)
            output = os.path.join(directory, "run-cost-summary.json")
            real = os.path.join(directory, "elsewhere.md")
            open(real, "w").close()
            receipt = os.path.join(directory, "run-receipt.md")
            os.symlink(real, receipt)
            self._emit(events=events, output=output, receipt=receipt)
            # Nothing is written through the symlink, and no artifact is
            # produced. A symlinked receipt is an operator misconfiguration the
            # command refuses; it cannot record its own refusal anywhere safe,
            # so the refusal goes to stderr and the receipt stays untouched.
            self.assertFalse(os.path.exists(output))
            with open(real) as f:
                self.assertEqual(f.read(), "")
        finally:
            shutil.rmtree(directory, ignore_errors=True)

    def test_build_leaves_digest_none(self):
        summary = build_run_cost_summary(self._fixture_events())
        self.assertIsNone(summary["digest"])

    # -- 13. Validator rejects malformed artifacts (strict schema) --

    def test_extra_top_level_field_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["extra_field"] = True
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_extra_phase_row_field_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        if not summary["phases"]:
            self.skipTest("no phases in fixture")
        bad = json.loads(json.dumps(summary))
        bad["phases"][0]["extra_field"] = True
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_malformed_usage_provenance_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["totals"]["usage_provenance"] = "garbage"
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_coverage_non_integer_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["measurement_coverage"]["usage"]["expected"] = "five"
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_coverage_boolean_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["measurement_coverage"]["cost"]["missing"] = True
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_bad_digest_type_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["digest"] = 123
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)

    def test_forged_volatile_fields_is_rejected(self):
        summary = build_run_cost_summary(self._fixture_events())
        bad = json.loads(json.dumps(summary))
        bad["volatile_fields"] = ["invocation.emitted_at", "totals.cost_usd"]
        with self.assertRaises(ValueError):
            validate_run_cost_summary(bad)


if __name__ == "__main__":
    unittest.main()
