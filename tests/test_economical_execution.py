"""Offline behavioral cases for the existing Pipeline/router paths. No paid calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "plugins/pipeline/references/select-workflow.sh"
ROUTER = ROOT / "plugins/model-router/skills/model-router/references"
KERNEL = ROOT / "plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"


class WorkflowCases(unittest.TestCase):
    def select(self, **changes):
        data = dict(acceptanceClear=True, designSettled=True, consequence="low",
                    reversibility="easy", coordination="single-pass", existingPattern=True,
                    verificationDefined=True, unansweredQuestions=[], explicitFull=False,
                    reviewRequired=False, securitySensitive=False, minimumMode="direct",
                    rationale="Settled scope with focused behavior proof.")
        data.update(changes)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "assessment.json"
            p.write_text(json.dumps(data))
            result = subprocess.run([str(SELECTOR), str(p)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_typo_config_and_settled_application(self):
        # Same evidence-based assessment for typo/config and settled handler/templ/tests.
        for label in ("typo", "config repair", "Go/Templ/Datastar application and tests"):
            with self.subTest(label=label):
                result = self.select(rationale=label)
                self.assertEqual(result["mode"], "direct")
                self.assertEqual(result["stages"], ["implement", "verify", "deliver"])
                self.assertEqual(result["executorRole"], "builder-fast")
                self.assertFalse(result["independentReview"])
                self.assertEqual(result["verification"], "required")

    def test_bounded_judgment(self):
        result = self.select(consequence="medium")
        self.assertEqual(result["mode"], "lean")
        self.assertTrue(result["independentReview"])
        self.assertEqual(result["researchQuestions"], [])
        self.assertNotIn("targeted-research", result["stages"])

    def test_bounded_factual_question_uses_targeted_lean_research(self):
        result = self.select(unansweredQuestions=["Confirm the installed API spelling."])
        self.assertEqual(result["mode"], "lean")
        self.assertIn("targeted-research", result["stages"])
        self.assertNotIn("applicable-adversary", result["stages"])
        # Once the factual question is resolved, settled execution is eligible.
        self.assertEqual(self.select(minimumMode="lean")["executorRole"], "builder-fast")

    def test_small_authorization_is_consequential(self):
        result = self.select(securitySensitive=True)
        self.assertEqual(result["mode"], "full")
        self.assertEqual(result["executorRole"], "builder-deep")
        self.assertTrue(result["independentReview"])
        self.assertNotIn("targeted-research", result["stages"])

    def test_uncertain_cross_component(self):
        result = self.select(designSettled=False, coordination="ordered",
                             unansweredQuestions=["Which component owns authorization?"])
        self.assertEqual(result["mode"], "full")
        self.assertIn("targeted-research", result["stages"])
        self.assertEqual(len(result["researchQuestions"]), 1)

    def test_explicit_full_keeps_settled_executor(self):
        result = self.select(explicitFull=True)
        self.assertEqual(result["mode"], "full")
        self.assertEqual(result["executorRole"], "builder-fast")

    def test_new_risk_escalates_without_restart_or_downgrade(self):
        result = self.select(consequence="high", minimumMode="lean")
        self.assertEqual(result["mode"], "full")
        self.assertTrue(result["reuseCompletedWork"])
        self.assertEqual(self.select(minimumMode="full")["mode"], "full")

    def test_repository_review_remains_required(self):
        result = self.select(reviewRequired=True)
        self.assertEqual(result["mode"], "direct")
        self.assertTrue(result["independentReview"])


class DispatchCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.router = self.dir / "router"
        shutil.copytree(ROUTER, self.router)
        self.policy = json.loads((self.router / "role-policy.json").read_text())
        self.prompt = self.dir / "prompt.md"
        self.prompt.write_text("Inspect the bounded evidence. Return one finding or CLEAN.")
        self.availability = self.dir / "availability.json"
        self.availability.write_text(json.dumps({"codex": {"state": "ok", "authMode": "subscription"},
                                                "claude": {"state": "ok", "authMode": "subscription", "plan": "max"},
                                                "openrouter": {"state": "ok"}}))
        self.calls = self.dir / "calls.jsonl"
        self.cli = self.dir / "codex"
        self.cli.write_text('''#!/usr/bin/env python3
import json,os,sys
a=sys.argv[1:]
if a[:2]==["features","list"]:
 if os.environ.get("FAST_PROBE_FAILURE")=="1": sys.exit(2)
 if os.environ.get("FAST_UNSUPPORTED")!="1": print("fast_mode stable true")
 sys.exit(0)
if a[:2]==["exec","--help"]: print("--strict-config");sys.exit(0)
model=a[a.index("--model")+1]; out=a[a.index("--output-last-message")+1]
with open(os.environ["CALLS"],"a") as f:f.write(json.dumps(a)+"\\n")
sys.stdin.read()
failure=os.environ.get("FAILURE","")
if model=="gpt-6.1-sol" and os.environ.get("FAIL_PRIMARY_SOL")=="1":
 print(json.dumps({"type":"error","code":"model_not_found","message":"specific model fault"}));sys.exit(1)
if model=="gpt-6-luna" and failure:
 open(out,"w").write("useful partial diagnosis")
 if failure=="quota": print(json.dumps({"type":"error","code":"usage_limit_reached","message":"quota"}))
 elif failure=="transient": print(json.dumps({"type":"error","message":"429 rate limited"}))
 elif failure=="model": print(json.dumps({"type":"error","message":"model unavailable"}))
 elif failure=="fast": print("Fast mode unavailable",file=sys.stderr)
 elif failure=="default": print(json.dumps({"type":"turn.completed","service_tier":"default"}))
 sys.exit(1)
open(out,"w").write("CLEAN")
if os.environ.get("QUOTED_FAST_FAILURE")=="1": print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"Fast mode unavailable; unknown service_tier; quoted source text only"}}))
print(json.dumps({"type":"turn.completed","service_tier":"priority","usage":{"input_tokens":10,"output_tokens":2,"cached_input_tokens":5}}))
''')
        self.cli.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.dir}:{os.environ['PATH']}",
                    "MODEL_ROUTER_TEST_MODE": "1", "MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS": "1",
                    "MODEL_ROUTER_AVAILABILITY_FILE": str(self.availability), "CALLS": str(self.calls)}
        self.index = self.dir / "terminal-receipt-index.json"
        self.index.write_text('{"schemaVersion":1,"receiptFiles":[]}')

    def dispatch(self, name, role="review-fast", **env):
        expected_status = int(env.pop("expected_status", 0))
        receipt = self.dir / f"{name}.json"
        command = [str(self.router / "role-dispatch.sh"), "--role", role,
                   "--capability", "read-repository", "--capability", "tool-use", "--effort", "medium",
                   "--workflow-kernel", str(KERNEL), "--prompt-file", str(self.prompt),
                   "--output-file", str(self.dir / f"{name}.out"), "--receipt-file", str(receipt),
                   "--run-receipt-index", str(self.index)]
        r = subprocess.run(command, env={**self.env, **env}, capture_output=True, text=True)
        self.assertEqual(r.returncode, expected_status, r.stderr)
        result = json.loads(receipt.read_text())
        index = json.loads(self.index.read_text())
        index["receiptFiles"].append(receipt.name)
        self.index.write_text(json.dumps(index))
        return result

    def native_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_every_luna_role_transmits_fast_and_separate_effort(self):
        roles = [role for role, rows in self.policy["roles"].items() if rows[0]["model"] == "gpt-6-luna"]
        self.assertEqual(set(roles), {"builder-fast", "review-fast", "research-fast", "editorial"})
        for role in roles:
            receipt = self.dispatch(role, role)
            self.assertEqual(receipt["served"]["model"], "gpt-6-luna")
            self.assertEqual(receipt["served"]["serviceMode"]["confirmed"], "fast")
        for argv in self.native_calls():
            self.assertIn('service_tier="fast"', argv)
            self.assertIn('model_reasoning_effort="medium"', argv)
            self.assertIn("--strict-config", argv)
            self.assertIn("fast_mode", argv)

    def test_unsupported_fast_selects_eligible_fallback_and_recommendation(self):
        r = self.dispatch("unsupported", FAST_UNSUPPORTED="1")
        self.assertEqual(r["served"]["model"], "gpt-6.1-sol")
        self.assertEqual(r["attempts"][0]["reason"], "fast_mode_unsupported")
        rec = self.recommend(FAST_UNSUPPORTED="1")
        self.assertEqual(rec["recommendedStart"]["model"], r["served"]["model"])
        self.assertEqual(len(self.native_calls()), 1)

    def recommend(self, **env):
        r = subprocess.run([str(self.router / "operator-recommendation.sh"), "--role", "review-fast",
                            "--capability", "read-repository", "--capability", "tool-use", "--effort", "medium",
                            "--matrix-file", str(ROOT / "plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"),
                            "--availability-file", str(self.availability), "--run-receipt-index", str(self.index),
                            "--format", "json"], env={**self.env, **env}, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_fast_unavailable_or_standard_not_silently_accepted(self):
        for failure in ("fast", "default"):
            r = self.dispatch(failure, FAILURE=failure)
            self.assertEqual(r["served"]["model"], "gpt-6.1-sol")
            self.assertEqual(r["attempts"][0]["reason"], "fast_mode_unavailable")

    def test_confirmed_run_failure_is_reused_but_new_run_does_not_inherit(self):
        self.dispatch("quota", FAILURE="quota", expected_status="76")
        # Fixtures are never live evidence. This fixture promotion represents the
        # exact native producer fields and is confined to a disposable test root.
        p = self.dir / "quota.json"
        r = json.loads(p.read_text()); r["probeSource"] = "live"; p.write_text(json.dumps(r))
        self.calls.write_text("")
        # No candidate on the confirmed exhausted native rail may be invoked.
        second = self.dispatch("same-run", expected_status="76")
        self.assertTrue(all(x.get("reusedFailure") for x in second["attempts"]))
        self.assertEqual(self.calls.read_text(), "")
        self.assertIsNone(second["served"])
        cmd = ['bash', '-c', 'source "$1"; RUN_RECEIPT_INDEX="$2"; load_run_failures; run_failure_reason codex-cli gpt-6.1-sol', '_',
               str(self.router / "run-availability.sh"), str(self.index)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "rate_limit_exhausted")
        self.index.write_text('{"schemaVersion":1,"receiptFiles":[]}')
        self.assertEqual(self.dispatch("new-run")["served"]["model"], "gpt-6-luna")

    def test_transient_is_not_confirmed_and_partial_output_survives(self):
        r = self.dispatch("transient", FAILURE="transient")
        self.assertEqual(r["attempts"][0]["failureScope"], "transient")
        self.assertFalse(r["attempts"][0]["failureConfirmed"])
        self.assertEqual((self.dir / r["attempts"][0]["partialOutput"]).read_text(), "useful partial diagnosis")
        p = self.dir / "transient.json"; r["probeSource"] = "live"; p.write_text(json.dumps(r))
        self.assertEqual(self.dispatch("retry")["served"]["model"], "gpt-6-luna")

    def test_luna_fallback_requests_fast(self):
        rows = self.policy["roles"]["review-fast"]
        rows[0], rows[1] = rows[1], rows[0]
        (self.router / "role-policy.json").write_text(json.dumps(self.policy))
        r = self.dispatch("luna-fallback", FAIL_PRIMARY_SOL="1")
        self.assertEqual(r["served"]["model"], "gpt-6-luna")
        self.assertEqual(r["attempts"][0]["failureScope"], "model")
        self.assertEqual(r["served"]["serviceMode"]["transmitted"], "fast")
        self.assertIn('service_tier="fast"', self.native_calls()[-1])

    def test_model_and_credential_failures_reuse_only_confirmed_scope(self):
        # Validate scope application through the same helper used by both real
        # dispatch and recommendations; every prior row is live-shaped test data.
        for scope, reason in (("rail", "provider_credential_unavailable"),
                              ("rail", "insufficient_credits"),
                              ("rail", "organization_monthly_budget_exceeded"),
                              ("model", "provider_model_unavailable")):
            prior = self.dir / "prior.json"
            prior.write_text(json.dumps({"schemaVersion": 1, "probeSource": "live", "transportStub": False,
                "attempts": [{"model": "specific/model", "transport": "openrouter", "outcome": "failed",
                              "reason": reason, "failureScope": scope, "failureConfirmed": True}]}))
            self.index.write_text(json.dumps({"schemaVersion": 1, "receiptFiles": [prior.name]}))
            cmd = ["bash", "-c", 'source "$1"; RUN_RECEIPT_INDEX="$2"; load_run_failures; run_failure_reason openrouter other/model',
                   "_", str(self.router / "run-availability.sh"), str(self.index)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), reason if scope == "rail" else "")
            # Unsupported/malformed diagnosis never poisons another lane.
            r = json.loads(prior.read_text()); r["attempts"][0]["failureConfirmed"] = False
            prior.write_text(json.dumps(r))
            self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).stdout.strip(), "")

    def test_probe_failure_does_not_become_confirmed_exclusion(self):
        r = self.dispatch("probe-fault", FAST_PROBE_FAILURE="1")
        self.assertEqual(r["attempts"][0]["reason"], "fast_mode_probe_unavailable")
        self.assertFalse(r["attempts"][0]["failureConfirmed"])
        self.assertEqual(r["attempts"][0]["failureScope"], "infrastructure")
        p = self.dir / "probe-fault.json"; r["probeSource"] = "live"; p.write_text(json.dumps(r))
        self.assertEqual(self.dispatch("probe-recovered")["served"]["model"], "gpt-6-luna")

    def test_successful_quoted_fast_error_is_not_provider_diagnosis(self):
        r = self.dispatch("quoted-source", QUOTED_FAST_FAILURE="1")
        self.assertEqual(r["served"]["model"], "gpt-6-luna")
        self.assertEqual(r["served"]["serviceMode"]["confirmed"], "fast")
        self.assertEqual(len(self.native_calls()), 1)

    def test_cached_primary_skip_keeps_fallback_reporting(self):
        r = self.dispatch("closed-fast", FAST_UNSUPPORTED="1")
        p = self.dir / "closed-fast.json"; r["probeSource"] = "live"; p.write_text(json.dumps(r))
        next_result = self.dispatch("cached-fast")
        self.assertEqual(next_result["served"]["model"], "gpt-6.1-sol")
        self.assertTrue(next_result["fallback"])
        self.assertTrue(next_result["attempts"][0]["reusedFailure"])
        self.assertEqual(next_result["fallbackReason"], "fast_mode_unsupported")

    def test_unsafe_index_is_rejected(self):
        self.index.write_text('{"schemaVersion":1,"receiptFiles":["../foreign.json"]}')
        result = subprocess.run(["bash", "-c", 'source "$1"; RUN_RECEIPT_INDEX="$2"; load_run_failures', "_",
                                 str(self.router / "run-availability.sh"), str(self.index)], capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_recommendation_matches_actual_fast_dispatch(self):
        rec = self.recommend()
        r = self.dispatch("parity")
        self.assertEqual(rec["recommendedStart"]["model"], r["served"]["model"])
        self.assertEqual(rec["recommendedStart"]["serviceMode"], "fast")

    def test_judgment_starts_on_sol_and_keeps_design_specialist(self):
        for role in ("architect", "plan-critic", "review-deep", "builder-deep"):
            self.assertEqual(self.dispatch(role, role)["served"]["model"], "gpt-6.1-sol")
        self.assertEqual(self.policy["roles"]["design-consultant"][0]["model"], "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main()
