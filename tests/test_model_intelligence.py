"""Regression tests for scheduled model-intelligence tooling."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools/model-intelligence.py"
NATIVE_BENCH = REPO / "tools/run-native-depot-role-benchmark.sh"


class ModelIntelligenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(TOOL), *args], cwd=REPO, text=True, capture_output=True
        )

    def test_catalog_refresh_updates_existing_models_and_only_nominates_new(self) -> None:
        matrix = self.root / "matrix.json"
        matrix.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "snapshot_date": "2026-08-01",
                    "catalog_source": "https://openrouter.ai/api/v1/models",
                    "freshness_rule_minutes": 15,
                    "native_api_equivalent_cost": {"snapshot_date": "2026-07-31"},
                    "models": [
                        {
                            "slug": "example/existing",
                            "name": "Old",
                            "catalog_status": "available",
                            "input_usd_per_m": 1.0,
                            "output_usd_per_m": 2.0,
                            "local_evidence": "preserve me",
                            "snapshot_date": "2026-08-01",
                        }
                    ],
                }
            )
        )
        catalog = self.root / "catalog.json"
        catalog.write_text(
            json.dumps(
                {
                    "data": [
                        {
                            "id": "example/existing",
                            "canonical_slug": "example/existing-20260826",
                            "name": "Existing 2",
                            "created": 10,
                            "context_length": 1000,
                            "architecture": {
                                "input_modalities": ["text"],
                                "output_modalities": ["text"],
                            },
                            "pricing": {"prompt": "0.0000005", "completion": "0.000001"},
                            "top_provider": {
                                "context_length": 1000,
                                "max_completion_tokens": 100,
                                "is_moderated": False,
                            },
                            "supported_parameters": ["tools", "structured_outputs"],
                            "default_parameters": {},
                        },
                        {
                            "id": "example/new",
                            "canonical_slug": "example/new-20260826",
                            "name": "New",
                            "created": 20,
                            "context_length": 2000,
                            "architecture": {
                                "input_modalities": ["text"],
                                "output_modalities": ["text"],
                            },
                            "pricing": {"prompt": "0.0000002", "completion": "0.0000004"},
                            "top_provider": {},
                            "supported_parameters": ["tools", "structured_outputs"],
                            "default_parameters": {},
                        },
                    ]
                }
            )
        )
        receipt = self.root / "receipt.json"
        result = self.run_tool(
            "catalog-refresh",
            "--catalog",
            str(catalog),
            "--matrix",
            str(matrix),
            "--observed-at",
            "2026-08-26T05:00:00+08:00",
            "--output",
            str(receipt),
            "--write",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        evidence = json.loads(receipt.read_text())
        self.assertGreater(evidence["material_change_count"], 0)
        self.assertEqual(evidence["new_candidates"][0]["slug"], "example/new")
        refreshed = json.loads(matrix.read_text())
        self.assertEqual([model["slug"] for model in refreshed["models"]], ["example/existing"])
        self.assertEqual(refreshed["models"][0]["input_usd_per_m"], 0.5)
        self.assertEqual(refreshed["models"][0]["local_evidence"], "preserve me")
        self.assertEqual(refreshed["native_api_equivalent_cost"]["snapshot_date"], "2026-07-31")
        stale = self.run_tool(
            "catalog-refresh",
            "--catalog",
            str(catalog),
            "--matrix",
            str(matrix),
            "--observed-at",
            "2026-08-26T05:00:00+08:00",
            "--write",
        )
        self.assertEqual(stale.returncode, 2)
        self.assertIn("not newer", stale.stderr)

    def test_report_keeps_tokens_bytes_cost_and_quality_separate(self) -> None:
        run = self.root / "runs" / "one"
        run.mkdir(parents=True)
        (run / "run-cost-summary.json").write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "model": "example/model",
                            "duration_seconds": 3,
                            "input_usage_count": 10,
                            "output_usage_count": 4,
                            "reasoning_usage_count": 2,
                            "input_bytes": None,
                            "cost_usd": 0.01,
                            "usage_estimated": False,
                            "measurement_source": "openrouter_api_receipt",
                        },
                        {
                            "model": "native/model",
                            "duration_seconds": 5,
                            "input_usage_count": None,
                            "output_usage_count": None,
                            "reasoning_usage_count": None,
                            "input_bytes": 400,
                            "cost_usd": 0.02,
                            "usage_estimated": True,
                            "measurement_source": "estimated_input_bytes",
                        },
                    ]
                }
            )
        )
        (run / "metrics.json").write_text(
            json.dumps(
                {
                    "finding_contributions_by_model": {"example/model": 2},
                    "finding_contributions_by_provider": {"example": 2},
                    "models": {"example/model": 1},
                    "providers": {"example": 1},
                    "retry_reasons": {"capacity": 1},
                    "completion_rate": 1.0,
                    "fallback_rate": 0.0,
                    "validation_first_pass_rate": 0.5,
                    "canonical_finding_count": 2,
                }
            )
        )
        benchmark = self.root / "bench" / "example" / "case" / "run-1"
        benchmark.mkdir(parents=True)
        (benchmark / "result.json").write_text(
            json.dumps(
                {
                    "caseId": "case",
                    "parsed": True,
                    "qualityScore": 100,
                    "durationSeconds": 2,
                    "requestedModel": "example/model",
                    "servedModel": "example/model",
                    "transport": "openrouter",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "cost": 0.01},
                }
            )
        )
        output = self.root / "latest.json"
        markdown = self.root / "latest.md"
        result = self.run_tool(
            "report",
            "--run-root",
            str(self.root / "runs"),
            "--benchmark-root",
            str(self.root / "bench"),
            "--observed-at",
            "2026-08-26T05:00:00+08:00",
            "--json-output",
            str(output),
            "--markdown-output",
            str(markdown),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text())
        rows = {row["model"]: row for row in report["production"]["by_model"]}
        self.assertEqual(rows["example/model"]["input_tokens"], 10)
        self.assertEqual(rows["example/model"]["input_bytes"], 0)
        self.assertEqual(rows["native/model"]["input_tokens"], 0)
        self.assertEqual(rows["native/model"]["input_bytes"], 400)
        self.assertEqual(rows["example/model"]["finding_contributions"], 2)
        self.assertIn("different units", markdown.read_text())


class NativeDepotBenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def executable(self, name: str, content: str) -> Path:
        path = self.root / name
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_codex_subscription_attempt_uses_existing_scorer(self) -> None:
        stub = self.executable(
            "codex-stub",
            """#!/usr/bin/env bash
set -eu
output=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-last-message) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
cat >/dev/null
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$output"
printf '%s\n' '{"usage":{"input_tokens":20,"output_tokens":10}}'
""",
        )
        result_dir = self.root / "codex-result"
        env = os.environ.copy()
        env["DEPOT_BENCH_CODEX_BIN"] = str(stub)
        result = subprocess.run(
            [
                str(NATIVE_BENCH),
                "--case",
                "review-zero-deferral",
                "--transport",
                "codex-cli",
                "--model",
                "gpt-5.6-sol",
                "--effort",
                "medium",
                "--result-dir",
                str(result_dir),
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertEqual(scored["qualityScore"], 100)
        self.assertEqual(scored["transport"], "codex-cli")
        self.assertEqual(scored["billingMode"], "included-subscription")

    def test_claude_subscription_attempt_uses_existing_scorer(self) -> None:
        stub = self.executable(
            "claude-stub",
            """#!/usr/bin/env bash
set -eu
cat >/dev/null
printf '%s\n' '{"structured_output":{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false},"usage":{"input_tokens":10,"output_tokens":5}}'
""",
        )
        result_dir = self.root / "claude-result"
        env = os.environ.copy()
        env["DEPOT_BENCH_CLAUDE_BIN"] = str(stub)
        result = subprocess.run(
            [
                str(NATIVE_BENCH),
                "--case",
                "review-zero-deferral",
                "--transport",
                "claude-cli",
                "--model",
                "fable",
                "--effort",
                "medium",
                "--result-dir",
                str(result_dir),
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertEqual(scored["qualityScore"], 100)
        self.assertEqual(scored["transport"], "claude-cli")


if __name__ == "__main__":
    unittest.main()
