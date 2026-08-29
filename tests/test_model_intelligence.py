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

    def run_native(
        self,
        *,
        case: str,
        transport: str,
        model: str,
        result_dir: Path,
        stub: Path,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env[
            "DEPOT_BENCH_CODEX_BIN"
            if transport == "codex-cli"
            else "DEPOT_BENCH_CLAUDE_BIN"
        ] = str(stub)
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [
                str(NATIVE_BENCH),
                "--case",
                case,
                "--transport",
                transport,
                "--model",
                model,
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

    def codex_stub(self, name: str, event: str, output: str | None) -> Path:
        output_command = (
            f"printf '%s\\n' '{output}' > \"$output\"" if output is not None else ":"
        )
        return self.executable(
            name,
            f"""#!/usr/bin/env bash
set -eu
output=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-last-message) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
cat >/dev/null
{output_command}
printf '%s\n' '{event}'
""",
        )

    def claude_stub(self, name: str, telemetry: dict[str, object]) -> Path:
        return self.executable(
            name,
            "#!/usr/bin/env bash\nset -eu\ncat >/dev/null\nprintf '%s\\n' '"
            + json.dumps(telemetry, separators=(",", ":"))
            + "'\n",
        )

    def test_codex_explicit_identity_and_independent_usage_use_v2_scorer(self) -> None:
        output = '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}'
        event = json.dumps(
            {
                "type": "turn.completed",
                "model": "gpt-5.6-luna",
                "provider": "openai",
                "fallbackUsed": False,
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "reasoning_tokens": 3,
                    "cached_input_tokens": 4,
                    "cache_creation_input_tokens": 5,
                },
            },
            separators=(",", ":"),
        )
        stub = self.codex_stub("codex-stub", event, output)
        result_dir = self.root / "codex-result"
        result = self.run_native(
            case="review-zero-deferral",
            transport="codex-cli",
            model="gpt-5.6-luna",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertEqual(scored["qualityScore"], 100)
        self.assertTrue(scored["overallSuccess"])
        self.assertEqual(scored["transport"], "codex-cli")
        self.assertEqual(scored["billingMode"], "included-subscription")
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(receipt["responseModel"], "gpt-5.6-luna")
        self.assertEqual(
            receipt["usage"],
            {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "reasoning_tokens": 3,
                "cache_read_tokens": 4,
                "cache_creation_tokens": 5,
                "cost": None,
            },
        )
        self.assertFalse(receipt["fallbackUsed"])
        self.assertEqual(receipt["fallbackProvenance"], "cli-event")

    def test_claude_opus_primary_retains_haiku_as_ancillary(self) -> None:
        raw_response = {
            "nextChunk": "role-complete benchmark corpus and deterministic scorer",
            "executorRole": "bounded repository architect",
            "executorCapabilities": ["repository reading", "structured results"],
            "rejectedComplexity": ["hosted judge", "generic workflow engine"],
        }
        telemetry = {
            "result": json.dumps(raw_response),
            "usage": {
                "input_tokens": 995,
                "output_tokens": 1203,
                "reasoning_tokens": 77,
                "cache_read_input_tokens": 11,
                "cache_creation_input_tokens": 22083,
            },
            "modelUsage": {
                "claude-haiku-4-5-20251001": {
                    "inputTokens": 993,
                    "outputTokens": 13,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                    "provider": "anthropic",
                },
                "claude-opus-5": {
                    "inputTokens": 2,
                    "outputTokens": 1190,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 22083,
                    "provider": "anthropic",
                },
            },
        }
        stub = self.claude_stub("claude-opus-stub", telemetry)
        result_dir = self.root / "claude-opus-result"
        result = self.run_native(
            case="assembly-next-chunk",
            transport="claude-cli",
            model="opus",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(receipt["responseModel"], "claude-opus-5")
        self.assertEqual(
            receipt["primaryModelProvenance"],
            "modelUsage-unique-max-output-tokens",
        )
        self.assertEqual(receipt["primaryModelUsage"]["outputTokens"], 1190)
        self.assertEqual(
            [item["model"] for item in receipt["ancillaryModelUsage"]],
            ["claude-haiku-4-5-20251001"],
        )
        self.assertEqual(receipt["usage"]["cache_read_tokens"], 11)
        self.assertEqual(receipt["usage"]["cache_creation_tokens"], 22083)
        self.assertIsNone(receipt["fallbackUsed"])
        self.assertEqual(receipt["fallbackProvenance"], "not_available")
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertFalse(scored["comparable"])
        self.assertEqual(scored["failureClass"], "unknown-served-identity")
        self.assertEqual((result_dir / "output.json").read_text(), json.dumps(raw_response) + "\n")
        self.assertEqual(json.loads((result_dir / "native-events.json").read_text()), telemetry)

    def test_claude_tied_output_usage_is_ambiguous(self) -> None:
        telemetry = {
            "result": "{}",
            "fallbackUsed": False,
            "modelUsage": {
                "claude-opus-5": {"outputTokens": 20, "provider": "anthropic"},
                "claude-haiku-4-5": {"outputTokens": 20, "provider": "anthropic"},
            },
        }
        stub = self.claude_stub("claude-ambiguous-stub", telemetry)
        result_dir = self.root / "claude-ambiguous-result"
        result = self.run_native(
            case="assembly-next-chunk",
            transport="claude-cli",
            model="opus",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertIsNone(receipt["responseModel"])
        self.assertTrue(receipt["identityAmbiguous"])
        self.assertEqual(receipt["primaryModelProvenance"], "modelUsage-tied-max-output-tokens")
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertFalse(scored["comparable"])
        self.assertFalse(scored["overallSuccess"])
        self.assertIsNone(scored["modelConclusion"])

    def test_codex_missing_served_identity_never_substitutes_requested_alias(self) -> None:
        output = '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}'
        event = '{"type":"turn.completed","fallbackUsed":false,"usage":{"input_tokens":20,"output_tokens":10}}'
        stub = self.codex_stub("codex-no-identity-stub", event, output)
        result_dir = self.root / "codex-no-identity-result"
        result = self.run_native(
            case="review-zero-deferral",
            transport="codex-cli",
            model="gpt-5.6-luna",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(receipt["requestedModel"], "gpt-5.6-luna")
        self.assertIsNone(receipt["responseModel"])
        self.assertEqual(receipt["responseModelProvenance"], "not_available")
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertIsNone(scored["servedIdentity"])
        self.assertFalse(scored["comparable"])

    def test_codex_explicit_fallback_true_retains_attempt_provenance(self) -> None:
        output = '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}'
        event = json.dumps(
            {
                "type": "turn.completed",
                "model": "gpt-5.6-luna-20260829",
                "provider": "openai",
                "fallbackUsed": True,
                "attemptedModels": ["gpt-5.6-luna", "gpt-5.6-luna-20260829"],
            },
            separators=(",", ":"),
        )
        stub = self.codex_stub("codex-fallback-stub", event, output)
        result_dir = self.root / "codex-fallback-result"
        result = self.run_native(
            case="review-zero-deferral",
            transport="codex-cli",
            model="gpt-5.6-luna",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertTrue(receipt["fallbackUsed"])
        self.assertEqual(receipt["fallbackProvenance"], "cli-event")
        self.assertEqual(
            receipt["attemptedModels"],
            ["gpt-5.6-luna", "gpt-5.6-luna-20260829"],
        )
        self.assertEqual(receipt["attemptedModel"], "gpt-5.6-luna-20260829")

    def test_fenced_claude_object_normalizes_without_hiding_strict_failure(self) -> None:
        response = "```json\n{}\n```"
        telemetry = {
            "result": response,
            "model": "fable",
            "provider": "anthropic",
            "fallbackUsed": False,
            "usage": {"input_tokens": 2, "output_tokens": 3},
        }
        stub = self.claude_stub("claude-fenced-stub", telemetry)
        result_dir = self.root / "claude-fenced-result"
        result = self.run_native(
            case="assembly-next-chunk",
            transport="claude-cli",
            model="fable",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertFalse(scored["strictParse"]["passed"])
        self.assertTrue(scored["normalizedParse"]["passed"])
        self.assertEqual(
            scored["normalizedParse"]["normalization"],
            "whole-response-markdown-json-fence",
        )
        self.assertEqual(scored["rawOutput"], response + "\n")
        self.assertFalse(scored["contractPassed"])
        self.assertFalse(scored["overallSuccess"])

    def test_operational_failures_cannot_be_quality_successes(self) -> None:
        output = '{"findings":[],"deferred":false}'
        cases = {
            "nonzero": self.executable(
                "codex-nonzero-stub",
                "#!/usr/bin/env bash\nset -eu\noutput=''\nwhile [ \"$#\" -gt 0 ]; do case \"$1\" in --output-last-message) output=\"$2\"; shift 2 ;; *) shift ;; esac; done\ncat >/dev/null\nprintf '%s\\n' '"
                + output
                + "' > \"$output\"\nprintf '%s\\n' '{\"type\":\"turn.completed\",\"model\":\"gpt-5.6-luna\",\"provider\":\"openai\",\"fallbackUsed\":false}'\nexit 7\n",
            ),
            "missing-output": self.codex_stub(
                "codex-missing-output-stub",
                '{"type":"turn.completed","model":"gpt-5.6-luna","provider":"openai","fallbackUsed":false}',
                None,
            ),
            "malformed-telemetry": self.codex_stub(
                "codex-malformed-stub", "{malformed", output
            ),
        }
        for name, stub in cases.items():
            with self.subTest(name=name):
                result_dir = self.root / f"operational-{name}"
                result = self.run_native(
                    case="review-zero-deferral",
                    transport="codex-cli",
                    model="gpt-5.6-luna",
                    result_dir=result_dir,
                    stub=stub,
                )
                self.assertNotEqual(result.returncode, 0)
                receipt = json.loads((result_dir / "receipt.json").read_text())
                self.assertEqual(receipt["outcome"], "failed")
                scored = json.loads((result_dir / "result.json").read_text())
                self.assertFalse(scored["overallSuccess"])
                self.assertIsNone(scored["modelConclusion"])

    def test_preflight_rejections_do_not_invoke_cli_or_overwrite_results(self) -> None:
        marker = self.root / "invoked"
        stub = self.executable(
            "marker-stub",
            "#!/usr/bin/env bash\nprintf invoked > \"$DEPOT_BENCH_MARKER\"\nexit 99\n",
        )
        policy_path = REPO / "plugins/model-router/skills/model-router/references/role-policy.json"
        insufficient_policy = json.loads(policy_path.read_text())
        luna = next(
            candidate
            for candidate in insufficient_policy["roles"]["review-fast"]
            if candidate["model"] == "gpt-5.6-luna"
        )
        luna["capabilities"].remove("structured-output")
        insufficient_path = self.root / "insufficient-policy.json"
        insufficient_path.write_text(json.dumps(insufficient_policy))
        malformed_policy = self.root / "malformed-policy.json"
        malformed_policy.write_text("{malformed")
        malformed_suite = self.root / "malformed-suite.json"
        malformed_suite.write_text(json.dumps({"schemaVersion": 1, "cases": []}))

        scenarios = [
            ("unknown-case", "not-a-v2-case", "gpt-5.6-luna", {}),
            ("wrong-role", "review-zero-deferral", "gpt-5.6-sol", {}),
            (
                "insufficient-capabilities",
                "review-zero-deferral",
                "gpt-5.6-luna",
                {"DEPOT_BENCH_ROLE_POLICY": str(insufficient_path)},
            ),
            (
                "malformed-policy",
                "review-zero-deferral",
                "gpt-5.6-luna",
                {"DEPOT_BENCH_ROLE_POLICY": str(malformed_policy)},
            ),
            (
                "malformed-suite",
                "review-zero-deferral",
                "gpt-5.6-luna",
                {"DEPOT_BENCH_SUITE": str(malformed_suite)},
            ),
        ]
        for name, case, model, overrides in scenarios:
            with self.subTest(name=name):
                marker.unlink(missing_ok=True)
                result = self.run_native(
                    case=case,
                    transport="codex-cli",
                    model=model,
                    result_dir=self.root / f"rejected-{name}",
                    stub=stub,
                    extra_env={"DEPOT_BENCH_MARKER": str(marker), **overrides},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())

        marker.unlink(missing_ok=True)
        nonempty = self.root / "nonempty-result"
        nonempty.mkdir()
        sentinel = nonempty / "retained.txt"
        sentinel.write_text("do not overwrite")
        result = self.run_native(
            case="review-zero-deferral",
            transport="codex-cli",
            model="gpt-5.6-luna",
            result_dir=nonempty,
            stub=stub,
            extra_env={"DEPOT_BENCH_MARKER": str(marker)},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertEqual(list(nonempty.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_text(), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
