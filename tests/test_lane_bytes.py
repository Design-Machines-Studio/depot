"""Tests for the deterministic lane input-bytes calculator and CLI command."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from workflow_kernel import cli
from workflow_kernel._usage_identity import (
    AttemptContext,
    ProviderAttribution,
)
from workflow_kernel.cost_summary import (
    build_run_cost_summary,
    validate_run_cost_summary,
)
from workflow_kernel.lane_bytes import (
    MEASUREMENT_SOURCE,
    estimate_lane_input_bytes,
    measure_lane_inputs,
)
from workflow_kernel.metrics import (
    MetricsAggregator,
    _attempt_identity,
    _coverage_assignments,
    _scoped_totals,
)
from workflow_kernel.openrouter_usage import translate_openrouter_receipt
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts

FIXTURES = Path(__file__).parent / "fixtures" / "lane-bytes"
AGENT_FIXTURE = FIXTURES / "agent-definition.md"
DIFF_FIXTURE = FIXTURES / "diff.patch"
BOILERPLATE_FIXTURE = FIXTURES / "boilerplate.md"

USAGE_KEYS = {
    "usage_count", "input_usage_count", "output_usage_count",
    "cache_read_usage_count", "cache_write_usage_count",
    "reasoning_usage_count", "cost_usd",
}
BASE_KEYS = {
    "usage_scope", "measurement_source", "usage_estimated", "attempt",
    "chunk_id", "node_id", "duration_seconds", "lane",
    "requested_provider", "attempted_provider", "implemented_by",
    "provider", "model", "host",
}
CONTEXT = AttemptContext(
    lane="dm-review", chunk_id="chunk-a", node_id="chunk-a",
    attempt=1, host="claude-code", duration_seconds=12.5,
)
ATTRIBUTION = ProviderAttribution(
    requested_provider="anthropic", attempted_provider="anthropic",
    implemented_by="claude-code", provider="anthropic",
    model="claude-opus-4",
)
# Splatted at every call site, so the carrier swap stays a one-line change.
IDENTITY = {"context": CONTEXT, "attribution": ATTRIBUTION}
# The flat spelling, for assertions that walk the identity fields and for the
# CLI argv builder -- the command line is still eleven flags.
IDENTITY_FIELDS = dict(
    lane=CONTEXT.lane, chunk_id=CONTEXT.chunk_id, node_id=CONTEXT.node_id,
    attempt=CONTEXT.attempt, host=CONTEXT.host,
    duration_seconds=CONTEXT.duration_seconds,
    requested_provider=ATTRIBUTION.requested_provider,
    attempted_provider=ATTRIBUTION.attempted_provider,
    implemented_by=ATTRIBUTION.implemented_by,
    provider=ATTRIBUTION.provider, model=ATTRIBUTION.model,
)
_CONTEXT_FIELDS = frozenset(
    ("lane", "chunk_id", "node_id", "attempt", "host", "duration_seconds")
)


def _identity(**overrides):
    """Rebuild the identity kwargs with individual fields overridden."""
    import dataclasses

    context_changes = {
        key: value for key, value in overrides.items() if key in _CONTEXT_FIELDS
    }
    attribution_changes = {
        key: value for key, value in overrides.items()
        if key not in _CONTEXT_FIELDS
    }
    return {
        "context": dataclasses.replace(CONTEXT, **context_changes),
        "attribution": dataclasses.replace(ATTRIBUTION, **attribution_changes),
    }
BYTE_ARGS = dict(agent_definition_bytes=100, diff_bytes=50, boilerplate_bytes=25)


def _envelope(payload, sequence=0):
    envelope = {
        "run_id": "lane-bytes-e2e", "sequence": sequence,
        "stage": "attempt_usage", "status": "observed",
        "occurred_at": "2026-08-07T00:00:00Z",
        "authoritative_receipt": "receipts/lane-bytes-%d.json" % sequence,
    }
    envelope.update(payload)
    return envelope


def _invoke(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _cli_args(agent=None, diff=None, boilerplate=(), output=None, **overrides):
    identity = dict(IDENTITY_FIELDS)
    identity.update(overrides)
    argv = [
        "lane-input-bytes",
        "--agent-definition", str(agent if agent is not None else AGENT_FIXTURE),
        "--diff", str(diff if diff is not None else DIFF_FIXTURE),
    ]
    for path in boilerplate:
        argv += ["--boilerplate", str(path)]
    argv += [
        "--lane", identity["lane"],
        "--chunk-id", identity["chunk_id"],
        "--node-id", identity["node_id"],
        "--attempt", str(identity["attempt"]),
        "--host", identity["host"],
        "--duration-seconds", str(identity["duration_seconds"]),
        "--requested-provider", identity["requested_provider"],
        "--attempted-provider", identity["attempted_provider"],
        "--implemented-by", identity["implemented_by"],
        "--provider", identity["provider"],
        "--model", identity["model"],
    ]
    if output is not None:
        argv += ["--output", str(output)]
    return argv


class LaneInputBytesPayloadTests(unittest.TestCase):
    def test_payload_shape_and_byte_sum(self):
        payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        self.assertEqual(payload["usage_scope"], "attempt")
        self.assertEqual(payload["measurement_source"], "estimated_input_bytes")
        self.assertIs(payload["usage_estimated"], True)
        self.assertEqual(payload["input_bytes"], 175)
        for key, value in IDENTITY_FIELDS.items():
            self.assertEqual(payload[key], value)

    def test_exact_key_set_omits_other_counters_and_cost(self):
        payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        self.assertEqual(set(payload), BASE_KEYS | {"input_bytes"})
        for key in USAGE_KEYS - {"input_bytes"}:
            self.assertNotIn(key, payload)
        self.assertTrue(all(value is not None for value in payload.values()))

    def test_zero_bytes_is_a_present_integer(self):
        payload = estimate_lane_input_bytes(
            agent_definition_bytes=0, diff_bytes=0, boilerplate_bytes=0,
            **IDENTITY,
        )
        self.assertIn("input_bytes", payload)
        self.assertEqual(payload["input_bytes"], 0)
        self.assertIs(type(payload["input_bytes"]), int)

    def test_byte_sum_larger_than_two_to_31_stays_exact_int(self):
        total = 2**31 + 7
        payload = estimate_lane_input_bytes(
            agent_definition_bytes=2**31, diff_bytes=7, boilerplate_bytes=0,
            **IDENTITY,
        )
        self.assertEqual(payload["input_bytes"], total)
        self.assertIs(type(payload["input_bytes"]), int)
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        self.assertIn('"input_bytes":' + str(total), encoded)
        self.assertEqual(json.loads(encoded)["input_bytes"], total)

    def test_invalid_byte_counts_rejected(self):
        for bad in (-1, -100, 1.5, "10", True, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    estimate_lane_input_bytes(
                        agent_definition_bytes=bad, diff_bytes=0,
                        boilerplate_bytes=0, **IDENTITY,
                    )
        for bad in (-1, 2.5, False, None):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    estimate_lane_input_bytes(
                        agent_definition_bytes=0, diff_bytes=bad,
                        boilerplate_bytes=0, **IDENTITY,
                    )

    def test_invalid_identity_rejected(self):
        for field in (
            "lane", "chunk_id", "node_id", "host", "requested_provider",
            "attempted_provider", "implemented_by", "provider", "model",
        ):
            for bad in ("", None, 7):
                with self.subTest(field=field, bad=bad):
                    with self.assertRaises(ValueError):
                        estimate_lane_input_bytes(
                            **BYTE_ARGS, **_identity(**{field: bad}),
                        )
        for bad_attempt in (0, -1, 1.5, "1", True, None):
            with self.subTest(attempt=bad_attempt):
                with self.assertRaises(ValueError):
                    estimate_lane_input_bytes(
                        **BYTE_ARGS, **_identity(attempt=bad_attempt),
                    )
        for bad_duration in (-0.1, -1, float("nan"), float("inf"), "1.0", True, None):
            with self.subTest(duration=bad_duration):
                with self.assertRaises(ValueError):
                    estimate_lane_input_bytes(
                        **BYTE_ARGS,
                        **_identity(duration_seconds=bad_duration),
                    )


class MeasureLaneInputsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.agent = root / "agent.md"
        self.diff = root / "diff.patch"
        self.boiler = root / "boilerplate.md"
        self.agent.write_bytes(b"agent definition body\n")
        self.diff.write_bytes(b"diff body\n")
        self.boiler.write_bytes(b"boilerplate body\n")

    def test_sizes_come_from_stat(self):
        expected = sum(
            os.stat(path).st_size
            for path in (self.agent, self.diff, self.boiler)
        )
        payload = measure_lane_inputs(
            self.agent, self.diff, [self.boiler], **IDENTITY,
        )
        self.assertEqual(payload["input_bytes"], expected)
        self.assertEqual(payload["measurement_source"], MEASUREMENT_SOURCE)
        self.assertIs(payload["usage_estimated"], True)
        self.assertEqual(payload["lane"], "dm-review")

    def test_zero_length_files_contribute_present_zero(self):
        empty = Path(self._tmp.name) / "empty.md"
        empty.write_bytes(b"")
        payload = measure_lane_inputs(empty, empty, [], **IDENTITY)
        self.assertIn("input_bytes", payload)
        self.assertEqual(payload["input_bytes"], 0)

    def test_missing_path_names_the_path(self):
        missing = Path(self._tmp.name) / "missing.md"
        with self.assertRaises(ValueError) as caught:
            measure_lane_inputs(missing, self.diff, [], **IDENTITY)
        self.assertIn(str(missing), str(caught.exception))

    def test_directory_as_file_names_the_path(self):
        directory = Path(self._tmp.name)
        with self.assertRaises(ValueError) as caught:
            measure_lane_inputs(directory, self.diff, [], **IDENTITY)
        self.assertIn(str(directory), str(caught.exception))

    def test_dangling_symlink_names_the_path(self):
        link = Path(self._tmp.name) / "dangling.md"
        os.symlink(Path(self._tmp.name) / "no-such-target.md", link)
        with self.assertRaises(ValueError) as caught:
            measure_lane_inputs(link, self.diff, [], **IDENTITY)
        self.assertIn(str(link), str(caught.exception))

    def test_live_symlink_is_followed(self):
        link = Path(self._tmp.name) / "live.md"
        os.symlink(self.agent, link)
        payload = measure_lane_inputs(link, self.diff, [], **IDENTITY)
        self.assertEqual(
            payload["input_bytes"],
            os.stat(self.agent).st_size + os.stat(self.diff).st_size,
        )

    def test_permission_denied_names_the_path(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root bypasses permission checks")
        locked = Path(self._tmp.name) / "locked"
        locked.mkdir()
        secret = locked / "secret.md"
        secret.write_bytes(b"secret\n")
        os.chmod(locked, 0)
        self.addCleanup(os.chmod, locked, 0o700)
        with self.assertRaises(ValueError) as caught:
            measure_lane_inputs(secret, self.diff, [], **IDENTITY)
        self.assertIn(str(secret), str(caught.exception))

    def test_repeated_boilerplate_counts_once_per_occurrence(self):
        boiler_size = os.stat(self.boiler).st_size
        once = measure_lane_inputs(
            self.agent, self.diff, [self.boiler], **IDENTITY,
        )
        twice = measure_lane_inputs(
            self.agent, self.diff, [self.boiler, self.boiler], **IDENTITY,
        )
        self.assertEqual(
            twice["input_bytes"] - once["input_bytes"],
            boiler_size,
        )


class LaneInputBytesCliTests(unittest.TestCase):
    def test_stdout_payload_matches_fixture_byte_sum(self):
        expected = sum(
            os.stat(path).st_size
            for path in (AGENT_FIXTURE, DIFF_FIXTURE, BOILERPLATE_FIXTURE)
        )
        code, out, err = _invoke(_cli_args(boilerplate=[BOILERPLATE_FIXTURE]))
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["input_bytes"], expected)
        self.assertEqual(payload["measurement_source"], "estimated_input_bytes")
        self.assertIs(payload["usage_estimated"], True)
        self.assertEqual(set(payload), BASE_KEYS | {"input_bytes"})

    def test_output_file_carries_full_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "payload.json"
            code, _, err = _invoke(_cli_args(output=destination))
            self.assertEqual(code, 0, err)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            for key, value in IDENTITY_FIELDS.items():
                self.assertEqual(payload[key], value)

    def test_repeated_boilerplate_flag_counts_each_occurrence(self):
        once = _invoke(_cli_args(boilerplate=[BOILERPLATE_FIXTURE]))
        twice = _invoke(_cli_args(
            boilerplate=[BOILERPLATE_FIXTURE, BOILERPLATE_FIXTURE],
        ))
        self.assertEqual(once[0], 0, once[2])
        self.assertEqual(twice[0], 0, twice[2])
        self.assertEqual(
            json.loads(twice[1])["input_bytes"]
            - json.loads(once[1])["input_bytes"],
            os.stat(BOILERPLATE_FIXTURE).st_size,
        )

    def test_output_is_byte_identical_across_invocations(self):
        first = _invoke(_cli_args())
        second = _invoke(_cli_args())
        self.assertEqual(first[0], 0, first[2])
        self.assertEqual(second[0], 0, second[2])
        self.assertEqual(first[1], second[1])

    def test_output_is_byte_identical_for_relative_and_absolute_paths(self):
        absolute = _invoke(_cli_args(boilerplate=[BOILERPLATE_FIXTURE]))
        previous = os.getcwd()
        os.chdir(FIXTURES)
        try:
            relative = _invoke(_cli_args(
                agent="agent-definition.md", diff="diff.patch",
                boilerplate=["boilerplate.md"],
            ))
        finally:
            os.chdir(previous)
        self.assertEqual(absolute[0], 0, absolute[2])
        self.assertEqual(relative[0], 0, relative[2])
        self.assertEqual(absolute[1], relative[1])

    def test_output_is_byte_identical_across_timezones(self):
        baseline = _invoke(_cli_args())
        self.assertEqual(baseline[0], 0, baseline[2])
        for zone in ("UTC", "Pacific/Kiritimati"):
            old = os.environ.get("TZ")
            os.environ["TZ"] = zone
            try:
                rerun = _invoke(_cli_args())
            finally:
                if old is None:
                    del os.environ["TZ"]
                else:
                    os.environ["TZ"] = old
            self.assertEqual(rerun[0], 0, rerun[2])
            self.assertEqual(baseline[1], rerun[1])

    def test_missing_file_exits_nonzero_naming_path_without_traceback(self):
        missing = FIXTURES / "no-such-file.md"
        code, out, err = _invoke(_cli_args(agent=missing))
        self.assertNotEqual(code, 0)
        self.assertIn(str(missing), err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(out, "")

    def test_directory_as_file_exits_nonzero_naming_path(self):
        code, out, err = _invoke(_cli_args(agent=FIXTURES))
        self.assertNotEqual(code, 0)
        self.assertIn(str(FIXTURES), err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(out, "")


class LaneBytesAggregationTests(unittest.TestCase):
    def _events(self, *payloads):
        return list(translate_pipeline_receipts([
            _envelope(payload, sequence=index)
            for index, payload in enumerate(payloads)
        ]))

    def _openrouter_payload(self, lane, prompt_tokens):
        return translate_openrouter_receipt(
            {
                "schemaVersion": 2, "outcome": "success",
                "usage": {"prompt_tokens": prompt_tokens},
            },
            context=AttemptContext(
                lane=lane, chunk_id="chunk-a", node_id="chunk-a",
                attempt=1, host="codex", duration_seconds=9.0,
            ),
        )

    def test_payload_lands_in_attempt_economics(self):
        payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        report = MetricsAggregator().aggregate(self._events(payload))
        self.assertEqual(len(report.attempt_economics), 1)
        row = report.attempt_economics[0]
        self.assertIs(row["usage_estimated"], True)
        self.assertEqual(row["measurement_source"], "estimated_input_bytes")
        self.assertEqual(row["input_bytes"], 175)
        self.assertEqual(row["lane"], "dm-review")
        self.assertEqual(row["chunk_id"], "chunk-a")
        self.assertEqual(row["attempt"], 1)

    def test_payload_surfaces_in_run_cost_summary_lanes(self):
        payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        summary = build_run_cost_summary(self._events(payload))
        self.assertEqual(summary["schema_version"], 1)
        validate_run_cost_summary(summary)
        lanes = [row for row in summary["lanes"] if row.get("lane") == "dm-review"]
        self.assertEqual(len(lanes), 1)
        lane = lanes[0]
        self.assertIs(lane["usage_estimated"], True)
        self.assertEqual(lane["measurement_source"], "estimated_input_bytes")
        self.assertEqual(lane["input_bytes"], 175)
        self.assertEqual(lane["chunk_id"], "chunk-a")
        self.assertEqual(lane["attempt"], 1)

    def test_bytes_and_tokens_never_share_a_field(self):
        """A byte row and a token row are separate columns, not one column.

        This is the invariant behind the unit split: a consumer reading a lane
        row can never receive bytes under a token-named key, so it cannot
        misread a ~4x-inflated number as a token count.
        """
        lane_payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        openrouter_payload = self._openrouter_payload("implementation", 40)
        events = self._events(lane_payload, openrouter_payload)
        report = MetricsAggregator().aggregate(events)
        rows_by_lane = {row["lane"]: row for row in report.attempt_economics}
        byte_row = rows_by_lane["dm-review"]
        token_row = rows_by_lane["implementation"]
        self.assertEqual(byte_row["input_bytes"], 175)
        self.assertNotIn("input_usage_count", byte_row)
        self.assertEqual(token_row["input_usage_count"], 40)
        self.assertNotIn("input_bytes", token_row)
        self.assertIs(byte_row["usage_estimated"], True)
        self.assertIs(token_row["usage_estimated"], False)

    def test_partial_field_coverage_nulls_that_field_total(self):
        """Neither total sums, because neither field covers every attempt.

        Two attempts, each measured in a different unit: `input_bytes` is
        missing from one and `input_usage_count` from the other. A total is
        only honest when every expected attempt contributed to it.
        """
        lane_payload = estimate_lane_input_bytes(**BYTE_ARGS, **IDENTITY)
        openrouter_payload = self._openrouter_payload("implementation", 40)
        events = self._events(lane_payload, openrouter_payload)
        event_rows = [
            (_attempt_identity(event), event.payload) for event in events
        ]
        expected = {identity for identity, _ in event_rows}
        totals, provenance, _, _ = _scoped_totals(event_rows, [], [], expected)
        for field in ("input_bytes", "input_usage_count"):
            with self.subTest(field=field):
                self.assertIsNone(totals[field])
                self.assertIsNone(provenance[field])

    def test_mixed_measurement_sources_null_the_field_total(self):
        """Same field, disagreeing provenance -> no sum.

        Two attempts both report `input_usage_count`, but one is a provider
        receipt and the other is tagged as a failed receipt. Coverage is
        complete, so only the single-source rule can stop the sum -- and it
        must, or an estimate gets promoted to measured truth.
        """
        first = self._openrouter_payload("implementation", 40)
        second = self._openrouter_payload("browser", 60)
        second["measurement_source"] = "estimated_input_bytes"
        second["usage_estimated"] = True
        second.pop("identity_provenance", None)
        events = self._events(first, second)
        event_rows = [
            (_attempt_identity(event), event.payload) for event in events
        ]
        expected = {identity for identity, _ in event_rows}
        totals, provenance, _, _ = _scoped_totals(event_rows, [], [], expected)
        self.assertIsNone(totals["input_usage_count"])
        self.assertIsNone(provenance["input_usage_count"])

    def test_shared_measurement_source_still_sums(self):
        first = self._openrouter_payload("implementation", 40)
        second = self._openrouter_payload("browser", 60)
        events = self._events(first, second)
        event_rows = [
            (_attempt_identity(event), event.payload) for event in events
        ]
        expected = {identity for identity, _ in event_rows}
        totals, provenance, _, _ = _scoped_totals(event_rows, [], [], expected)
        self.assertEqual(totals["input_usage_count"], 100)
        self.assertEqual(provenance["input_usage_count"], "derived_complete_attempts")

    def test_complete_byte_attempts_sum_into_the_input_bytes_total(self):
        """The byte total had row-level and partial-coverage tests but nothing
        asserting that two complete byte-measured attempts actually sum, so a
        regression in the new aggregation branch or its provenance would not
        have been caught."""
        first = estimate_lane_input_bytes(
            agent_definition_bytes=100, diff_bytes=50, boilerplate_bytes=25,
            **_identity(lane="implementation"),
        )
        second = estimate_lane_input_bytes(
            agent_definition_bytes=200, diff_bytes=25, boilerplate_bytes=0,
            **_identity(lane="browser", chunk_id="chunk-b", node_id="chunk-b"),
        )
        self.assertEqual(first["input_bytes"], 175)
        self.assertEqual(second["input_bytes"], 225)
        events = self._events(first, second)
        event_rows = [
            (_attempt_identity(event), event.payload) for event in events
        ]
        expected = {identity for identity, _ in event_rows}
        totals, provenance, _, _ = _scoped_totals(event_rows, [], [], expected)
        self.assertEqual(totals["input_bytes"], 400)
        self.assertEqual(provenance["input_bytes"], "derived_complete_attempts")

    def test_orphan_chunk_identity_is_measured_under_its_own_identity(self):
        payload = estimate_lane_input_bytes(
            **BYTE_ARGS,
            **_identity(chunk_id="chunk-orphan", node_id="chunk-orphan"),
        )
        events = self._events(payload)
        report = MetricsAggregator().aggregate(events)
        rows = [row for row in report.attempt_economics if row["lane"] == "dm-review"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["chunk_id"], "chunk-orphan")
        event_rows = [
            (_attempt_identity(event), event.payload) for event in events
        ]
        expected = {identity for identity, _ in event_rows}
        usage_coverage, assigned = _coverage_assignments(
            expected, event_rows, lambda row: "input_bytes" in row,
        )
        self.assertEqual(usage_coverage["expected"], 1)
        self.assertEqual(usage_coverage["measured"], 1)
        self.assertEqual(usage_coverage["missing"], 0)
        self.assertEqual(usage_coverage["unassigned"], 0)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0][0][1], "chunk-orphan")
        self.assertEqual(assigned[0][0][4], "dm-review")
        cost_coverage, _ = _coverage_assignments(
            expected, event_rows, lambda row: "cost_usd" in row,
        )
        self.assertEqual(cost_coverage["expected"], 1)
        self.assertEqual(cost_coverage["measured"], 0)
        self.assertEqual(cost_coverage["missing"], 1)
        self.assertEqual(cost_coverage["unassigned"], 0)


if __name__ == "__main__":
    unittest.main()
