"""Tests for subscription-rail API-equivalent cost imputation."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from workflow_kernel import cli
from workflow_kernel.cost_summary import (
    build_run_cost_summary,
    compute_cost_summary_digest,
    validate_run_cost_summary,
)
from workflow_kernel.imputed_cost import (
    impute_attempt_cost,
    validate_model_matrix,
)
from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
from workflow_kernel.runtime_resolution import PluginBundle, resolve_plugin_bundle
from workflow_kernel.schema import WorkflowEvent


MATRIX = {
    "schema_version": 1,
    "snapshot_date": "2026-08-03",
    "models": [{
        "slug": "openai/gpt-test",
        "input_usd_per_m": 1.0,
        "output_usd_per_m": 2.0,
        "cache_read_usd_per_m": 0.5,
        "snapshot_date": "2026-08-03",
    }],
    "native_api_equivalent_cost": {
        "schema_version": 1,
        "snapshot_date": "2026-08-03",
        "input_bytes_per_token_estimate": 4,
        "aliases": {},
        "models": [],
    },
}
REAL_MATRIX = json.loads((
    Path(__file__).parents[1] / "plugins/openrouter/skills/openrouter-delegate"
    / "references/model-matrix.json"
).read_text(encoding="utf-8"))


def _native_receipt(*, model="gpt-5.6-terra", cost_usd=None, byte_only=False):
    receipt = {
        "run_id": "native-cost-run", "sequence": 0,
        "stage": "attempt_usage", "status": "observed",
        "node_id": "chunk-1", "chunk_id": "chunk-1", "lane": "implementation",
        "occurred_at": "2026-08-09T00:00:00Z",
        "authoritative_receipt": "receipts/native-cost.json",
        "attempt": 1, "usage_scope": "attempt", "host": "codex",
        "provider": "codex", "model": model,
        "requested_provider": "codex", "attempted_provider": "codex",
        "implemented_by": "codex", "duration_seconds": 1.0,
        "measurement_source": "estimated_input_bytes" if byte_only else "native_token_usage",
        "usage_estimated": byte_only,
    }
    if byte_only:
        receipt["input_bytes"] = 4096
    else:
        receipt.update(input_usage_count=1_000_000, output_usage_count=500_000)
    if cost_usd is not None:
        receipt["cost_usd"] = cost_usd
    return receipt


def _write_bundle(root: Path, matrix=REAL_MATRIX):
    asset = root / "skills/openrouter-delegate/references/model-matrix.json"
    asset.parent.mkdir(parents=True)
    asset.write_text(json.dumps(matrix), encoding="utf-8")
    return PluginBundle(root, "codex", "1.11.0", "highest_compatible_semver")


def _write_installed_asset(home: Path, *, plugin="pricing-provider", version="2.3.0",
                           matrix=REAL_MATRIX):
    root = home / ".codex/plugins/cache/depot" / plugin / version
    asset = root / "references/model-matrix.json"
    asset.parent.mkdir(parents=True)
    asset.write_text(json.dumps(matrix), encoding="utf-8")
    marker = root / ".codex-plugin/plugin.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "name": plugin, "version": version,
    }), encoding="utf-8")
    return asset


def _row(**overrides):
    row = {
        "model": "openai/gpt-test",
        "input_usage_count": 1_000_000,
        "output_usage_count": 500_000,
        "cache_read_usage_count": 250_000,
        "cost_usd": None,
        "measurement_source": "subscription_usage",
        "usage_estimated": False,
    }
    row.update(overrides)
    return row


class ImputedCostTests(unittest.TestCase):
    def test_priced_attempt_gains_cost_and_visible_provenance(self):
        result = impute_attempt_cost(_row(), MATRIX)
        self.assertEqual(result["cost_usd"], 2.125)
        self.assertEqual(
            result["measurement_source"],
            "subscription_usage+imputed_cost(model-matrix@2026-08-03)",
        )
        self.assertTrue(result["usage_estimated"])

    def test_unpriceable_model_is_unchanged(self):
        row = _row(model="missing/model")
        self.assertIs(impute_attempt_cost(row, MATRIX), row)

    def test_absent_native_section_is_an_unchanged_unpriceable_row(self):
        row = _row(
            model="missing/model", implemented_by="codex", provider="codex",
        )
        matrix = {"models": MATRIX["models"]}
        self.assertIs(impute_attempt_cost(row, matrix), row)

    def test_missing_measurement_source_still_gets_visible_provenance(self):
        row = _row()
        del row["measurement_source"]
        result = impute_attempt_cost(row, MATRIX)
        self.assertEqual(result["cost_usd"], 2.125)
        self.assertEqual(
            result["measurement_source"],
            "imputed_cost(model-matrix@2026-08-03)",
        )

    def test_missing_required_price_is_unchanged(self):
        row = _row()
        matrix = {
            "models": [{
                "slug": "openai/gpt-test",
                "output_usd_per_m": 2.0,
                "cache_read_usd_per_m": 0.5,
                "snapshot_date": "2026-08-03",
            }],
        }
        self.assertIs(impute_attempt_cost(row, matrix), row)

    def test_present_cost_is_never_overwritten(self):
        row = _row(cost_usd=4.25)
        self.assertIs(impute_attempt_cost(row, MATRIX), row)
        self.assertEqual(row["cost_usd"], 4.25)

    def test_missing_counters_stay_missing_and_contribute_nothing(self):
        row = _row(output_usage_count=None, cache_read_usage_count=None)
        result = impute_attempt_cost(row, MATRIX)
        self.assertEqual(result["cost_usd"], 1.0)
        self.assertIsNone(result["output_usage_count"])
        self.assertIsNone(result["cache_read_usage_count"])

    def test_output_is_deterministic_and_input_is_not_mutated(self):
        row = _row()
        first = impute_attempt_cost(row, MATRIX)
        second = impute_attempt_cost(row, MATRIX)
        self.assertEqual(first, second)
        self.assertIsNone(row["cost_usd"])
        self.assertFalse(row["usage_estimated"])

    def test_summary_totals_identify_imputed_subscription_equivalent(self):
        event = WorkflowEvent(
            1, 0, "imputation-run", "chunk-1", "evidence.recorded",
            "2026-08-09T00:00:00Z",
            {
                "stage": "attempt_usage", "status": "observed",
                "chunk_id": "chunk-1", "lane": "implementation",
                "attempt": 1, "usage_scope": "attempt",
                "model": "openai/gpt-test", "host": "codex",
                "input_usage_count": 1_000_000,
                "output_usage_count": 500_000,
                "cache_read_usage_count": 250_000,
                "measurement_source": "subscription_usage",
                "usage_estimated": False,
            },
        )
        summary = build_run_cost_summary((event,), matrix=MATRIX)
        validate_run_cost_summary(summary)
        self.assertEqual(summary["totals"]["cost_usd"], 2.125)
        self.assertEqual(
            summary["totals"]["cost_provenance"],
            "imputed_subscription_equivalent",
        )
        self.assertEqual(summary["measurement_coverage"]["cost"]["estimated"], 1)
        self.assertEqual(summary["measurement_coverage"]["cost"]["missing"], 0)

    def test_unpriced_cost_counters_keep_row_and_total_incomplete(self):
        event = WorkflowEvent(
            1, 0, "imputation-run", "chunk-1", "evidence.recorded",
            "2026-08-09T00:00:00Z",
            {
                "stage": "attempt_usage", "status": "observed",
                "chunk_id": "chunk-1", "lane": "implementation",
                "attempt": 1, "usage_scope": "attempt",
                "model": "openai/gpt-test", "host": "codex",
                "input_usage_count": 1_000_000,
                "cache_write_usage_count": 200_000,
                "reasoning_usage_count": 300_000,
                "measurement_source": "subscription_usage",
                "usage_estimated": False,
            },
        )
        summary = build_run_cost_summary((event,), matrix=MATRIX)
        lane = summary["lanes"][0]
        self.assertIsNone(lane["cost_usd"])
        self.assertIn(
            "cost_imputation_excluded(unpriced=cache_write_usage_count"
            "+reasoning_usage_count)",
            lane["measurement_source"],
        )
        self.assertIsNone(summary["totals"]["cost_usd"])
        self.assertIsNone(summary["totals"]["cost_provenance"])
        self.assertEqual(summary["measurement_coverage"]["cost"]["estimated"], 0)
        self.assertEqual(summary["measurement_coverage"]["cost"]["missing"], 1)

    def test_production_shaped_native_codex_alias_is_priceable(self):
        events = translate_pipeline_receipts([_native_receipt()])
        summary = build_run_cost_summary(events, matrix=REAL_MATRIX)
        lane = summary["lanes"][0]
        self.assertEqual(lane["cost_usd"], 4.0)
        self.assertIn(
            "+model_alias(gpt-5.6-terra->openai/gpt-5.6-terra)",
            lane["measurement_source"],
        )

    def test_production_baseline_sol_byte_row_is_priceable(self):
        events = translate_pipeline_receipts([
            _native_receipt(model="gpt-5.6-sol", byte_only=True),
        ])
        lane = build_run_cost_summary(events, matrix=REAL_MATRIX)["lanes"][0]
        self.assertEqual(lane["cost_usd"], 0.00512)
        self.assertIsNone(lane["input_usage_count"])
        self.assertIsNone(lane["output_usage_count"])
        self.assertIsNone(lane["cache_read_usage_count"])
        self.assertTrue(lane["usage_estimated"])
        self.assertIn(
            "+model_alias(gpt-5.6-sol->openai/gpt-5.6-sol)",
            lane["measurement_source"],
        )
        self.assertIn(
            "+estimated_input_tokens(input_bytes/4_bytes_per_token)",
            lane["measurement_source"],
        )

    def test_direct_openrouter_byte_only_row_stays_unpriced(self):
        row = _row(
            input_usage_count=None,
            output_usage_count=None,
            cache_read_usage_count=None,
            input_bytes=4096,
            provider="openrouter",
            implemented_by="openrouter",
        )
        self.assertIs(impute_attempt_cost(row, MATRIX), row)
        self.assertIsNone(row["cost_usd"])

    def test_unsupported_or_unmeasured_native_rows_stay_null(self):
        generic = _native_receipt(model="gpt-5.6", byte_only=True)
        opus = _native_receipt(model="opus", byte_only=True)
        opus.update(provider="claude", implemented_by="claude", host="claude")
        for receipt in (generic, opus):
            with self.subTest(model=receipt["model"], measured="input_bytes" in receipt):
                events = translate_pipeline_receipts([receipt])
                lane = build_run_cost_summary(events, matrix=REAL_MATRIX)["lanes"][0]
                self.assertIsNone(lane["cost_usd"])
        unmeasured = {
            "model": "gpt-5.6-sol", "implemented_by": "codex",
            "provider": "codex", "cost_usd": None,
            "measurement_source": "attempt_unmeasured", "usage_estimated": False,
        }
        self.assertIs(impute_attempt_cost(unmeasured, REAL_MATRIX), unmeasured)

    def test_claude_alias_prices_only_when_matrix_explicitly_maps_it(self):
        matrix = json.loads(json.dumps(MATRIX))
        native = matrix["native_api_equivalent_cost"]
        native["models"] = [{
            **matrix["models"][0],
            "slug": "vendor/opus-api-equivalent",
        }]
        native["aliases"] = {
            "opus": "vendor/opus-api-equivalent",
        }
        row = _row(
            model="opus", implemented_by="claude", provider="claude",
        )
        result = impute_attempt_cost(row, matrix)
        self.assertEqual(result["cost_usd"], 2.125)
        self.assertIn(
            "+model_alias(opus->vendor/opus-api-equivalent)",
            result["measurement_source"],
        )

    def test_matrix_validation_rejects_duplicate_or_mismatched_entries(self):
        validate_model_matrix(MATRIX)
        duplicate = json.loads(json.dumps(MATRIX))
        duplicate["models"].append(dict(duplicate["models"][0]))
        with self.assertRaises(ValueError):
            validate_model_matrix(duplicate)
        drifted = json.loads(json.dumps(MATRIX))
        drifted["models"][0]["snapshot_date"] = "2026-08-04"
        with self.assertRaises(ValueError):
            validate_model_matrix(drifted)

    def test_matrix_validation_rejects_each_trust_boundary(self):
        mutations = {
            "schema": lambda matrix: matrix.update(schema_version=2),
            "snapshot_date": lambda matrix: matrix.update(snapshot_date="2026-8-3"),
            "price": lambda matrix: matrix["models"][0].update(input_usd_per_m=-1),
            "ratio": lambda matrix: matrix["native_api_equivalent_cost"].update(
                input_bytes_per_token_estimate=0,
            ),
            "cross_section_slug": lambda matrix: matrix[
                "native_api_equivalent_cost"
            ]["models"].append(dict(matrix["models"][0])),
            "alias_target": lambda matrix: matrix[
                "native_api_equivalent_cost"
            ]["aliases"].update({"native-name": "missing/model"}),
        }
        for branch, mutate in mutations.items():
            with self.subTest(branch=branch):
                matrix = json.loads(json.dumps(MATRIX))
                mutate(matrix)
                with self.assertRaises(ValueError):
                    validate_model_matrix(matrix)

    def test_matrix_validation_rejects_impossible_calendar_snapshot(self):
        matrix = json.loads(json.dumps(MATRIX))
        matrix["snapshot_date"] = "2026-02-30"
        for model in matrix["models"]:
            model["snapshot_date"] = "2026-02-30"
        native = matrix["native_api_equivalent_cost"]
        native["snapshot_date"] = "2026-02-30"
        for model in native["models"]:
            model["snapshot_date"] = "2026-02-30"
        with self.assertRaises(ValueError):
            validate_model_matrix(matrix)

    def test_matrix_validation_accepts_real_leap_day_snapshot(self):
        matrix = json.loads(json.dumps(MATRIX))
        matrix["snapshot_date"] = "2028-02-29"
        for model in matrix["models"]:
            model["snapshot_date"] = "2028-02-29"
        native = matrix["native_api_equivalent_cost"]
        native["snapshot_date"] = "2028-02-29"
        for model in native["models"]:
            model["snapshot_date"] = "2028-02-29"
        validate_model_matrix(matrix)

    def test_generic_installed_plugin_asset_is_accepted_without_provider_coupling(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            asset = _write_installed_asset(home)
            with mock.patch("workflow_kernel.cli._runtime_home", return_value=home):
                loaded = cli._load_cost_imputation_matrix(str(asset))
        self.assertEqual(loaded, REAL_MATRIX)

    def test_generic_bundle_command_emits_caller_bindable_asset_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "pricing-provider" / "2.3.0"
            asset = root / "references/model-matrix.json"
            asset.parent.mkdir(parents=True)
            asset.write_text(json.dumps(REAL_MATRIX), encoding="utf-8")
            bundle = PluginBundle(
                root, "codex", "2.3.0", "highest_compatible_semver",
            )
            stdout = io.StringIO()
            with mock.patch(
                "workflow_kernel.cli.resolve_plugin_bundle", return_value=bundle,
            ) as resolver, contextlib.redirect_stdout(stdout):
                result = cli.main([
                    "resolve-plugin-asset", "--plugin", "pricing-provider",
                    "--asset", "references/model-matrix.json",
                    "--minimum-version", "2.0.0",
                ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), str(asset.resolve()) + "\n")
        resolver.assert_called_once_with(
            "pricing-provider", ["references/model-matrix.json"],
            active_host=None, minimum_version="2.0.0",
        )

    def test_no_matrix_cli_matches_frozen_pre_imputation_oracle(self):
        oracle = json.loads((
            Path(__file__).parent / "fixtures/run-cost-summary-no-matrix-v1.json"
        ).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.json"
            events.write_text(
                json.dumps([_native_receipt(model="gpt-5.6-sol", byte_only=True)]),
                encoding="utf-8",
            )
            output = root / "summary.json"
            self.assertEqual(cli.main([
                "run-cost-summary", "--events", str(events),
                "--output", str(output),
            ]), 0)
            emitted = json.loads(output.read_text(encoding="utf-8"))
            del emitted["invocation"]["emitted_at"]
        self.assertEqual(emitted, oracle)

    def test_empty_matrix_selector_is_expected_absence_without_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = root / "events.json"
            events.write_text(json.dumps([_native_receipt()]), encoding="utf-8")
            for command in ("run-cost-summary", "emit-cost-summary"):
                output = root / (command + ".json")
                argv = [
                    command, "--events", str(events), "--output", str(output),
                    "--matrix", "",
                ]
                if command == "emit-cost-summary":
                    argv += ["--receipt", str(root / "receipt.md")]
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(cli.main(argv), 0)
                self.assertEqual(stderr.getvalue(), "")
                self.assertIsNone(
                    json.loads(output.read_text(encoding="utf-8"))["lanes"][0]["cost_usd"],
                )

    def test_both_cli_commands_use_installed_matrix_and_recompute_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = _write_installed_asset(root)
            events = root / "events.json"
            events.write_text(json.dumps([_native_receipt()]), encoding="utf-8")
            for command in ("run-cost-summary", "emit-cost-summary"):
                output = root / (command + ".json")
                argv = [
                    command, "--events", str(events), "--output", str(output),
                    "--matrix", str(asset),
                ]
                if command == "emit-cost-summary":
                    argv += ["--receipt", str(root / "receipt.md")]
                stdout, stderr = io.StringIO(), io.StringIO()
                with mock.patch(
                    "workflow_kernel.cli._runtime_home", return_value=root,
                ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(cli.main(argv), 0)
                self.assertEqual(stderr.getvalue(), "")
                summary = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(summary["lanes"][0]["cost_usd"], 4.0)
                self.assertEqual(summary["digest"], compute_cost_summary_digest(summary))

    def test_both_cli_commands_skip_unreadable_matrix_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing_asset = (
                root / ".codex/plugins/cache/depot/pricing-provider/2.3.0"
                / "references/model-matrix.json"
            )
            events = root / "events.json"
            events.write_text(json.dumps([_native_receipt()]), encoding="utf-8")
            for command in ("run-cost-summary", "emit-cost-summary"):
                output = root / (command + ".json")
                argv = [
                    command, "--events", str(events), "--output", str(output),
                    "--matrix", str(missing_asset),
                ]
                if command == "emit-cost-summary":
                    argv += ["--receipt", str(root / "receipt.md")]
                stderr = io.StringIO()
                with mock.patch(
                    "workflow_kernel.cli._runtime_home", return_value=root,
                ), contextlib.redirect_stderr(stderr):
                    self.assertEqual(cli.main(argv), 0)
                self.assertEqual(stderr.getvalue().count("skipping imputation"), 1)
                summary = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsNone(summary["lanes"][0]["cost_usd"])

    def test_arbitrary_matrix_path_is_not_pricing_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hostile = root / "hostile.json"
            hostile.write_text(json.dumps(REAL_MATRIX), encoding="utf-8")
            events = root / "events.json"
            events.write_text(json.dumps([_native_receipt()]), encoding="utf-8")
            output = root / "summary.json"
            stderr = io.StringIO()
            with mock.patch(
                "workflow_kernel.cli._runtime_home", return_value=root,
            ), contextlib.redirect_stderr(stderr):
                self.assertEqual(cli.main([
                    "run-cost-summary", "--events", str(events),
                    "--output", str(output), "--matrix", str(hostile),
                ]), 0)
            self.assertEqual(stderr.getvalue().count("skipping imputation"), 1)
            self.assertIsNone(
                json.loads(output.read_text(encoding="utf-8"))["lanes"][0]["cost_usd"],
            )

    def test_invalid_trusted_matrix_content_skips_imputation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = json.loads(json.dumps(REAL_MATRIX))
            invalid["models"][0]["snapshot_date"] = "2026-08-04"
            asset = _write_installed_asset(root, matrix=invalid)
            events = root / "events.json"
            events.write_text(json.dumps([_native_receipt()]), encoding="utf-8")
            output = root / "summary.json"
            stderr = io.StringIO()
            with mock.patch(
                "workflow_kernel.cli._runtime_home", return_value=root,
            ), contextlib.redirect_stderr(stderr):
                self.assertEqual(cli.main([
                    "run-cost-summary", "--events", str(events),
                    "--output", str(output),
                    "--matrix", str(asset),
                ]), 0)
            self.assertEqual(stderr.getvalue().count("skipping imputation"), 1)
            self.assertIsNone(
                json.loads(output.read_text(encoding="utf-8"))["lanes"][0]["cost_usd"],
            )

    def test_unmocked_resolver_selects_first_alias_contract_release(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for version, matrix in (("1.10.0", MATRIX), ("1.11.0", REAL_MATRIX)):
                root = (
                    home / ".codex/plugins/cache/depot/openrouter" / version
                )
                bundle = _write_bundle(root, matrix)
                marker = bundle.root / ".codex-plugin/plugin.json"
                marker.parent.mkdir(parents=True)
                marker.write_text(json.dumps({
                    "name": "openrouter", "version": version,
                }), encoding="utf-8")
            selected = resolve_plugin_bundle(
                "openrouter",
                ["skills/openrouter-delegate/references/model-matrix.json"],
                home=home, minimum_version="1.11.0",
            )
            self.assertEqual(selected.version, "1.11.0")
            selected_matrix = json.loads((
                selected.root
                / "skills/openrouter-delegate/references/model-matrix.json"
            ).read_text(encoding="utf-8"))
            validate_model_matrix(selected_matrix)
            self.assertIn(
                "gpt-5.6-sol",
                selected_matrix["native_api_equivalent_cost"]["aliases"],
            )

    def test_cli_keeps_present_billed_cost_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = _write_installed_asset(root)
            events = root / "events.json"
            events.write_text(
                json.dumps([_native_receipt(cost_usd=4.25)]), encoding="utf-8",
            )
            output = root / "summary.json"
            with mock.patch(
                "workflow_kernel.cli._runtime_home", return_value=root,
            ):
                self.assertEqual(cli.main([
                    "run-cost-summary", "--events", str(events),
                    "--output", str(output),
                    "--matrix", str(asset),
                ]), 0)
            lane = json.loads(output.read_text(encoding="utf-8"))["lanes"][0]
            self.assertEqual(lane["cost_usd"], 4.25)
            self.assertEqual(lane["measurement_source"], "native_token_usage")


if __name__ == "__main__":
    unittest.main()
