"""Regression tests for scheduled model-intelligence tooling."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
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

    def v2_result(
        self,
        *,
        case_id: str,
        model: str,
        transport: str,
        observed_at: str,
        endpoint_provider: str = "openai",
        success: bool = True,
        failure_class: str = "none",
        failure_owner: str = "none",
        benchmark_fault: bool = False,
        transport_status: str = "success",
        identity_confidence: str = "confirmed",
        quality_score: int = 100,
        duration: int | None = 2,
        usage: dict[str, int | float | None] | None = None,
    ) -> dict[str, object]:
        suite = json.loads(
            (
                REPO
                / "plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
            ).read_text()
        )
        case = next(item for item in suite["cases"] if item["id"] == case_id)
        suite_bindings = suite["bindings"]
        case_bindings = suite_bindings["cases"][case_id]
        bindings = {
            "suiteRevision": suite_bindings["suiteRevision"],
            "suiteDigest": suite_bindings["suiteDigest"],
            "caseRevision": case_bindings["caseRevision"],
            "caseDigest": case_bindings["caseDigest"],
            "promptRevision": case_bindings["promptRevision"],
            "promptDigest": case_bindings["promptDigest"],
            "scorerRevision": case_bindings["scorerRevision"],
            "scorerDigest": case_bindings["scorerDigest"],
            "normalizerRevision": suite_bindings["normalizerRevision"],
            "normalizerDigest": suite_bindings["normalizerDigest"],
        }
        gate = success
        return {
            "schemaVersion": 2,
            "suiteId": suite["suiteId"],
            "caseId": case_id,
            "role": case["role"],
            "observedAt": observed_at,
            "behavioralContract": suite["behavioralContract"],
            "evidenceBindings": {
                name: {"declared": value, "actual": value, "match": True}
                for name, value in bindings.items()
            },
            "transport": transport,
            "endpointProvider": endpoint_provider,
            "transportOutcome": {"status": transport_status, "failureKind": None},
            "identityStatus": {"confidence": identity_confidence, "provenance": "response"},
            "requestedIdentity": model,
            "servedIdentity": model,
            "fallback": {
                "used": False,
                "attemptedIdentity": model,
                "attemptedIdentities": [model],
                "provenance": "response_model",
            },
            "durationSeconds": duration,
            "usage": usage
            if usage is not None
            else {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "reasoning_tokens": 2,
                "cache_read_tokens": 3,
                "cache_creation_tokens": 1,
                "cost": 0.01,
            },
            "strictParse": {"passed": gate},
            "normalizedParse": {"passed": True, "normalization": "strict-raw-object"},
            "contractPassed": gate,
            "mandatoryPassed": gate,
            "semanticPassed": gate,
            "semanticScore": quality_score,
            "validationPassed": gate,
            "benchmarkFault": benchmark_fault,
            "comparable": not benchmark_fault and transport_status == "success" and identity_confidence == "confirmed",
            "overallSuccess": success,
            "failureClass": failure_class,
            "failureOwner": failure_owner,
            "failureReasons": [] if success else [failure_class],
            "modelConclusion": "success" if success else None,
            "qualityScore": quality_score,
            "parsed": True,
        }

    def write_attempt(
        self,
        benchmark_root: Path,
        name: str,
        result: dict[str, object],
        *,
        receipt: dict[str, object] | None = None,
        output: dict[str, object] | None = None,
        human: dict[str, object] | None = None,
    ) -> Path:
        directory = benchmark_root / name
        directory.mkdir(parents=True)
        (directory / "result.json").write_text(json.dumps(result))
        if receipt is not None:
            (directory / "receipt.json").write_text(json.dumps(receipt))
        if output is not None:
            (directory / "output.json").write_text(json.dumps(output))
        if human is not None:
            (directory / "human-rubric.json").write_text(json.dumps(human))
        return directory

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

    def test_v2_rollup_uses_validated_gates_grouping_and_attributable_rework(self) -> None:
        benchmark_root = self.root / "bench-v2"
        model = "deepseek/deepseek-v4-flash-0731"
        benchmark_fault = self.v2_result(
            case_id="review-zero-deferral",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T01:00:00Z",
            endpoint_provider="Baidu",
            success=False,
            failure_class="benchmark-prompt-contract-fault",
            failure_owner="benchmark",
            benchmark_fault=True,
        )
        partial = self.v2_result(
            case_id="review-zero-deferral",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T01:01:00Z",
            endpoint_provider="Reka AI",
            success=False,
            failure_class="semantic-assertion-failure",
            failure_owner="model",
            quality_score=15,
            duration=2,
        )
        partial["contractPassed"] = True
        partial["mandatoryPassed"] = True
        partial["semanticPassed"] = False
        partial["validationPassed"] = False
        validated = self.v2_result(
            case_id="review-zero-deferral",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T01:02:00Z",
            endpoint_provider="DeepInfra",
            duration=3,
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 7,
                "reasoning_tokens": 4,
                "cache_read_tokens": 6,
                "cache_creation_tokens": 2,
                "cost": 0.02,
            },
        )
        for name, evidence in (
            ("01-benchmark-fault", benchmark_fault),
            ("02-partial", partial),
            ("03-valid", validated),
        ):
            self.write_attempt(benchmark_root, name, evidence)

        transport_failure = self.v2_result(
            case_id="review-false-positive-control",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T01:03:00Z",
            success=False,
            failure_class="transport-failure",
            failure_owner="operational",
            transport_status="failed",
        )
        self.write_attempt(benchmark_root, "04-transport-failure", transport_failure)
        incompatible = self.v2_result(
            case_id="review-zero-deferral",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T01:04:00Z",
        )
        incompatible["evidenceBindings"]["promptDigest"]["match"] = False
        self.write_attempt(benchmark_root, "05-incompatible", incompatible)
        incomplete_dir = benchmark_root / "06-incomplete"
        incomplete_dir.mkdir(parents=True)
        (incomplete_dir / "receipt.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "requestedModel": model,
                    "transport": "openrouter",
                    "outcome": "failed",
                    "failureKind": "http-error",
                    "durationSeconds": 9,
                    "usage": {"prompt_tokens": 11, "cache_read_tokens": 4},
                    "benchmark": {
                        "suiteId": "depot-role-v2",
                        "caseId": "review-zero-deferral",
                        "role": "review-fast",
                    },
                }
            )
        )

        output = self.root / "v2.json"
        markdown = self.root / "v2.md"
        completed = self.run_tool(
            "report",
            "--run-root",
            str(self.root / "no-runs"),
            "--benchmark-root",
            str(benchmark_root),
            "--observed-at",
            "2026-08-29T09:00:00+08:00",
            "--json-output",
            str(output),
            "--markdown-output",
            str(markdown),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(output.read_text())
        rollup = report["benchmarks"]
        primary = next(group for group in rollup["groups"] if group["case_id"] == "review-zero-deferral")
        self.assertEqual(primary["attempts"], 3)
        self.assertEqual(primary["comparable_attempts"], 2)
        self.assertEqual(primary["validated_attempts"], 1)
        self.assertFalse(primary["first_pass_validated"])
        self.assertEqual(primary["model_rework_to_valid"], 1)
        self.assertEqual(primary["time_to_first_validated_seconds"], 5)
        self.assertEqual(primary["median_duration_seconds"], 2.5)
        self.assertEqual(primary["tokens_to_first_validated"]["prompt_tokens"], 30)
        self.assertEqual(primary["operational_retries_before_valid"], {"prompt": 1})
        self.assertEqual(
            set(primary["endpoint_providers"]), {"Baidu", "Reka AI", "DeepInfra"}
        )
        self.assertEqual(primary["failure_counts"]["semantic"], 1)
        self.assertNotIn(15, [group["validated_attempts"] for group in rollup["groups"]])
        self.assertEqual(len(rollup["incompatible_v2"]), 1)
        self.assertEqual(rollup["incompatible_v2"][0]["model_conclusion"], None)
        self.assertEqual(rollup["incomplete_attempts"][0]["duration_seconds"], 9)
        self.assertEqual(rollup["incomplete_attempts"][0]["prompt_tokens"], 11)
        self.assertEqual(rollup["routing_conclusion"], "no routing change justified")
        review_role = next(role for role in rollup["roles"] if role["role"] == "review-fast")
        self.assertEqual(review_role["median_duration_seconds"], 2.5)
        model_row = next(
            row for row in rollup["model_role_evidence"]
            if row["role"] == "review-fast" and row["model"] == model
        )
        self.assertEqual(model_row["row_level_conclusion"], "no model conclusion")
        self.assertEqual(model_row["routing_conclusion"], "no routing change justified")
        self.assertEqual(
            {role["role"] for role in rollup["roles"]},
            set(
                json.loads(
                    (
                        REPO
                        / "plugins/model-router/skills/model-router/references/role-policy.json"
                    ).read_text()
                )["roles"]
            ),
        )
        self.assertLess(
            markdown.read_text().index("Per-role validated quality and efficiency"),
            markdown.read_text().index("Provider spend and access economics"),
        )
        self.assertIn("no model conclusion", markdown.read_text())
        self.assertIn("| no model conclusion | no routing change justified |", markdown.read_text())

    def test_v2_digest_compatibility_and_missing_ordering_stay_separate_and_null(self) -> None:
        benchmark_root = self.root / "digest-v2"
        for name in ("one", "two"):
            evidence = self.v2_result(
                case_id="mechanical-owned-edit",
                model="gpt-5.6-luna",
                transport="codex-cli",
                observed_at="not-an-order",
            )
            evidence["durationSeconds"] = None
            evidence["usage"] = {
                "prompt_tokens": None,
                "completion_tokens": None,
                "reasoning_tokens": None,
                "cache_read_tokens": None,
                "cache_creation_tokens": None,
                "cost": None,
            }
            if name == "two":
                evidence["evidenceBindings"]["suiteDigest"] = {
                    "declared": "sha256:" + "b" * 64,
                    "actual": "sha256:" + "b" * 64,
                    "match": True,
                }
            self.write_attempt(benchmark_root, name, evidence)
        output = self.root / "digest.json"
        completed = self.run_tool(
            "report",
            "--run-root",
            str(self.root / "no-runs"),
            "--benchmark-root",
            str(benchmark_root),
            "--observed-at",
            "2026-08-29T09:00:00+08:00",
            "--json-output",
            str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        groups = rollup["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(rollup["incompatible_v2"]), 1)
        for group in groups:
            self.assertIsNone(group["first_pass_validated"])
            self.assertIsNone(group["model_rework_to_valid"])
            self.assertIsNone(group["time_to_first_validated_seconds"])
            self.assertIsNone(group["tokens_to_first_validated"]["prompt_tokens"])
            self.assertEqual(group["telemetry_coverage"]["tool_calls"]["recorded"], 0)

    def test_v2_mandatory_validation_and_identity_failures_are_distinct(self) -> None:
        benchmark_root = self.root / "failure-classes-v2"
        mandatory = self.v2_result(
            case_id="review-zero-deferral",
            model="gpt-5.6-luna",
            transport="codex-cli",
            observed_at="2026-08-29T03:00:00Z",
            success=False,
            failure_class="mandatory-assertion-failure",
            failure_owner="model",
            quality_score=50,
        )
        mandatory["contractPassed"] = True
        validation = self.v2_result(
            case_id="review-zero-deferral",
            model="gpt-5.6-luna",
            transport="codex-cli",
            observed_at="2026-08-29T03:01:00Z",
            success=False,
            failure_class="deterministic-validation-failure",
            failure_owner="model",
        )
        validation["contractPassed"] = True
        validation["mandatoryPassed"] = True
        validation["semanticPassed"] = True
        identity = self.v2_result(
            case_id="review-zero-deferral",
            model="gpt-5.6-luna",
            transport="codex-cli",
            observed_at="2026-08-29T03:02:00Z",
            success=True,
            failure_class="unknown-served-identity",
            failure_owner="operational",
            identity_confidence="unknown",
        )
        for name, evidence in (
            ("mandatory", mandatory),
            ("validation", validation),
            ("identity", identity),
        ):
            self.write_attempt(benchmark_root, name, evidence)
        output = self.root / "failure-classes.json"
        completed = self.run_tool(
            "report",
            "--run-root",
            str(self.root / "no-runs"),
            "--benchmark-root",
            str(benchmark_root),
            "--observed-at",
            "2026-08-29T09:00:00+08:00",
            "--json-output",
            str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        groups = json.loads(output.read_text())["benchmarks"]["groups"]
        categories = {
            attempt["failure_category"]: (group, attempt)
            for group in groups
            for attempt in group["attempt_records"]
        }
        self.assertEqual(set(categories), {"mandatory", "validation", "identity"})
        group = groups[0]
        self.assertEqual(group["validated_attempts"], 0)
        self.assertEqual(group["model_attributable_failures"], 2)
        self.assertEqual(group["comparable_attempts"], 2)
        self.assertEqual(group["operational_retries"], {"identity": 1})

    def test_editorial_human_evidence_is_optional_blinded_and_digest_matched(self) -> None:
        benchmark_root = self.root / "editorial-v2"
        output_artifact = {"copy": "member update", "preservedFacts": []}
        digest = "sha256:" + hashlib.sha256(
            (json.dumps(output_artifact, indent=2) + "\n").encode()
        ).hexdigest()
        accepted_result = self.v2_result(
            case_id="editorial-member-update",
            model="fable",
            transport="claude-cli",
            observed_at="2026-08-29T02:00:00Z",
            endpoint_provider="anthropic",
        )
        accepted_human = {
            "schemaVersion": 1,
            "suiteId": "depot-role-v2",
            "caseId": "editorial-member-update",
            "caseRevision": 2,
            "rubricRevision": 1,
            "outputArtifactSha256": digest,
            "observedAt": "2026-08-29T02:30:00Z",
            "blindToCandidate": True,
            "criterionScores": {"member-clarity": 5, "member-voice": 4},
        }
        self.write_attempt(
            benchmark_root,
            "accepted",
            accepted_result,
            output=output_artifact,
            human=accepted_human,
        )
        missing = self.v2_result(
            case_id="editorial-release-note",
            model="fable",
            transport="claude-cli",
            observed_at="2026-08-29T02:01:00Z",
            endpoint_provider="anthropic",
        )
        self.write_attempt(benchmark_root, "missing", missing, output={"headline": "release"})
        rejected = dict(accepted_human)
        rejected["candidate"] = "fable"
        rejected_result = self.v2_result(
            case_id="editorial-member-update",
            model="fable",
            transport="claude-cli",
            observed_at="2026-08-29T02:02:00Z",
            endpoint_provider="anthropic",
        )
        self.write_attempt(
            benchmark_root,
            "rejected",
            rejected_result,
            output=output_artifact,
            human=rejected,
        )
        report_path = self.root / "editorial.json"
        completed = self.run_tool(
            "report",
            "--run-root",
            str(self.root / "no-runs"),
            "--benchmark-root",
            str(benchmark_root),
            "--observed-at",
            "2026-08-29T09:00:00+08:00",
            "--json-output",
            str(report_path),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(report_path.read_text())["benchmarks"]
        editorial = next(role for role in rollup["roles"] if role["role"] == "editorial")
        self.assertEqual(editorial["editorial_human_evidence"]["accepted_receipts"], 1)
        self.assertEqual(editorial["editorial_human_evidence"]["median_mean_score"], 4.5)
        missing_group = next(group for group in rollup["groups"] if group["case_id"] == "editorial-release-note")
        self.assertIsNone(missing_group["editorial_human_evidence"])
        rejected_group = next(
            group for group in rollup["groups"]
            if group["case_id"] == "editorial-member-update"
            and group["editorial_human_rejections"]
        )
        self.assertEqual(
            rejected_group["editorial_human_rejections"],
            {"malformed or identity-bearing human rubric fields": 1},
        )

    def test_v2_policy_authority_and_closed_fallback_identity_gate_comparability(self) -> None:
        benchmark_root = self.root / "authority-v2"
        model = "deepseek/deepseek-v4-flash-0731"
        valid = self.v2_result(
            case_id="review-zero-deferral",
            model=model,
            transport="openrouter",
            observed_at="2026-08-29T04:00:00Z",
        )
        self.write_attempt(benchmark_root, "fallback-00-valid", valid)
        fallback_variants = {
            "true": {"used": True, "attemptedIdentity": model, "attemptedIdentities": [model], "provenance": "response_model"},
            "unavailable": {"used": None, "attemptedIdentity": model, "attemptedIdentities": [model], "provenance": "not_available"},
            "arbitrary": {"used": False, "attemptedIdentity": model, "attemptedIdentities": [model], "provenance": "claimed"},
            "contradictory": {"used": False, "attemptedIdentity": "other/model", "attemptedIdentities": [model, "other/model"], "provenance": "response_model"},
        }
        for offset, (name, fallback) in enumerate(fallback_variants.items(), 1):
            evidence = self.v2_result(
                case_id="review-zero-deferral",
                model=model,
                transport="openrouter",
                observed_at=f"2026-08-29T04:0{offset}:00Z",
            )
            evidence["fallback"] = fallback
            self.write_attempt(benchmark_root, f"fallback-{offset:02d}-{name}", evidence)

        authority_variants = []
        wrong_role = self.v2_result(
            case_id="review-zero-deferral", model=model, transport="openrouter",
            observed_at="2026-08-29T04:10:00Z",
        )
        wrong_role["role"] = "builder-fast"
        authority_variants.append(("wrong-role", wrong_role, None))
        wrong_candidate = self.v2_result(
            case_id="review-zero-deferral", model="not/policy-eligible", transport="openrouter",
            observed_at="2026-08-29T04:11:00Z",
        )
        authority_variants.append(("wrong-candidate", wrong_candidate, None))
        wrong_transport = self.v2_result(
            case_id="review-zero-deferral", model=model, transport="codex-cli",
            observed_at="2026-08-29T04:12:00Z",
        )
        authority_variants.append(("wrong-transport", wrong_transport, None))
        missing_capability = self.v2_result(
            case_id="research-claim-source-map", model="gpt-5.6-luna", transport="codex-cli",
            observed_at="2026-08-29T04:13:00Z",
        )
        authority_variants.append(("missing-capability", missing_capability, None))
        receipt_mismatch = self.v2_result(
            case_id="review-zero-deferral", model=model, transport="openrouter",
            observed_at="2026-08-29T04:14:00Z",
        )
        authority_variants.append(
            ("receipt-mismatch", receipt_mismatch, {"requestedModel": "other/model", "transport": "openrouter"})
        )
        for name, evidence, receipt in authority_variants:
            self.write_attempt(benchmark_root, name, evidence, receipt=receipt)

        output = self.root / "authority.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root), "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        fallback_group = next(
            group for group in rollup["groups"]
            if group["case_id"] == "review-zero-deferral"
            and group["requested_candidate"] == model
        )
        self.assertEqual(fallback_group["attempts"], 5)
        self.assertEqual(fallback_group["comparable_attempts"], 1)
        self.assertEqual(fallback_group["validated_attempts"], 1)
        self.assertEqual(fallback_group["operational_retries"], {"identity": 4})
        self.assertEqual(len(rollup["incompatible_v2"]), 5)
        self.assertTrue(all(item["model_conclusion"] is None for item in rollup["incompatible_v2"]))
        wrong_role_row = next(item for item in rollup["incompatible_v2"] if item["path"].endswith("wrong-role"))
        self.assertEqual(wrong_role_row["role"], "review-fast")
        review_role = next(role for role in rollup["roles"] if role["role"] == "review-fast")
        self.assertEqual(review_role["operational_retries"]["harness"], 4)
        research_role = next(role for role in rollup["roles"] if role["role"] == "research-fast")
        self.assertEqual(research_role["operational_retries"], {"harness": 1})
        self.assertEqual(review_role["retained_attempts"], 9)
        self.assertEqual(rollup["views"]["reliability"]["operational_retry_counts"]["harness"], 5)
        self.assertEqual(rollup["views"]["reliability"]["retained_attempts"], 10)

    def test_native_served_identity_must_match_the_policy_alias_mapping(self) -> None:
        benchmark_root = self.root / "native-alias-authority-v2"
        allowed = self.v2_result(
            case_id="assembly-next-chunk", model="opus", transport="claude-cli",
            observed_at="2026-08-29T04:20:00Z", endpoint_provider="anthropic",
        )
        allowed["servedIdentity"] = "claude-opus-5"
        allowed["fallback"]["attemptedIdentity"] = "claude-opus-5"
        allowed["fallback"]["attemptedIdentities"] = ["claude-opus-5"]
        rejected = self.v2_result(
            case_id="review-zero-deferral", model="gpt-5.6-luna", transport="codex-cli",
            observed_at="2026-08-29T04:21:00Z", endpoint_provider="openai",
        )
        rejected["servedIdentity"] = "gpt-5.6-sol"
        rejected["fallback"]["attemptedIdentity"] = "gpt-5.6-sol"
        rejected["fallback"]["attemptedIdentities"] = ["gpt-5.6-sol"]
        self.write_attempt(benchmark_root, "allowed-opus-alias", allowed)
        self.write_attempt(benchmark_root, "rejected-cross-model", rejected)

        output = self.root / "native-alias-authority.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root),
            "--observed-at", "2026-08-29T09:00:00+08:00", "--json-output", str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        groups = json.loads(output.read_text())["benchmarks"]["groups"]
        opus = next(group for group in groups if group["requested_candidate"] == "opus")
        luna = next(group for group in groups if group["requested_candidate"] == "gpt-5.6-luna")
        self.assertEqual(opus["validated_attempts"], 1)
        self.assertEqual(opus["comparable_attempts"], 1)
        self.assertEqual(luna["validated_attempts"], 0)
        self.assertEqual(luna["comparable_attempts"], 0)
        self.assertEqual(luna["operational_retries"], {"identity": 1})
        self.assertIsNone(luna["attempt_records"][0]["model_conclusion"])

    def test_v2_role_metrics_and_competitive_evidence_never_mix_evaluator_cohorts(self) -> None:
        benchmark_root = self.root / "cohorts-v2"

        def add_attempt(name: str, case_id: str, model: str, transport: str, scorer: str, duration: int) -> None:
            evidence = self.v2_result(
                case_id=case_id, model=model, transport=transport,
                observed_at=f"2026-08-29T05:{len(list(benchmark_root.glob('*'))):02d}:00Z",
                duration=duration,
            )
            evidence["evidenceBindings"]["scorerDigest"] = {
                "declared": scorer, "actual": scorer, "match": True,
            }
            self.write_attempt(benchmark_root, name, evidence)

        cases = ("review-zero-deferral", "review-false-positive-control")
        for scorer, durations in (("scorer-a", (2, 4, 6)), ("scorer-b", (10, 12, 14))):
            for case_id in cases:
                for attempt, duration in enumerate(durations, 1):
                    add_attempt(
                        f"luna-{scorer}-{case_id}-{attempt}", case_id,
                        "gpt-5.6-luna", "codex-cli", scorer, duration,
                    )
        for attempt in range(1, 4):
            add_attempt(
                f"deepseek-a-case-one-{attempt}", cases[0],
                "deepseek/deepseek-v4-flash-0731", "openrouter", "scorer-a", 3,
            )
            add_attempt(
                f"deepseek-b-case-two-{attempt}", cases[1],
                "deepseek/deepseek-v4-flash-0731", "openrouter", "scorer-b", 9,
            )

        output = self.root / "cohorts.json"
        markdown = self.root / "cohorts.md"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root), "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output), "--markdown-output", str(markdown),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        role = next(item for item in rollup["roles"] if item["role"] == "review-fast")
        self.assertEqual(role["evaluator_cohorts"], [])
        self.assertIsNone(role["first_pass_validated_rate"])
        self.assertIsNone(role["best_deterministic_quality"])
        self.assertIsNone(role["median_duration_seconds"])
        self.assertEqual(len(rollup["incompatible_v2"]), 18)
        self.assertTrue(all(item["model_conclusion"] is None for item in rollup["incompatible_v2"]))
        self.assertEqual(rollup["groups"], [])
        self.assertIn("Median duration", markdown.read_text())
        self.assertIn("Incompatible v2 attempts retained: 18", markdown.read_text())

    def test_v2_same_case_binding_conflicts_null_role_metrics_and_competition(self) -> None:
        benchmark_root = self.root / "case-binding-cohorts-v2"
        model = "gpt-5.6-luna"

        def add_attempt(name: str, case_id: str, binding: str, attempt: int) -> None:
            evidence = self.v2_result(
                case_id=case_id,
                model=model,
                transport="codex-cli",
                observed_at=f"2026-08-29T06:{len(list(benchmark_root.glob('*'))):02d}:00Z",
                duration=2 if binding == "a" else 10,
            )
            evidence["evidenceBindings"]["caseDigest"] = {
                "declared": f"case-{binding}", "actual": f"case-{binding}", "match": True,
            }
            evidence["evidenceBindings"]["promptDigest"] = {
                "declared": f"prompt-{binding}", "actual": f"prompt-{binding}", "match": True,
            }
            self.write_attempt(benchmark_root, name, evidence)

        for attempt in range(1, 4):
            add_attempt(f"zero-a-{attempt}", "review-zero-deferral", "a", attempt)
            add_attempt(f"zero-b-{attempt}", "review-zero-deferral", "b", attempt)
            add_attempt(
                f"false-positive-a-{attempt}",
                "review-false-positive-control",
                "a",
                attempt,
            )

        output = self.root / "case-binding-cohorts.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root),
            "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        role = next(item for item in rollup["roles"] if item["role"] == "review-fast")
        self.assertEqual(role["evaluator_cohorts"], [])
        self.assertFalse(role["case_binding_conflict"])
        self.assertIsNone(role["best_deterministic_quality"])
        self.assertIsNone(role["median_duration_seconds"])
        self.assertEqual(len(rollup["incompatible_v2"]), 9)
        self.assertEqual(rollup["groups"], [])

    def test_degraded_attempts_retain_receipt_evidence_and_all_recorded_spend_once(self) -> None:
        benchmark_root = self.root / "retained-v2"
        model = "deepseek/deepseek-v4-flash-0731"

        def receipt(cost: float | None, outcome: str = "failed") -> dict[str, object]:
            return {
                "schemaVersion": 2, "requestedModel": model, "responseModel": model,
                "servingProvider": "fixture-provider", "transport": "openrouter",
                "billingMode": "api", "outcome": outcome, "failureKind": "fixture-failure",
                "durationSeconds": 7,
                "usage": {
                    "prompt_tokens": 11, "completion_tokens": 5, "reasoning_tokens": 2,
                    "cache_read_tokens": 3, "cache_creation_tokens": 1, "cost": None,
                },
                "providerBilledCostUsd": cost,
                "contextTokens": 99, "toolCalls": 0,
                "benchmark": {"suiteId": "depot-role-v2", "caseId": "review-zero-deferral", "role": "review-fast"},
            }

        historical = {
            "schemaVersion": 1, "requestedModel": model, "servedModel": model,
            "transport": "openrouter", "role": "review-fast", "caseId": "review-zero-deferral",
            "usage": {"cost": 0.1},
        }
        self.write_attempt(benchmark_root, "historical", historical)
        incompatible = self.v2_result(
            case_id="review-zero-deferral", model=model, transport="openrouter",
            observed_at="2026-08-29T06:00:00Z",
            usage={"cost": 0.2},
        )
        incompatible["evidenceBindings"]["promptDigest"]["match"] = False
        self.write_attempt(benchmark_root, "incompatible", incompatible)
        malformed_dir = benchmark_root / "malformed"
        malformed_dir.mkdir(parents=True)
        (malformed_dir / "result.json").write_text("{")
        (malformed_dir / "receipt.json").write_text(json.dumps(receipt(0.3)))
        non_object_dir = benchmark_root / "non-object"
        non_object_dir.mkdir(parents=True)
        (non_object_dir / "result.json").write_text("[]")
        (non_object_dir / "receipt.json").write_text(json.dumps(receipt(0.4)))
        missing_dir = benchmark_root / "missing-result"
        missing_dir.mkdir(parents=True)
        (missing_dir / "receipt.json").write_text(json.dumps(receipt(0.5)))
        (missing_dir / "prompt.txt").write_text("fixture prompt with receipt")
        prompt_only = benchmark_root / "prompt-only"
        prompt_only.mkdir(parents=True)
        (prompt_only / "prompt.txt").write_text("fixture prompt")

        output = self.root / "retained.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root), "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        self.assertAlmostEqual(rollup["measured_cost_usd"], 1.5)
        self.assertEqual(
            rollup["views"]["provider_spend"]["recorded_cost_coverage"],
            {"recorded": 5, "attempts": 6, "rate": 5 / 6},
        )
        retained = {Path(item["path"]).name: item for item in rollup["incomplete_attempts"]}
        self.assertEqual(set(retained), {"malformed", "non-object", "missing-result", "prompt-only"})
        for name in ("malformed", "non-object", "missing-result"):
            item = retained[name]
            self.assertEqual(item["requested_candidate"], model)
            self.assertEqual(item["served_identity"], model)
            self.assertEqual(item["endpoint_provider"], "fixture-provider")
            self.assertEqual(item["transport"], "openrouter")
            self.assertEqual(item["role"], "review-fast")
            self.assertEqual(item["case_id"], "review-zero-deferral")
            self.assertEqual(item["receipt_outcome"], "failed")
            self.assertEqual(item["duration_seconds"], 7)
            self.assertEqual(item["prompt_tokens"], 11)
            self.assertEqual(item["cache_read_tokens"], 3)
            self.assertEqual(item["context_tokens"], 99)
            self.assertEqual(item["cost_usd"], {"malformed": 0.3, "non-object": 0.4, "missing-result": 0.5}[name])
            self.assertEqual(item["failure_reason"], "fixture-failure")
        self.assertTrue(all(value is None for key, value in retained["prompt-only"].items() if key not in {"path", "failure_category", "failure_reason"}))
        empty_root = self.root / "empty-spend"
        empty_root.mkdir()
        empty_output = self.root / "empty-spend.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(empty_root), "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(empty_output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIsNone(json.loads(empty_output.read_text())["benchmarks"]["measured_cost_usd"])

    def test_human_rubric_requires_artifact_recomputation_and_valid_declared_digests(self) -> None:
        benchmark_root = self.root / "human-digest-v2"
        artifact = {"copy": "member update", "preservedFacts": []}
        digest = hashlib.sha256((json.dumps(artifact, indent=2) + "\n").encode()).hexdigest()

        def rubric(output_digest: str) -> dict[str, object]:
            return {
                "schemaVersion": 1, "suiteId": "depot-role-v2", "caseId": "editorial-member-update",
                "caseRevision": 2, "rubricRevision": 1, "outputArtifactSha256": output_digest,
                "observedAt": "2026-08-29T07:30:00Z", "blindToCandidate": True,
                "criterionScores": {"member-clarity": 5, "member-voice": 4},
            }

        no_artifact = self.v2_result(
            case_id="editorial-member-update", model="fable", transport="claude-cli",
            observed_at="2026-08-29T07:00:00Z",
        )
        no_artifact["normalizedOutputArtifactSha256"] = "a" * 64
        self.write_attempt(benchmark_root, "no-artifact", no_artifact, human=rubric("a" * 64))
        bad_rubric = self.v2_result(
            case_id="editorial-member-update", model="fable", transport="claude-cli",
            observed_at="2026-08-29T07:01:00Z",
        )
        self.write_attempt(benchmark_root, "bad-rubric", bad_rubric, output=artifact, human=rubric("SHA256:" + digest.upper()))
        bad_result = self.v2_result(
            case_id="editorial-member-update", model="fable", transport="claude-cli",
            observed_at="2026-08-29T07:02:00Z",
        )
        bad_result["normalizedOutputArtifactSha256"] = "sha256:" + "b" * 64
        self.write_attempt(benchmark_root, "bad-result", bad_result, output=artifact, human=rubric(digest))
        invalid_result = self.v2_result(
            case_id="editorial-member-update", model="fable", transport="claude-cli",
            observed_at="2026-08-29T07:02:30Z",
        )
        invalid_result["normalizedOutputArtifactSha256"] = "SHA256:" + digest.upper()
        self.write_attempt(benchmark_root, "invalid-result", invalid_result, output=artifact, human=rubric(digest))
        accepted = self.v2_result(
            case_id="editorial-member-update", model="fable", transport="claude-cli",
            observed_at="2026-08-29T07:03:00Z",
        )
        accepted["normalizedOutputArtifactSha256"] = "sha256:" + digest
        self.write_attempt(benchmark_root, "accepted", accepted, output=artifact, human=rubric("sha256:" + digest))

        output = self.root / "human-digest.json"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(benchmark_root), "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        rollup = json.loads(output.read_text())["benchmarks"]
        editorial = next(role for role in rollup["roles"] if role["role"] == "editorial")
        self.assertEqual(editorial["editorial_human_evidence"]["accepted_receipts"], 1)
        rejections = sum((Counter(group["editorial_human_rejections"]) for group in rollup["groups"]), Counter())
        self.assertEqual(rejections["human rubric normalized output artifact unavailable"], 1)
        self.assertEqual(rejections["human rubric output digest syntax invalid"], 1)
        self.assertEqual(rejections["declared normalized output digest mismatch"], 1)
        self.assertEqual(rejections["declared normalized output digest syntax invalid"], 1)

    def test_production_canary_stays_separate_and_uses_closed_ledger_states(self) -> None:
        canary_root = self.root / "canaries"
        work_units = {
            "architect": "canary-architect-routing-boundary",
            "research-fast": "canary-research-claim-map",
            "review-fast": "canary-review-fast-false-positive",
        }

        def write_validation(
            name: str,
            *,
            role: str,
            candidate: str,
            transport: str,
            comparable: bool,
            conclusion: str | None,
            benchmark_fault: bool = False,
            evidence_state: str = "comparable-but-insufficient",
            false_positives: int | None = None,
            measured_cost: float | None = None,
            first_pass_validity: bool | None = None,
        ) -> None:
            directory = canary_root / name
            directory.mkdir(parents=True)
            artifact = {
                "schemaVersion": 1,
                "evidenceClass": "production-canary-validation",
                "attemptId": name,
                "role": role,
                "requestedCandidate": candidate,
                "transport": transport,
                "servedIdentity": candidate,
                "benchmarkFault": benchmark_fault,
                "faultOwner": "fixture" if benchmark_fault else None,
                "faultCode": "broken-fixture" if benchmark_fault else None,
                "comparable": comparable,
                "identityConfirmed": not benchmark_fault,
                "instrumentationComplete": True,
                "paidCostComplete": True,
                "modelConclusion": conclusion,
                "evidenceState": evidence_state,
                "diagnostics": [],
                "quality": {
                    "firstPassValidity": conclusion == "valid" if first_pass_validity is None else first_pass_validity,
                    "finalValidity": conclusion == "valid",
                    "mandatoryAssertions": [{"id": "strict-json-object", "pass": True}],
                    "usefulFindings": 1 if role.startswith("review-") else None,
                    "falsePositives": false_positives,
                    "correctionCount": 0,
                    "validationAttempts": 1,
                },
                "timing": {
                    "startedAt": "2026-08-29T00:00:00Z",
                    "firstUsefulAt": "2026-08-29T00:00:01Z",
                    "validAt": "2026-08-29T00:00:02Z" if conclusion == "valid" else None,
                    "endedAt": "2026-08-29T00:00:02Z",
                    "timeToFirstUsefulSeconds": 1,
                    "timeToValidSeconds": 2 if conclusion == "valid" else None,
                    "totalDurationSeconds": 2,
                },
                "telemetry": {
                    "toolCallsByClass": {
                        "repositoryRead": 1,
                        "repositoryWrite": 0,
                        "validation": 1,
                        "other": 0,
                    },
                    "tokens": {"input": None, "output": None, "reasoning": None},
                    "contextCoverage": {
                        "applicable": True, "observed": 1, "total": 1,
                        "rate": 1, "reason": "fixture",
                    },
                    "toolCoverage": {
                        "applicable": True, "observed": 1, "total": 1,
                        "rate": 1, "reason": "fixture",
                    },
                },
                "bindings": {
                    "workUnitId": work_units[role],
                    "workUnitRevision": 1,
                    "workUnitDigest": "sha256:" + "a" * 64,
                    "taskFixtureDigest": "sha256:" + "b" * 64,
                    "validationContractDigest": "sha256:" + "c" * 64,
                    "sealedSuiteId": "depot-role-v2",
                    "sealedCaseId": "fixture-case",
                    "sealedCaseDigest": "sha256:" + "d" * 64,
                    "sealedScorerDigest": "sha256:" + "e" * 64,
                    "rolePolicyDigest": "sha256:" + "f" * 64,
                    "pluginVersions": {"openrouter": "1.20.0", "model-router": "0.4.2"},
                },
                "repository": {
                    "identity": "Design-Machines-Studio/depot",
                    "baseRevision": "5" * 40,
                    "headRevision": "5" * 40,
                    "cleanBase": True,
                    "patchDigest": "sha256:" + "0" * 64,
                    "changedFileCount": 0,
                },
                "cost": {
                    "currency": "USD",
                    "maximumBoundUsd": 0.5 if measured_cost is not None else None,
                    "measuredUsd": measured_cost,
                    "receiptCoverage": "measured" if measured_cost is not None else "subscription",
                },
                "artifacts": [{
                    "kind": "diagnostic", "path": "fixture.json",
                    "sha256": "sha256:" + "1" * 64, "bytes": 2,
                }],
            }
            (directory / "canary-validation.json").write_text(json.dumps(artifact))

        for index in range(5):
            write_validation(
                f"paid-{index}", role="research-fast",
                candidate="google/gemini-3.7-flash", transport="openrouter",
                comparable=True, conclusion="valid", measured_cost=0.01,
                first_pass_validity=index < 3,
            )
        write_validation(
            "incompatible", role="research-fast", candidate="gpt-5.6-luna",
            transport="codex-cli", comparable=False, conclusion=None,
            evidence_state="incompatible",
        )
        write_validation(
            "fault", role="architect", candidate="fable", transport="claude-cli",
            comparable=False, conclusion=None, benchmark_fault=True,
            evidence_state="benchmark-faulted",
        )
        write_validation(
            "false-positive", role="review-fast", candidate="deepseek/deepseek-v4-flash-0731",
            transport="openrouter", comparable=True, conclusion="invalid",
            false_positives=1, measured_cost=0.02,
        )

        valid_artifact = json.loads((canary_root / "paid-0" / "canary-validation.json").read_text())
        malformed_variants = {
            "malformed-quality": valid_artifact | {"quality": []},
            "extra-top-level": valid_artifact | {"unexpected": True},
            "contradictory-state": valid_artifact | {
                "benchmarkFault": True,
                "faultOwner": None,
                "faultCode": None,
            },
            "malformed-coverage": valid_artifact | {
                "telemetry": valid_artifact["telemetry"] | {
                    "contextCoverage": {
                        "applicable": True, "observed": 2, "total": 1,
                        "rate": 2, "reason": "invalid",
                    }
                }
            },
        }
        for name, artifact in malformed_variants.items():
            directory = canary_root / name
            directory.mkdir()
            (directory / "canary-validation.json").write_text(json.dumps(artifact))

        output = self.root / "canary-report.json"
        markdown = self.root / "canary-report.md"
        completed = self.run_tool(
            "report", "--run-root", str(self.root / "no-runs"),
            "--benchmark-root", str(self.root / "no-benchmarks"),
            "--canary-root", str(canary_root),
            "--observed-at", "2026-08-29T09:00:00+08:00",
            "--json-output", str(output), "--markdown-output", str(markdown),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report = json.loads(output.read_text())
        canary = report["production_canary"]
        self.assertEqual(report["benchmarks"]["attempts"], 0)
        self.assertEqual(report["production"]["metrics_artifacts"], 0)
        paid = next(group for group in canary["groups"] if group["requested_candidate"] == "google/gemini-3.7-flash")
        self.assertEqual(paid["evidence_state"], "gate-clearing")
        self.assertEqual(paid["valid_attempts"], 5)
        self.assertEqual(paid["first_pass_rate"], 0.6)
        self.assertEqual(paid["coverage"]["input_tokens"], {"recorded": 0, "comparable_attempts": 5, "rate": 0.0})
        review = next(group for group in canary["groups"] if group["role"] == "review-fast")
        self.assertEqual(review["false_positives"], 1)
        self.assertEqual(review["final_valid_rate"], 0)
        self.assertEqual(len(canary["benchmark_faults"]), 1)
        self.assertEqual(len(canary["malformed_artifacts"]), 4)
        self.assertIsNone(canary["benchmark_faults"][0]["model_conclusion"])
        self.assertTrue(all(not row["candidate_order_changed"] for row in canary["routing_ledger"]))
        self.assertEqual(canary["routing_conclusion"], "no routing change justified")
        rendered = markdown.read_text()
        self.assertIn("## Production-canary evidence (separate)", rendered)
        self.assertIn("does not enter sealed v2 aggregates", rendered)


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

    def test_claude_explicit_response_identity_precedes_root_requested_alias(self) -> None:
        expected = {
            "nextChunk": "depot-role-benchmark",
            "executorRole": "builder-fast",
            "executorCapabilities": ["read-repository", "write-repository", "structured-output"],
            "rejectedComplexity": ["Issue #86 Floor observation schemas", "daemon", "generic workflow engine"],
        }
        telemetry = {
            "result": json.dumps(expected, separators=(",", ":")),
            "model": "opus",
            "response": {"model": "claude-opus-5", "provider": "anthropic"},
            "fallbackUsed": False,
            "modelUsage": {
                "claude-haiku-4-5": {"outputTokens": 90, "provider": "anthropic"},
                "claude-opus-5": {"outputTokens": 10, "provider": "anthropic"},
            },
        }
        stub = self.claude_stub("claude-explicit-response-stub", telemetry)
        result_dir = self.root / "claude-explicit-response-result"
        result = self.run_native(
            case="assembly-next-chunk",
            transport="claude-cli",
            model="opus",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(receipt["requestedModel"], "opus")
        self.assertEqual(receipt["responseModel"], "claude-opus-5")
        self.assertEqual(receipt["responseModelProvenance"], "response")
        self.assertEqual(receipt["primaryModelProvenance"], "response")
        self.assertEqual(receipt["primaryModelUsage"]["outputTokens"], 10)
        self.assertEqual(
            [item["model"] for item in receipt["ancillaryModelUsage"]],
            ["claude-haiku-4-5"],
        )
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertTrue(scored["comparable"])
        self.assertTrue(scored["overallSuccess"])
        self.assertEqual(scored["requestedIdentity"], "opus")
        self.assertEqual(scored["servedIdentity"], "claude-opus-5")

    def test_claude_usage_identity_requires_every_output_counter(self) -> None:
        telemetry = {
            "result": "{}",
            "modelUsage": {
                "claude-haiku-4-5": {"provider": "anthropic"},
                "claude-opus-5": {"outputTokens": 10, "provider": "anthropic"},
            },
        }
        stub = self.claude_stub("claude-incomplete-usage-stub", telemetry)
        result_dir = self.root / "claude-incomplete-usage-result"
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
        self.assertEqual(
            receipt["responseModelProvenance"],
            "modelUsage-incomplete-output-counters",
        )
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertFalse(scored["comparable"])
        self.assertIsNone(scored["modelConclusion"])

    def test_codex_split_usage_retains_each_last_reported_counter(self) -> None:
        output = '{"findings":[],"deferred":false}'
        events = [
            {
                "type": "turn.started",
                "model": "gpt-5.6-luna",
                "provider": "openai",
                "fallbackUsed": False,
                "usage": {"input_tokens": 11, "reasoning_output_tokens": 3},
            },
            {
                "type": "usage.updated",
                "usage": {"output_tokens": 20, "cache_write_input_tokens": 7},
            },
            {
                "type": "turn.completed",
                "usage": {"input_usage_count": 13, "cached_input_tokens": 5},
            },
        ]
        event_stream = "\n".join(
            json.dumps(event, separators=(",", ":")) for event in events
        )
        stub = self.codex_stub("codex-split-usage-stub", event_stream, output)
        result_dir = self.root / "codex-split-usage-result"
        result = self.run_native(
            case="review-zero-deferral",
            transport="codex-cli",
            model="gpt-5.6-luna",
            result_dir=result_dir,
            stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(
            receipt["usage"],
            {
                "prompt_tokens": 13,
                "completion_tokens": 20,
                "reasoning_tokens": 3,
                "cache_read_tokens": 5,
                "cache_creation_tokens": 7,
                "cost": None,
            },
        )

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
        self.assertEqual(
            receipt["responseModelProvenance"],
            "modelUsage-unique-max-output-tokens",
        )
        self.assertIsNone(receipt["fallbackUsed"])
        self.assertEqual(receipt["fallbackProvenance"], "not_available")
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertEqual(
            scored["identityStatus"]["provenance"],
            "modelUsage-unique-max-output-tokens",
        )
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

    def test_codex_cross_model_identity_is_not_credited_to_requested_candidate(self) -> None:
        output = '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}'
        event = json.dumps(
            {
                "type": "turn.completed", "model": "gpt-5.6-sol", "provider": "openai",
                "fallbackUsed": False, "usage": {"input_tokens": 20, "output_tokens": 10},
            },
            separators=(",", ":"),
        )
        stub = self.codex_stub("codex-cross-model-stub", event, output)
        result_dir = self.root / "codex-cross-model-result"
        result = self.run_native(
            case="review-zero-deferral", transport="codex-cli", model="gpt-5.6-luna",
            result_dir=result_dir, stub=stub,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads((result_dir / "receipt.json").read_text())
        self.assertEqual(receipt["requestedModel"], "gpt-5.6-luna")
        self.assertEqual(receipt["responseModel"], "gpt-5.6-sol")
        scored = json.loads((result_dir / "result.json").read_text())
        self.assertFalse(scored["comparable"])
        self.assertFalse(scored["overallSuccess"])
        self.assertEqual(scored["failureClass"], "unknown-served-identity")
        self.assertIsNone(scored["modelConclusion"])

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

    def test_contradictory_fallback_telemetry_stays_ambiguous(self) -> None:
        output = '{"findings":[],"deferred":false}'
        event_streams = {
            "false-with-extra-attempt": [
                {
                    "type": "turn.completed",
                    "model": "gpt-5.6-luna",
                    "provider": "openai",
                    "fallbackUsed": False,
                    "attemptedModels": ["gpt-5.6-luna", "gpt-5.6-sol"],
                }
            ],
            "inconsistent-booleans": [
                {
                    "type": "turn.started",
                    "model": "gpt-5.6-luna",
                    "provider": "openai",
                    "fallbackUsed": False,
                },
                {"type": "turn.completed", "fallbackUsed": True},
            ],
        }
        for name, events in event_streams.items():
            with self.subTest(name=name):
                stream = "\n".join(
                    json.dumps(event, separators=(",", ":")) for event in events
                )
                stub = self.codex_stub(f"codex-{name}-stub", stream, output)
                result_dir = self.root / f"codex-{name}-result"
                result = self.run_native(
                    case="review-zero-deferral",
                    transport="codex-cli",
                    model="gpt-5.6-luna",
                    result_dir=result_dir,
                    stub=stub,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                receipt = json.loads((result_dir / "receipt.json").read_text())
                self.assertIsNone(receipt["fallbackUsed"])
                self.assertTrue(receipt["fallbackAmbiguous"])
                self.assertEqual(
                    receipt["fallbackProvenance"], "contradictory-cli-events"
                )
                self.assertEqual(
                    receipt["fallbackReportedValues"],
                    [False] if name == "false-with-extra-attempt" else [False, True],
                )
                if name == "false-with-extra-attempt":
                    self.assertEqual(
                        receipt["attemptedModels"],
                        ["gpt-5.6-luna", "gpt-5.6-sol"],
                    )
                scored = json.loads((result_dir / "result.json").read_text())
                self.assertFalse(scored["comparable"])
                self.assertFalse(scored["overallSuccess"])

    def test_present_wrong_typed_native_telemetry_is_malformed(self) -> None:
        output = '{"findings":[],"deferred":false}'
        codex_base = {
            "type": "turn.completed",
            "model": "gpt-5.6-luna",
            "provider": "openai",
            "fallbackUsed": False,
            "usage": {"input_tokens": 2},
        }
        claude_base = {
            "result": output,
            "response": {"model": "fable", "provider": "anthropic"},
            "fallbackUsed": False,
            "usage": {"input_tokens": 2},
        }
        malformed: list[tuple[str, str, str, dict[str, object]]] = [
            (
                "codex-counter",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "usage": {"input_tokens": "2"}},
            ),
            (
                "codex-identity",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "model": 56},
            ),
            (
                "codex-provider",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "provider": False},
            ),
            (
                "codex-fallback",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "fallbackUsed": "false"},
            ),
            (
                "codex-usage",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "usage": []},
            ),
            (
                "codex-attempts",
                "codex-cli",
                "gpt-5.6-luna",
                {**codex_base, "attemptedModels": "gpt-5.6-luna"},
            ),
            (
                "claude-counter",
                "claude-cli",
                "fable",
                {**claude_base, "usage": {"input_tokens": "2"}},
            ),
            (
                "claude-model-usage-counter",
                "claude-cli",
                "fable",
                {
                    **claude_base,
                    "modelUsage": {"fable": {"outputTokens": "2"}},
                },
            ),
            (
                "claude-identity",
                "claude-cli",
                "fable",
                {
                    **claude_base,
                    "response": {"model": 5, "provider": "anthropic"},
                },
            ),
            (
                "claude-provider",
                "claude-cli",
                "fable",
                {**claude_base, "provider": []},
            ),
            (
                "claude-fallback",
                "claude-cli",
                "fable",
                {**claude_base, "fallbackUsed": 0},
            ),
            (
                "claude-usage",
                "claude-cli",
                "fable",
                {**claude_base, "usage": "missing"},
            ),
            (
                "claude-attempts",
                "claude-cli",
                "fable",
                {**claude_base, "attemptedModels": [5]},
            ),
        ]
        for name, transport, model, telemetry in malformed:
            with self.subTest(name=name):
                stub = (
                    self.codex_stub(
                        f"{name}-stub",
                        json.dumps(telemetry, separators=(",", ":")),
                        output,
                    )
                    if transport == "codex-cli"
                    else self.claude_stub(f"{name}-stub", telemetry)
                )
                result_dir = self.root / f"{name}-result"
                result = self.run_native(
                    case=(
                        "review-zero-deferral"
                        if transport == "codex-cli"
                        else "assembly-next-chunk"
                    ),
                    transport=transport,
                    model=model,
                    result_dir=result_dir,
                    stub=stub,
                )
                self.assertNotEqual(result.returncode, 0)
                receipt = json.loads((result_dir / "receipt.json").read_text())
                self.assertEqual(receipt["outcome"], "failed")
                self.assertEqual(receipt["failureKind"], "malformed-telemetry")
                scored = json.loads((result_dir / "result.json").read_text())
                self.assertFalse(scored["overallSuccess"])
                self.assertIsNone(scored["modelConclusion"])

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
