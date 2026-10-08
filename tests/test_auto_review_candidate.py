"""Isolated direct/Pipeline candidate mechanics; no live participant claims."""
import json
import hashlib
import subprocess
import os
import re
import shutil
import tempfile
from pathlib import Path

import unittest
from tests import test_review_closeout as fixture
from workflow_kernel.review_closeout import source_identity


class AutoReviewCandidateTests(unittest.TestCase):
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    make_run = fixture.ReviewCloseoutTests.make_run
    preserve = fixture.ReviewCloseoutTests.preserve
    def exercise_path(self, workflow):
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", str(remote)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "push", "--quiet", "origin", "HEAD:refs/heads/candidate"], check=True)
        run, paths = self.make_run(workflow, "candidate-" + workflow)
        initial = self.preserve(run, paths)
        self.assertEqual("complete", initial["status"])
        # A retained finding is repaired, committed and pushed to an isolated
        # remote. Old source evidence must not become final-head evidence.
        (self.repo / "source.txt").write_text("repaired source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair retained fixture finding"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "push", "--quiet", "origin", "HEAD:refs/heads/candidate"], check=True)
        _, head = source_identity(self.repo)
        remote_head = subprocess.check_output(["git", "-C", str(self.repo), "ls-remote", "origin", "refs/heads/candidate"], text=True).split()[0]
        self.assertEqual(head, remote_head)
        stale = self.preserve(run, paths)
        self.assertEqual("incomplete", stale["status"])
        # Existing sealed inputs stay immutable. Recheck produces fresh owned
        # evidence for the new head rather than relabeling the old receipt.
        recheck, current = self.make_run(workflow, "candidate-recheck-" + workflow)
        final = self.preserve(recheck, current)
        self.assertEqual("complete", final["status"])
        retained = Path(final["evidence_path"])
        self.assertEqual(head, json.loads((retained / "review/request.json").read_text())["source_head"])
        retry = self.preserve(recheck, current)
        self.assertEqual(final["evidence_path"], retry["evidence_path"])
        self.assertEqual("complete", retry["status"])
        # Evidence survives disposable-output cleanup; foreign ignored data in
        # the product checkout is not swept.
        foreign = self.repo / ".foreign-ignored"
        (self.repo / ".git/info/exclude").write_text(".foreign-ignored\n")
        foreign.write_text("another owner's data\n")
        subprocess.run(["git", "-C", str(self.repo), "check-ignore", "--quiet", foreign.name], check=True)
        recheck.finish("succeeded", retain_diagnostics=True)
        self.assertTrue((retained / "review/raw-lane-outputs.json").is_file())
        self.assertTrue(foreign.is_file())

    def test_direct_loop_repair_push_and_final_head_closeout(self):
        self.exercise_path("dm-review-loop")

    def test_pipeline_owner_repair_push_and_final_head_closeout(self):
        self.exercise_path("pipeline")


class ReviewedPRCallerFixtures(unittest.TestCase):
    """Fixture-owner orchestration proof; no installed workflow or live canary.

    Execute the direct/full/Lean source caller seams, using the real production
    producer and disposable production-shaped data. Only git remote projection
    and gh are mocked; no participant or actual PR is claimed.
    """
    make_run = fixture.ReviewCloseoutTests.make_run

    CALLERS = {
        "direct": "plugins/dm-review/skills/review/references/automatic-implementation-closeout.md",
        "full": "plugins/pipeline/agents/workflow/execution-orchestrator.md",
        "lean": "plugins/pipeline/commands/pipeline.md",
    }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publish-reviewed-pr-test.")
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repository"
        self.repo.mkdir()
        self.state = self.root / "runs"
        self.state.mkdir()
        self.source = Path(__file__).resolve().parents[1]
        self.git = shutil.which("git")
        for argv in (
            ["init", "--quiet", "-b", "candidate"],
            ["config", "user.name", "Fixture"],
            ["config", "user.email", "fixture@example.test"],
            ["remote", "add", "origin", "https://github.com/Fixture/consumer.git"],
        ):
            self.git_run(*argv)
        (self.repo / "source.txt").write_text("reviewed source\n")
        (self.repo / ".gitignore").write_text(".workflow-kernel/\n.claude/\n")
        self.git_run("add", ".")
        self.git_run("commit", "--quiet", "-m", "fixture")
        self.log = self.root / "gh.log"
        self.git_log = self.root / "git.log"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.write_tool("git", r'''#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GIT_LOG"
if [ "${3:-}" = ls-remote ]; then
  printf '%s\trefs/heads/candidate\n' "$REMOTE_HEAD"
else exec "$REAL_GIT" "$@"; fi
''')
        self.write_tool("gh", r'''#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GH_LOG"
case "$1 ${2:-}" in
  'pr create') printf 'https://github.com/Fixture/consumer/pull/42\n' ;;
  'pr ready') ;;
  'pr view') jq -cn --arg head "$PR_HEAD" --arg base "${PR_BASE:-main}" '{headRefOid:$head,headRefName:"candidate",baseRefName:$base,state:"OPEN",isDraft:true,reviewDecision:env.REVIEW_DECISION}' ;;
  'pr checks')
    required=false
    for arg in "$@"; do [ "$arg" != --required ] || required=true; done
    if [ "$required" = true ]; then
      case "${REQUIRED_MODE:-checks}" in
        none) printf "no required checks reported on the 'candidate' branch\n" >&2; exit 1 ;;
        lookup-failure) printf 'error connecting to api.github.com\n' >&2; exit 1 ;;
        empty-error) exit 1 ;; empty-success) printf '[]\n'; exit 0 ;;
        diagnostic-extra) printf "no required checks reported on the 'candidate' branch\nlookup failed\n" >&2; exit 1 ;;
        wrong-branch) printf "no required checks reported on the 'foreign' branch\n" >&2; exit 1 ;;
        missing) printf '[{"name":"missing CI","bucket":"pass","link":"https://example.test/missing"}]\n'; exit 0 ;;
      esac
    fi
    case "${ALL_CHECKS_MODE:-checks}" in
      missing) printf '[]\n'; exit 0 ;;
      lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
    esac
    jq -cn --arg bucket "${PR_BUCKET:-pass}" '[{name:"actual CI",bucket:$bucket,link:"https://example.test/ci"}]' ;;

  'api graphql')
    if [[ "$*" = *branchProtectionRule* ]]; then
      [[ "$*" = *"ref=refs/heads/${PR_BASE:-main}"* ]] || exit 2
      case "${CLASSIC_MODE:-checks}" in
        lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
        malformed) printf '{\n'; exit 0 ;;
        incomplete) printf '{"data":{"repository":{"ref":{"name":"main"}}}}\n'; exit 0 ;;
      esac
      jq -cn --arg base "${PR_BASE:-main}" --arg mode "${CLASSIC_MODE:-checks}" '
        {data:{repository:{ref:{name:(if $mode=="wrong-base" then "foreign" else $base end),
          branchProtectionRule:(if $mode=="none" then null else
            {requiresStatusChecks:($mode!="empty"),requiredStatusChecks:(if $mode=="empty" then [] else
              [{context:(if $mode=="absent" then "missing CI" else "actual CI" end),app:(if $mode=="app-bound" then {id:"App1"} else null end)}] end)} end)}}}} |
        if $mode=="partial-error" then .errors=[{message:"not accessible"}] else . end'
    else
      jq -cn --arg head "$PR_HEAD" '{data:{repository:{pullRequest:{headRefOid:$head,reviewThreads:{nodes:[{isResolved:(env.UNRESOLVED!="true")}],pageInfo:{hasNextPage:(env.MORE_THREADS=="true")}}}}}}'
    fi ;;
  'api --paginate')
    BASE_ENCODED="$(jq -rn --arg base "${PR_BASE:-main}" '$base|@uri')"
    [ "$*" = "api --paginate --slurp repos/Fixture/consumer/rules/branches/$BASE_ENCODED?per_page=100" ] || exit 2
    case "${RULES_MODE:-none}" in
      lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
      malformed) printf '{\n'; exit 0 ;;
      incomplete) printf '[[],null]\n'; exit 0 ;;
      none) printf '[[]]\n'; exit 0 ;;
    esac
    jq -cn --arg mode "$RULES_MODE" '
      {type:(if $mode=="workflow" then "workflows" elif $mode=="unknown" then "future_required_rule" else "required_status_checks" end),
        ruleset_id:73,ruleset_source_type:"Organization",ruleset_source:"Fixture",
        parameters:(if $mode=="workflow" then {workflows:[{path:".github/workflows/required.yml",repository_id:42,ref:"refs/heads/main"}]}
          elif $mode=="missing-parameters" then {} else
            {required_status_checks:[{context:(if $mode=="absent" or $mode=="second-page" then "missing CI" else "actual CI" end)}]} |
              if $mode=="app-bound" then .required_status_checks[0].integration_id=123 else . end end)} |
      if $mode=="second-page" then [[],[.]] else [[.]] end' ;;
  *) exit 2 ;;
esac
''')
        self.env = dict(os.environ, DM_REVIEW_DEVELOPMENT_TEST_ROOT=str(self.root),
                        REAL_GIT=self.git, GH_LOG=str(self.log), GIT_LOG=str(self.git_log),
                        DM_REVIEW_BUNDLE_ROOT=str(self.source / "plugins/dm-review"),
                        WORKFLOW_KERNEL=str(self.source / "plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"),
                        REVIEW_ROOT=str(self.repo), REVIEW_PR_URL="https://github.com/Fixture/consumer/pull/42",
                        PR_BUCKET="pass", UNRESOLVED="false", REVIEW_DECISION="APPROVED",
                        TERMINAL_MODEL_REPORT_OWNER="pipeline-run", CALLER_VERIFICATION_PASSED="true")

    def tearDown(self):
        # No agent merge may occur on success, rejection or recovery paths.
        if self.log.exists():
            self.assertNotRegex(self.log.read_text(), r"(?m)^pr merge(?: |$)")
        if self.git_log.exists():
            self.assertNotRegex(self.git_log.read_text(), r" -?merge(?: |$)")
        self.temp.cleanup()

    def git_run(self, *args):
        return subprocess.check_output([self.git, "-C", str(self.repo), *args], text=True).strip()

    def write_tool(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(0o700)

    def prepare(self, caller, suffix="initial"):
        workflow = "dm-review-loop" if caller == "direct" else "pipeline"
        run_id = f"{caller}-initial" if suffix == "exact-replay" else f"{caller}-{suffix}"
        run, paths = self.make_run(workflow, run_id)
        state = self.repo / ".workflow-kernel/runs" / run_id
        state.mkdir(parents=True, exist_ok=True)
        producer = self.root / f"{run_id}-producer.json"
        keys = {"request": "request", "receipts": "receipts", "lane-receipts": "lane_receipts",
                "raw-lane-outputs": "raw_lane_outputs", "raw-findings": "raw_findings",
                "decisions": "decisions", "private-router-directory": "router", "report": "report"}
        producer.write_text(json.dumps({key: str(paths[value]) for key, value in keys.items()}))
        head = self.git_run("rev-parse", "HEAD")
        self.readiness = self.root / f"{run_id}-readiness.json"
        self.facts = {
            "owner": {"repository": "Fixture/consumer", "workflow": workflow, "run_id": run_id,
                      "run_root": str(run.root), "state_dir": str(state)}, "uiNonImpact": None,
            "readiness": {
                "target": "Vetted candidate", "detail": "https://example.test/report", "finalHead": head,
                "dirty": False, "feedbackSettled": False,
                "coverage": {"status": "missing", "head": None, "gaps": [], "requiredBrowserCases": [], "evidence": None},
                "lanes": [{"area": area, "status": "covered" if area == "Security" else "exempt",
                           "note": None if area == "Security" else "Not selected by this bounded fixture.",
                           "evidence": "https://example.test/security" if area == "Security" else None}
                          for area in ("Architecture", "Simplicity", "Security", "Testing", "Fixture/distribution")],
                "findings": [], "checks": [{"name": "candidate tests", "stage": "candidate", "status": "pass", "link": None},
                                           {"name": "actual CI", "stage": "pr", "status": "pending", "link": None}],
                "ui": {"changed": False, "preview": None, "tasks": [], "acceptance": None},
            },
        }
        self.save_facts()
        self.env.update(REVIEW_RUN_ROOT=str(run.root), REVIEW_PRODUCER_INPUT=str(producer),
                        REVIEW_READINESS_INPUT=str(self.readiness), REMOTE_HEAD=head, PR_HEAD=head)
        self.log.write_text("")
        self.git_log.write_text("")
        return run, paths

    def save_facts(self):
        self.readiness.write_text(json.dumps(self.facts))

    def snippet(self, caller, marker):
        text = (self.source / self.CALLERS[caller]).read_text()
        match = re.search(rf"<!-- {marker}:start -->\n```bash\n(.*?)\n```\n<!-- {marker}:end -->", text, re.S)
        self.assertIsNotNone(match, marker)
        return match.group(1)

    def publish(self, caller, operation="create"):
        marker = f"reviewed-pr-{caller}" + ("-ready" if operation == "ready" else "")
        return subprocess.run(["bash", "-euc", self.snippet(caller, marker)],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def reject(self, caller, operation="create", *, no_gh=True):
        self.log.write_text("")
        result = self.publish(caller, operation)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotRegex(self.log.read_text(), r"(?m)^pr (create|ready)(?: |$)")
        if no_gh:
            self.assertEqual("", self.log.read_text())
        return result

    def test_callers_block_pre_review_creation_and_missing_source(self):
        for caller in self.CALLERS:
            with self.subTest(caller=caller):
                run, paths = self.prepare(caller)
                paths["lane_receipts"].unlink()
                rejected = self.reject(caller)
                self.assertIn("required producer validation failed", rejected.stderr)
                self.prepare(caller, "missing-source")
                (self.repo / "source.txt").unlink()
                self.reject(caller)
                self.git_run("restore", "source.txt")

    def test_full_parent_defers_both_operations_until_actual_caller_checks(self):
        # Execute the child guards and the shared Full/Lean parent seams.
        # Producer-valid evidence cannot bypass missing caller verification.
        self.prepare("full")
        self.env["TERMINAL_MODEL_REPORT_OWNER"] = "pipeline"
        for operation in ("create", "ready"):
            child = self.publish("full", operation)
            self.assertEqual(0, child.returncode, child.stderr)
            self.assertIn("Publication deferred", child.stdout)
            self.assertEqual("", self.log.read_text())
            self.env["CALLER_VERIFICATION_PASSED"] = "false"
            self.reject("lean", operation)

        # A caller-discovered defect is committed before publication; covered
        # old HEAD still fails even after the caller passes its new checks.
        (self.repo / "source.txt").write_text("caller-discovered repair\n")
        self.git_run("add", "source.txt")
        self.git_run("commit", "--quiet", "-m", "repair caller verification defect")
        self.env["CALLER_VERIFICATION_PASSED"] = "true"
        self.reject("lean")
        self.prepare("full", "exact-replay")
        # No broad redispatch: fresh producer evidence is an exact-owned replay.
        created = self.publish("lean")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertIn("pr create", self.log.read_text())
        self.env["CALLER_VERIFICATION_PASSED"] = "false"
        self.reject("lean", "ready")
        self.env["CALLER_VERIFICATION_PASSED"] = "true"
        self.facts["readiness"]["feedbackSettled"] = True
        self.save_facts()
        ready = self.publish("lean", "ready")
        self.assertEqual(0, ready.returncode, ready.stderr)
        self.assertIn("pr ready", self.log.read_text())

    def test_standalone_publishes_after_own_checks_and_rejects_unknown_owner(self):
        _, paths = self.prepare("full")
        # Standalone corresponding candidate checks still gate publication.
        self.facts["readiness"]["checks"][0]["status"] = "fail"
        self.save_facts()
        self.reject("full")
        self.facts["readiness"]["checks"][0]["status"] = "pass"
        self.save_facts()
        self.env["TERMINAL_MODEL_REPORT_OWNER"] = "unknown"
        self.reject("full")
        self.env.pop("TERMINAL_MODEL_REPORT_OWNER")
        self.reject("full")
        self.env["TERMINAL_MODEL_REPORT_OWNER"] = "pipeline-run"
        paths["lane_receipts"].unlink()
        self.reject("full")
        self.prepare("full", "standalone-checked")
        created = self.publish("full")
        self.assertEqual(0, created.returncode, created.stderr)
        self.assertIn("pr create", self.log.read_text())
        self.facts["readiness"]["feedbackSettled"] = True
        self.save_facts()
        ready = self.publish("full", "ready")
        self.assertEqual(0, ready.returncode, ready.stderr)
        self.assertIn("pr ready", self.log.read_text())

    def test_candidate_repairs_and_fresh_replay_precede_publication(self):
        for caller in self.CALLERS:
            with self.subTest(caller=caller):
                run, paths = self.prepare(caller)
                preserved = fixture.ReviewCloseoutTests.preserve(self, run, paths)
                self.assertEqual("complete", preserved["status"])
                retained = Path(preserved["evidence_path"])
                original = {p.relative_to(retained): p.read_bytes() for p in retained.rglob("*") if p.is_file()}
                self.facts["readiness"]["findings"] = [{"severity": "P3", "location": "source.txt:1", "problem": "Concrete fixture defect"}]
                self.save_facts()
                self.reject(caller)
                (self.repo / "source.txt").write_text(f"{caller} repaired source\n")
                self.git_run("add", "source.txt")
                self.git_run("commit", "--quiet", "-m", "repair fixture defect")
                self.reject(caller, "ready")  # old review cannot ready the repaired head
                self.prepare(caller, "exact-replay")
                created = self.publish(caller)
                self.assertEqual(0, created.returncode, created.stdout + created.stderr)
                self.assertIn("--draft", self.log.read_text())
                self.assertIn("pr create", self.log.read_text())
                self.assertEqual(original, {p.relative_to(retained): p.read_bytes() for p in retained.rglob("*") if p.is_file()})
                self.env["PR_BUCKET"] = "pending"
                self.reject(caller, "ready", no_gh=False)
                self.env["PR_BUCKET"] = "pass"
                self.env["UNRESOLVED"] = "true"
                self.reject(caller, "ready", no_gh=False)
                self.env["UNRESOLVED"] = "false"
                self.facts["readiness"]["feedbackSettled"] = True
                self.save_facts()
                ready = self.publish(caller, "ready")
                self.assertEqual(0, ready.returncode, ready.stdout + ready.stderr)
                self.assertIn("pr ready", self.log.read_text())

    def test_unchanged_covered_head_unsettled_feedback_does_not_select_reviewers(self):
        # The selector alone would currently ask for broad review on false
        # prFeedbackSettled. Callers must separate that wait before invoking it.
        for caller in self.CALLERS:
            with self.subTest(caller=caller):
                self.prepare(caller)
                self.env.update(SOURCE_COVERAGE_GAP="false", SUPPORTED_RETAINED_FINDING="false",
                                RENDERED_AUTOMATION_GAP="false", REVIEW_ACTION_INPUT=str(self.root / "not-applicable-feedback.json"))
                result = subprocess.run(["bash", "-euc", self.snippet(caller, f"review-gap-{caller}")],
                                        env=self.env, capture_output=True, text=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("without reviewer dispatch", result.stdout)
                self.assertNotIn("modelWork: true", result.stdout)
                self.assertEqual("", self.log.read_text())

    def test_changed_ui_keeps_draft_until_designer_acceptance(self):
        for caller in self.CALLERS:
            with self.subTest(caller=caller):
                self.prepare(caller)
                self.facts["readiness"].update(feedbackSettled=True)
                self.facts["readiness"]["ui"].update(changed=True, preview="https://preview.test", tasks=["Check confirmation."])
                self.save_facts()
                created = self.publish(caller)
                self.assertEqual(0, created.returncode, created.stderr)
                self.reject(caller, "ready", no_gh=False)
                self.facts["readiness"]["ui"]["acceptance"] = {"head": self.env["PR_HEAD"], "unchangedSince": False}
                self.save_facts()
                ready = self.publish(caller, "ready")
                self.assertEqual(0, ready.returncode, ready.stderr)
                self.assertIn("pr ready", self.log.read_text())


class ReviewEvidenceProducerTests(unittest.TestCase):
    """Synthetic CLI lifecycle, distinct from live and installed consumer proof."""
    setUp = fixture.ReviewCloseoutTests.setUp
    tearDown = fixture.ReviewCloseoutTests.tearDown
    preserve = fixture.ReviewCloseoutTests.preserve

    def make_run(self, workflow="dm-review", run_id="closeout", *, synthetic=True, **options):
        return fixture.ReviewCloseoutTests.make_run(self, workflow, run_id, synthetic=synthetic, **options)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + "\n")
        return path

    def prepare(self, lanes=("security",), *, synthetic=True):
        run, paths = self.make_run("dm-review-loop", "producer", synthetic=synthetic)
        request = json.loads(paths["request"].read_text())
        request["required_lanes"] = list(lanes)
        self.write(paths["request"], request)
        paths["receipts"].write_text("[]\n")
        for key in ("lane_receipts", "raw_lane_outputs", "raw_findings", "decisions"):
            paths[key].unlink()
        paths["lanes"] = {}
        original = json.loads(paths["input"].read_text())
        original_companion = json.loads((run.root / "review/companion.json").read_text())
        for lane in lanes:
            value = json.loads(json.dumps(original))
            value["lane"] = value["reviewer"] = lane
            value["literal"]["companion_ref"] = f"review/{lane}-companion.json"
            companion = dict(original_companion, lane=lane, reviewer=lane)
            self.write(run.root / value["literal"]["companion_ref"], companion)
            paths["lanes"][lane] = self.write(run.root / f"review/{lane}-input.json", value)
        return run, paths

    def cli(self, run, paths, input_path, *, test_harness=True):
        import os
        import sys
        from tests import KERNEL_REFERENCES
        return subprocess.run([
            sys.executable, "-m", "workflow_kernel", "assemble-review-evidence",
            "--run-root", str(run.root), "--repository-root", str(self.repo),
            "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
            "--input", str(input_path), *(["--test-harness"] if test_harness else []),
        ], env=dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES)), capture_output=True, text=True, timeout=15)

    def export_cli(self, run, paths, output):
        import os
        import sys
        from tests import KERNEL_REFERENCES
        return subprocess.run([
            sys.executable, "-m", "workflow_kernel", "export-review-contributions",
            "--request", str(paths["request"]), "--receipts", str(paths["receipts"]),
            "--decisions", str(paths["decisions"]), "--raw-findings", str(paths["raw_findings"]),
            "--lane-receipts", str(paths["lane_receipts"]), "--raw-lane-outputs", str(paths["raw_lane_outputs"]),
            "--state-dir", str(run.root), "--output", str(output),
        ], env=dict(os.environ, PYTHONPATH=str(KERNEL_REFERENCES)), capture_output=True, text=True, timeout=15)

    def test_contribution_export_cli_preserves_conflicting_existing_output(self):
        run, paths = self.make_run(run_id="export-conflict")
        output = run.root / "review/contributions.json"
        output.write_text('[{"stage":"foreign-owned-receipt"}]\n')
        before, receipts = output.read_bytes(), paths["receipts"].read_bytes()
        result = self.export_cli(run, paths, output)
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertEqual(before, output.read_bytes())
        self.assertEqual(receipts, paths["receipts"].read_bytes())
        self.assertFalse((run.root / "contribution-inputs").exists())

    def test_contribution_export_cli_serializes_with_authoritative_append(self):
        import fcntl
        from concurrent.futures import ThreadPoolExecutor
        from workflow_kernel.cli import _open_receipt_stream_lock
        run, paths = self.make_run(run_id="export-append")
        before = json.loads(paths["receipts"].read_text())
        value = json.loads(paths["input"].read_text())
        value.update(pass_id="same-source-retry", attempt=2)
        input_path = self.write(run.root / "review/retry-input.json", value)
        # Queue actual CLI processes behind the authoritative stream lock.
        descriptor = _open_receipt_stream_lock(paths["receipts"])
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                exports = [pool.submit(self.export_cli, run, paths, output) for output in
                           (paths["receipts"], run.root / "review/optional-contributions.json")]
                append = pool.submit(self.cli, run, paths, input_path)
                import time
                time.sleep(0.2)
                self.assertTrue(all(not future.done() for future in [*exports, append]))
                self.assertEqual(before, json.loads(paths["receipts"].read_text()))
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                results = [future.result(timeout=20) for future in [*exports, append]]
        finally:
            import os
            os.close(descriptor)
        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)
        final = json.loads(paths["receipts"].read_text())
        self.assertEqual(before, final[:len(before)])
        self.assertEqual(list(range(len(final))), [row["sequence"] for row in final])
        self.assertEqual(2, sum(row["stage"] == "review_lane_evidence" for row in final))
        self.assertEqual(1, sum(row["stage"] == "finding_contribution_coverage" for row in final))
        optional = json.loads((run.root / "review/optional-contributions.json").read_text())
        self.assertEqual(before, optional[:len(before)])
        self.assertEqual(1, sum(row["stage"] == "finding_contribution_coverage" for row in optional))

    def lane(self, run, paths, lane="security", *, test_harness=True):
        result = self.cli(run, paths, paths["lanes"][lane], test_harness=test_harness)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)["record_ref"]

    def coverage(self, run, paths, records, *, test_harness=True, **overrides):
        value = {"schema_version": 1, "operation": "coverage", "run_id": run.run_id,
                 "pass_id": "initial", "selection": [
                     {"lane": lane, "record_ref": record, "history_refs": [], "transition_refs": []}
                     for lane, record in records.items()],
                 "decisions": [], "occurred_at": "2026-09-01T00:02:00Z", "required_case_refs": [], "resolutions": []}
        value.update(overrides)
        path = self.write(run.root / "review/aggregate-input.json", value)
        return self.cli(run, paths, path, test_harness=test_harness)

    def test_zero_findings_cli_completion_retry_and_missing_companion_reconstruction(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(0, result.returncode, result.stderr)
        before = paths["receipts"].read_bytes()
        original_output = (run.root / "raw/security.md").read_bytes()
        retained = json.loads((run.root / record).read_text())["bindings"]["raw/security.md"]["retained_ref"]
        self.assertEqual(original_output, (run.root / retained).read_bytes())
        paths["raw_lane_outputs"].unlink()
        retry = self.coverage(run, paths, {"security": record})
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertTrue(json.loads(retry.stdout)["reused"])
        self.assertEqual(before, paths["receipts"].read_bytes())
        self.assert_synthetic_terminal_rejected(run, paths)

    def assert_synthetic_terminal_rejected(self, run, paths):
        from workflow_kernel.review_closeout import has_preserved_review_evidence
        raw = (run.root / "raw/security.md").read_bytes()
        result = self.preserve(run, paths)
        self.assertEqual("incomplete", result["status"], result)
        self.assertFalse(has_preserved_review_evidence(run.root / "diagnostic"))
        with self.assertRaises(ValueError):
            run.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(raw, (run.root / "raw/security.md").read_bytes())
        return result

    def test_successful_dispatch_cannot_settle_incomplete_inspection(self):
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        value["result"] = {"status": "incomplete", "findings": [], "incomplete_reasons": ["required patch absent"]}
        value["inspected"]["paths"] = []
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode, result.stderr)
        record = json.loads(result.stdout)["record_ref"]
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertEqual(1, len(json.loads(paths["receipts"].read_text())))

    def test_missing_required_input_and_invalid_schema_are_distinct(self):
        run, paths = self.prepare()
        (run.root / "review/prompt.md").unlink()
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode)
        self.assertIn("review/prompt.md", json.loads(result.stdout)["missing"])
        value = json.loads(paths["lanes"]["security"].read_text())
        value["unexpected"] = "malformed"
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(2, result.returncode)
        self.assertEqual("invalid_evidence", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertNotIn(str(run.root), result.stderr)

    def test_absent_required_patch_diagnostic_names_its_safe_path(self):
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        value["requested"]["evidence_refs"].append("review/absent-required.patch")
        value["requested"]["required_evidence_refs"].append("review/absent-required.patch")
        self.write(paths["lanes"]["security"], value)
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(3, result.returncode, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual("incomplete", output["status"])
        self.assertEqual(["review/absent-required.patch"], output["missing"])
        self.assertEqual([{"stage": "lane_input", "reason": "missing_evidence", "path": "review/absent-required.patch"}], output["diagnostics"])

    def test_committed_identity_conflict_and_retained_digest_failure(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        original = paths["receipts"].read_bytes()
        (run.root / "raw/security.md").write_text("different bytes\n")
        result = self.cli(run, paths, paths["lanes"]["security"])
        self.assertEqual(6, result.returncode)
        self.assertEqual(original, paths["receipts"].read_bytes())
        retained = json.loads((run.root / record).read_text())["bindings"]["raw/security.md"]["retained_ref"]
        (run.root / retained).write_text("corruption\n")
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("digest_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])

    def test_concurrent_identical_and_distinct_lane_completions_preserve_sequences(self):
        from concurrent.futures import ThreadPoolExecutor
        run, paths = self.prepare(("security", "patterns"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda lane: self.cli(run, paths, paths["lanes"][lane]), ["security", "patterns", "security", "patterns"]))
        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)
        receipts = json.loads(paths["receipts"].read_text())
        self.assertEqual([0, 1], [row["sequence"] for row in receipts])
        records = {lane: next(row["authoritative_receipt"] for row in receipts if row["lane"] == lane) for lane in ("security", "patterns")}
        result = self.coverage(run, paths, records)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["security", "patterns"], [row["lane"] for row in json.loads(paths["lane_receipts"].read_text())["lanes"]])

    def test_interrupted_seal_before_append_resumes_without_coverage(self):
        from unittest import mock
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        run, paths = self.prepare()
        arguments = dict(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["lanes"]["security"], test_harness=True)
        with mock.patch("workflow_kernel.cli._append_receipts_locked", side_effect=OSError("synthetic interruption")):
            with self.assertRaises(EvidenceAssemblyError):
                assemble_review_evidence(**arguments)
        self.assertEqual([], json.loads(paths["receipts"].read_text()))
        result = assemble_review_evidence(**arguments)
        self.assertEqual("complete", result["status"])
        self.assertEqual(1, len(json.loads(paths["receipts"].read_text())))

    def test_equal_head_does_not_hide_changed_worktree_bytes(self):
        run, paths = self.prepare()
        record = self.lane(run, paths)
        (self.repo / "source.txt").write_text("uncommitted repair\n")
        result = self.coverage(run, paths, {"security": record})
        self.assertEqual(3, result.returncode)
        self.assertEqual("source_scope_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])

    def test_cli_repair_recheck_and_justified_reuse_preserve_history(self):
        self.repair_recheck_reuse(("security", "patterns"))

    def test_synthetic_eight_production_lanes_capacity_lifecycle(self):
        self.repair_recheck_reuse(("code-simplicity", "pattern-recognition", "security", "architecture", "agent-native", "performance", "ai-slop", "second-perspective"), capacity=True)

    def repair_recheck_reuse(self, lanes, *, capacity=False):
        import shutil
        from workflow_kernel.owned_run import ExactOwnedRun
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch, _resolve_snapshot
        (self.repo / "other.txt").write_text("unaffected source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "unaffected fixture source"], check=True)
        if capacity:
            # Real Git inventory and actual fixture diff; outputs/receipts are
            # deliberately synthetic and never live participant proof.
            from workflow_kernel.review_closeout import _document_digest
            _, base = source_identity(self.repo)
            names = [f"plugins/fixture/skills/source/references/{index:04d}-" + "m" * 7 + ".md" for index in range(1157)]
            files = {"source.txt": {"mode": "100644", "oid": "0" * 40}, "other.txt": {"mode": "100644", "oid": "0" * 40}}
            files.update({name: {"mode": "100644", "oid": "0" * 40} for name in names})
            encoded = json.dumps({"head": base, "files": files}, sort_keys=True, separators=(",", ":")).encode()
            extra = 146742 - len(encoded)
            self.assertGreaterEqual(extra, 0)
            # Distribute padding into realistic source path lengths.
            for index, name in enumerate(names):
                padding = extra // len(names) + (index < extra % len(names))
                path = self.repo / (name[:-3] + "m" * padding + ".md")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture metadata source\n")

            subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "synthetic production-sized fixture"], check=True)
            _, base = source_identity(self.repo)
            body = "".join(f"fixture review data {index:05d}\n" for index in range(6000))
            (self.repo / "source.txt").write_text(body)
            from workflow_kernel.review_closeout import _working_patch
            padding = 183933 - len(_working_patch(self.repo, base))
            self.assertGreater(padding, 0)
            (self.repo / "source.txt").write_text(body[:-1] + "x" * padding + "\n")
            subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "large synthetic fixture diff"], check=True)
            _, sized_head = source_identity(self.repo)
            snapshot = _source_snapshot(self.repo, sized_head)
            self.assertEqual(1159, len(snapshot["files"]))
            self.assertEqual(146742, len(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()))
            common_patch = _git_patch(self.repo, base, sized_head)
            self.assertEqual(183933, len(common_patch))
        run, paths = self.prepare(lanes)
        if capacity:
            common_ref = "review/repository-evidence.md"
            common = ("SYNTHETIC TEST HARNESS: complete cached fixture scope.\n" + "\n".join(f"Requirement {index}: inspect fixture source and report supported defects." for index in range(1, 21)) + "\n").encode() + common_patch
            (run.root / common_ref).write_bytes(common)
            for lane in lanes:
                lane_value = json.loads(paths["lanes"][lane].read_text())
                prompt_ref = f"review/{lane}-prompt.md"
                (run.root / prompt_ref).write_text(f"SYNTHETIC TEST HARNESS: {lane}; inspect source.txt and other.txt; read {common_ref} completely.\n")
                lane_value["source"]["base"] = base
                lane_value["requested"]["paths"] = ["source.txt", "other.txt"]
                lane_value["requested"].update(designation="full", evidence_refs=[prompt_ref, common_ref], required_evidence_refs=[prompt_ref, common_ref])
                lane_value["inspected"]["paths"] = ["source.txt", "other.txt"]
                lane_value["provenance"]["source_refs"] = [prompt_ref, common_ref]
                self.write(paths["lanes"][lane], lane_value)
                output_ref = f"raw/{lane}.md"
                dispatch_ref = f"receipts/private/router/{lane}.json"
                lane_value["literal"].update(output_ref=output_ref, dispatch_receipt_ref=dispatch_ref)
                (run.root / output_ref).write_text(f"SYNTHETIC TEST HARNESS: {lane} fixture output.\n")
                self.write(run.root / dispatch_ref, {"schemaVersion": 1, "receiptId": "dispatch-" + hashlib.sha256(lane.encode()).hexdigest()[:24], "requested": {}, "fallback": False, "synthetic_test_harness": True, "served": None, "attempts": []})
                self.write(paths["lanes"][lane], lane_value)
            self.write(paths["router"] / "terminal-receipt-index.json", {"schemaVersion": 1, "receiptFiles": [f"{lane}.json" for lane in lanes]})
        value = json.loads(paths["lanes"]["security"].read_text())
        finding = {"source_finding_id": "fixture-unsafe-source", "reviewer": "security", "lane": "security", "source_severity": "P2", "evidence_ref": "raw/security.md", "finding_path": "source.txt", "finding_anchor": "line=1", "finding_category": "fixture", "finding_root_cause": "fixture source requires repair"}
        value["result"] = {"status": "findings", "findings": [finding], "incomplete_reasons": []}
        self.write(paths["lanes"]["security"], value)
        records = {lane: self.lane(run, paths, lane) for lane in lanes}
        # Host synthesis explicitly supplies the existing decision contract.
        record = json.loads((run.root / records["security"]).read_text())
        companion = json.loads((run.root / "review/security-companion.json").read_text())
        decision = dict(finding, evidence_ref=record["bindings"][finding["evidence_ref"]]["retained_ref"], finding_disposition="retained", agreement="unique", decision_reason_code="retained-unique", attempt=1, occurred_at="2026-09-01T00:02:00Z")
        decision.update({key: companion[key] for key in ("requested_provider", "attempted_provider", "implemented_by", "provider", "model", "implementer_family", "reviewer_family", "resolution_reason")})
        initial = self.coverage(run, paths, records, decisions=[decision])
        self.assertEqual(0, initial.returncode, initial.stderr)
        original_output = (run.root / "raw/security.md").read_bytes()
        before = _resolve_snapshot(run.root, record["source_snapshot"], shared=record["schema_version"] == 2)
        (self.repo / "source.txt").write_text("repaired fixture source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "repair fixture finding"], check=True)
        _, head = source_identity(self.repo)
        after = _source_snapshot(self.repo, head)
        # Same-scope companion replacement is prohibited: use an owned replay,
        # retaining the committed stream and original sealed history.
        replay = ExactOwnedRun.start("dm-review-loop", run.run_id, base=self.state)
        replay.create_path("raw-output", "review")
        replay.create_path("raw-output", "receipts")
        shutil.copytree(run.root / "review", replay.root / "review", dirs_exist_ok=True)
        shutil.copytree(run.root / "receipts", replay.root / "receipts", dirs_exist_ok=True)
        shutil.copytree(run.root / "raw", replay.root / "raw")
        current = {key: replay.root / path.relative_to(run.root) if isinstance(path, Path) and path.is_relative_to(run.root) else path for key, path in paths.items()}
        for key in ("lane_receipts", "raw_lane_outputs", "raw_findings", "decisions"):
            current[key].unlink()
        request = json.loads(current["request"].read_text())
        request["source_head"] = head
        current["request"] = self.write(replay.root / "review/final-request.json", request)
        patch_ref = "review/repair.patch"
        (replay.root / patch_ref).write_bytes(_git_patch(self.repo, before["head"], head))
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": "review/selection.json", "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": [lane for lane in lanes if lane != "security"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
        selection = {"schema_version": 1, "selected_full_set": list(lanes), "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": None}
        if capacity:
            from workflow_kernel.review_closeout import _seal_evidence
            shared_before = {"snapshot_ref": _seal_evidence(replay.root, "source", before)}
            shared_after = {"snapshot_ref": _seal_evidence(replay.root, "source", after)}
            selection.update(schema_version=2, from_source=shared_before, to_source=shared_after)
        self.write(replay.root / "review/selection.json", selection)
        recheck = json.loads(json.dumps(value))
        recheck.update(pass_id="recheck", attempt=2)
        recheck["source"].update(head=head, base=before["head"], request_ref="review/final-request.json")
        recheck["literal"]["output_ref"] = "raw/security-recheck.md"
        (replay.root / "raw/security-recheck.md").write_text("No findings after inspecting the fixture repair.\n")
        recheck["requested"]["evidence_refs"].append(patch_ref)
        recheck["requested"]["required_evidence_refs"].append(patch_ref)
        recheck["result"] = {"status": "no_findings", "findings": [], "incomplete_reasons": []}
        recheck["recheck"] = {"prior_record_ref": records["security"], "selection_ref": "review/selection.json", "repair_refs": [patch_ref]}
        recheck_path = self.write(replay.root / "review/recheck-input.json", recheck)
        result = self.cli(replay, current, recheck_path)
        self.assertEqual(0, result.returncode, result.stderr)
        new_record = json.loads(result.stdout)["record_ref"]
        transition = {"schema_version": 1, "from_source": before, "to_source": after, "changed_paths": ["source.txt"], "patch_ref": patch_ref, "selection_ref": "review/selection.json", "worktree_ref": None}
        if capacity:
            transition.update(schema_version=2, from_source=shared_before, to_source=shared_after)
        self.write(replay.root / "review/reuse.json", transition)
        final_selection = [{"lane": lane, "record_ref": new_record if lane == "security" else records[lane], "history_refs": [records[lane]] if lane == "security" else [], "transition_refs": [] if lane == "security" else ["review/reuse.json"]} for lane in lanes]
        final = self.coverage(replay, current, {}, pass_id="final", selection=final_selection, resolutions=[{"source_finding_id": finding["source_finding_id"], "repair_ref": patch_ref, "verification_record_ref": new_record}])
        self.assertEqual(0, final.returncode, final.stderr)
        result = self.preserve(replay, current)
        self.assertEqual("incomplete", result["status"], result)
        retained = Path(result["evidence_path"])
        self.assertEqual(before["head"], json.loads((retained / records[next(lane for lane in lanes if lane != "security")]).read_text())["input"]["source"]["head"])
        self.assertEqual(original_output, (retained / record["bindings"]["raw/security.md"]["retained_ref"]).read_bytes())
        self.assertEqual([finding], json.loads((retained / records["security"]).read_text())["input"]["result"]["findings"])
        if capacity:
            from workflow_kernel.owned_run import _bounded_diagnostic
            from workflow_kernel.review_closeout import has_preserved_review_evidence
            count, size = _bounded_diagnostic(replay.root / "diagnostic")
            self.assertLessEqual(count, 128)
            self.assertLessEqual(size, 2097152)
            for ref in records.values():
                self.assertEqual((run.root / ref).read_bytes(), (retained / ref).read_bytes())
            retained_record = json.loads((retained / new_record).read_text())
            self.assertEqual(common, (retained / retained_record["bindings"][common_ref]["retained_ref"]).read_bytes())
            self.assertFalse(has_preserved_review_evidence(replay.root / "diagnostic"))
            print(f"SYNTHETIC scaling lifecycle: 8 logical completions + repair/recheck/carry; production INCOMPLETE; 1159 paths; 146742 metadata bytes; {len(common_patch)} actual fixture diff bytes; retained {count}/128 files, {size}/2097152 bytes; original history/output and shared input unchanged; successful cleanup rejected.")
        with self.assertRaises(ValueError):
            replay.finish("succeeded", retain_diagnostics=True)
        self.assertEqual(original_output, (replay.root / "raw/security.md").read_bytes())

    def test_shared_snapshot_missing_tampered_malformed_and_wrong_head_rejected(self):
        from workflow_kernel.review_closeout import _seal_evidence, _seal_record
        for defect in ("missing", "tampered", "malformed", "wrong-head", "unsafe"):
            with self.subTest(defect=defect):
                run, paths = self.prepare()
                ref = self.lane(run, paths)
                record = json.loads((run.root / ref).read_text())
                source_ref = record["source_snapshot"]["snapshot_ref"]
                source_file = run.root / source_ref
                if defect == "missing":
                    source_file.unlink()
                elif defect == "tampered":
                    source_file.write_text('{}\n')
                elif defect == "unsafe":
                    source_file.unlink()
                    source_file.symlink_to(paths["request"])
                else:
                    source = json.loads(source_file.read_text())
                    if defect == "malformed":
                        source["files"]["source.txt"]["mode"] = "invalid"
                    else:
                        source["head"] = "f" * 40
                    record["source_snapshot"] = {"snapshot_ref": _seal_evidence(run.root, "source", source)}
                    ref = _seal_record(run.root, "lane", record)
                    receipts = json.loads(paths["receipts"].read_text())
                    receipts[-1]["authoritative_receipt"] = ref
                    self.write(paths["receipts"], receipts)
                before = paths["receipts"].read_bytes()
                result = self.coverage(run, paths, {"security": ref})
                self.assertEqual(2 if defect == "malformed" else 3, result.returncode, result.stderr)
                self.assertEqual({"missing": "missing_evidence", "tampered": "digest_mismatch", "malformed": "invalid_evidence", "wrong-head": "source_scope_mismatch", "unsafe": "unsafe_path"}[defect], json.loads(result.stderr)["error"]["details"]["reason"])
                self.assertEqual(before, paths["receipts"].read_bytes())

    def test_valid_inline_history_is_retained_without_rewriting(self):
        from unittest import mock
        from workflow_kernel import review_closeout as closeout
        run, paths = self.prepare()
        seal = closeout._seal_record

        def inline(root, role, value):
            value = dict(value)
            if role == "lane":
                value["source_snapshot"] = closeout._resolve_snapshot(root, value["source_snapshot"], shared=True)
                value["schema_version"] = 1
            return seal(root, role, value)

        with mock.patch.object(closeout, "_seal_record", side_effect=inline):
            result = closeout.assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths["request"], receipts_path=paths["receipts"], input_path=paths["lanes"]["security"], test_harness=True)
        ref = result["record_ref"]
        original = (run.root / ref).read_bytes()
        self.assertEqual(1, json.loads(original)["schema_version"])
        self.assertEqual(0, self.coverage(run, paths, {"security": ref}).returncode)
        retained = self.preserve(run, paths)
        self.assertEqual("incomplete", retained["status"])
        self.assertEqual(original, (Path(retained["evidence_path"]) / ref).read_bytes())
        self.assertEqual(ref, self.lane(run, paths))
        with self.assertRaises(ValueError):
            run.finish("succeeded", retain_diagnostics=True)

    def test_terminal_revalidates_shared_snapshot_closure(self):
        from workflow_kernel.review_closeout import has_preserved_review_evidence
        run, paths = self.prepare(synthetic=False)
        ref = self.lane(run, paths, test_harness=False)
        self.assertEqual(0, self.coverage(run, paths, {"security": ref}, test_harness=False).returncode)
        result = self.preserve(run, paths)
        self.assertEqual("complete", result["status"])
        retained = Path(result["evidence_path"])
        source_ref = json.loads((retained / ref).read_text())["source_snapshot"]["snapshot_ref"]
        source_file = retained / source_ref
        original = source_file.read_bytes()
        for bad_bytes in (None, b"{}\n"):
            if bad_bytes is None:
                source_file.unlink()
            else:
                source_file.write_bytes(bad_bytes)
            self.assertFalse(has_preserved_review_evidence(run.root / "diagnostic"))
            source_file.write_bytes(original)
        self.assertTrue(has_preserved_review_evidence(run.root / "diagnostic"))
        run.finish("succeeded", retain_diagnostics=True)

    def test_wrong_patch_symlink_and_hardlink_are_refused_without_append(self):
        import os
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        patch_ref = 'review/required.patch'
        value['requested']['patch_ref'] = patch_ref
        value['requested']['evidence_refs'].append(patch_ref)
        value['requested']['required_evidence_refs'].append(patch_ref)
        self.write(paths['lanes']['security'], value)
        patch = run.root / patch_ref
        patch.write_text('wrong source bytes\n')
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('source_scope_mismatch', json.loads(result.stderr)['error']['details']['reason'])
        self.assertEqual([], json.loads(paths['receipts'].read_text()))
        patch.unlink()
        foreign = self.root / 'foreign.patch'
        foreign.write_text('foreign\n')
        patch.symlink_to(foreign)
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('unsafe_path', json.loads(result.stderr)['error']['details']['reason'])
        patch.unlink()
        os.link(foreign, patch)
        result = self.cli(run, paths, paths['lanes']['security'])
        self.assertEqual(3, result.returncode)
        self.assertEqual('unsafe_path', json.loads(result.stderr)['error']['details']['reason'])
        self.assertEqual('foreign\n', foreign.read_text())

    def test_production_invocation_cannot_settle_synthetic_lane(self):
        run, paths = self.prepare()
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        with self.assertRaises(EvidenceAssemblyError) as caught:
            assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=paths['request'], receipts_path=paths['receipts'], input_path=paths['lanes']['security'])
        self.assertEqual('incomplete_inspection', caught.exception.reason)
        self.assertEqual([], json.loads(paths['receipts'].read_text()))

    def test_test_mode_requires_durable_synthetic_provenance_through_retention(self):
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        for kind in ("live", "recovery"):
            with self.subTest(kind=kind):
                value["provenance"]["kind"] = kind
                self.write(paths["lanes"]["security"], value)
                result = self.cli(run, paths, paths["lanes"]["security"])
                self.assertEqual(3, result.returncode, result.stderr)
                self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
                self.assertEqual([], json.loads(paths["receipts"].read_text()))
                self.assertEqual("incomplete", self.preserve(run, paths)["status"])
        value["provenance"]["kind"] = "synthetic_test"
        self.write(paths["lanes"]["security"], value)
        record = self.lane(run, paths)
        result = self.cli(run, paths, paths["lanes"]["security"], test_harness=False)
        self.assertEqual(3, result.returncode, result.stderr)  # Committed retry also rejects.
        coverage = self.write(run.root / "review/aggregate-input.json", {
            "schema_version": 1, "operation": "coverage", "run_id": run.run_id, "pass_id": "initial",
            "selection": [{"lane": "security", "record_ref": record, "history_refs": [], "transition_refs": []}],
            "decisions": [], "occurred_at": "2026-09-01T00:02:00Z", "required_case_refs": [], "resolutions": [],
        })
        before = paths["receipts"].read_bytes()
        result = self.cli(run, paths, coverage, test_harness=False)
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual(before, paths["receipts"].read_bytes())
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])
        result = self.cli(run, paths, coverage)
        self.assertEqual(0, result.returncode, result.stderr)
        retained = Path(self.preserve(run, paths)["evidence_path"])
        self.assertEqual("synthetic_test", json.loads((retained / record).read_text())["input"]["provenance"]["kind"])
        retained_paths = dict(paths, request=retained / "review/request.json", receipts=retained / "review/authoritative-receipts.json")
        retained_input = self.write(retained / "review/coverage-retry.json", json.loads(coverage.read_text()))
        before = retained_paths["receipts"].read_bytes()
        result = self.cli(run, retained_paths, retained_input, test_harness=False)
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertEqual(before, retained_paths["receipts"].read_bytes())

    def test_production_dispatch_keeps_original_source_for_live_and_recovery(self):
        """Production-shaped fixture receipts; no external participant claims."""
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        original_head = value["source"]["head"]
        companion = json.loads((run.root / value["literal"]["companion_ref"]).read_text())
        dispatch = json.loads((run.root / value["literal"]["dispatch_receipt_ref"]).read_text())
        dispatch.update(served={"model": companion["model"], "provider": companion["provider"], "family": companion["reviewer_family"]},
                        attempts=[{"status": "completed"}], publication={"output": "published"}, transportStub=False)
        self.write(run.root / value["literal"]["dispatch_receipt_ref"], dispatch)
        original_dispatch = (run.root / value["literal"]["dispatch_receipt_ref"]).read_bytes()
        value["provenance"].update(kind="live", executed_at="2026-09-01T00:01:00Z")
        self.write(paths["lanes"]["security"], value)
        initial = self.cli(run, paths, paths["lanes"]["security"], test_harness=False)
        self.assertEqual(0, initial.returncode, initial.stderr)
        original_record = json.loads(initial.stdout)["record_ref"]
        retry = self.cli(run, paths, paths["lanes"]["security"], test_harness=False)
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertTrue(json.loads(retry.stdout)["reused"])
        before = _source_snapshot(self.repo, original_head)
        (self.repo / "source.txt").write_text("actual changed fixture source\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "fixture repair"], check=True)
        _, head = source_identity(self.repo)
        after = _source_snapshot(self.repo, head)
        request = json.loads(paths["request"].read_text())
        request["source_head"] = head
        current = dict(paths, request=self.write(run.root / "review/final-request.json", request))
        receipts_before = paths["receipts"].read_bytes()
        for kind in ("live", "recovery"):
            relabelled = json.loads(json.dumps(value))
            relabelled.update(pass_id="relabelled-" + kind, attempt=2)
            relabelled["source"].update(head=head, base=head, request_ref="review/final-request.json")
            relabelled["provenance"]["kind"] = kind
            result = self.cli(run, current, self.write(run.root / f"review/relabelled-{kind}.json", relabelled), test_harness=False)
            self.assertEqual(3, result.returncode, result.stderr)
            self.assertEqual("source_scope_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])
            self.assertEqual(receipts_before, paths["receipts"].read_bytes())
            self.assertEqual("incomplete", self.preserve(run, current)["status"])
        # Original historical recovery and its identical retry remain valid.
        historical = json.loads(json.dumps(value))
        historical.update(pass_id="historical-recovery", attempt=2)
        historical["provenance"]["kind"] = "recovery"
        historical_path = self.write(run.root / "review/historical-input.json", historical)
        result = self.cli(run, paths, historical_path, test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        historical_record = json.loads(result.stdout)["record_ref"]
        retry = self.cli(run, paths, historical_path, test_harness=False)
        self.assertTrue(json.loads(retry.stdout)["reused"])
        # A distinct original receipt can also be recovered at its historical HEAD.
        dispatch["receiptId"] = "dispatch-" + "b" * 24
        historical["literal"]["dispatch_receipt_ref"] = "receipts/private/router/historical.json"
        self.write(run.root / historical["literal"]["dispatch_receipt_ref"], dispatch)
        historical.update(pass_id="distinct-history", attempt=3)
        result = self.cli(run, paths, self.write(run.root / "review/distinct-history.json", historical), test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        # Current inspection needs a distinct dispatch and explicit predecessor.
        patch_ref, selection_ref = "review/repair.patch", "review/selection.json"
        (run.root / patch_ref).write_bytes(_git_patch(self.repo, original_head, head))
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete",
                     "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref,
                     "selective_rerun": False, "promoted_to_full": False, "full_fanout_override": False,
                     "lanes_rerun": ["security"], "lanes_skipped": [], "rerun_reasons": {"security": ["initial_full_fanout"]}, "selection_fallback_reason": None}
        self.write(run.root / selection_ref, {"schema_version": 1, "selected_full_set": ["security"], "applied": True,
            "iteration": iteration, "finding_owner_lanes": [], "file_trigger_lanes": ["security"],
            "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": None})
        fresh = json.loads(json.dumps(value))
        fresh.update(pass_id="current-recheck", attempt=4)
        fresh["source"].update(head=head, base=original_head, request_ref="review/final-request.json")
        fresh["literal"]["dispatch_receipt_ref"] = "receipts/private/router/current.json"
        dispatch["receiptId"] = "dispatch-" + "c" * 24
        self.write(run.root / fresh["literal"]["dispatch_receipt_ref"], dispatch)
        fresh["recheck"] = {"prior_record_ref": historical_record, "selection_ref": selection_ref, "repair_refs": [patch_ref]}
        fresh["requested"]["evidence_refs"].append(patch_ref)
        fresh["requested"]["required_evidence_refs"].append(patch_ref)
        fresh_path = self.write(run.root / "review/current-input.json", fresh)
        result = self.cli(run, current, fresh_path, test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        fresh_record = json.loads(result.stdout)["record_ref"]
        coverage = self.write(run.root / "review/production-coverage.json", {
            "schema_version": 1, "operation": "coverage", "run_id": run.run_id, "pass_id": "final",
            "selection": [{"lane": "security", "record_ref": fresh_record, "history_refs": [historical_record], "transition_refs": []}],
            "decisions": [], "occurred_at": "2026-09-01T00:04:00Z", "required_case_refs": [], "resolutions": [],
        })
        result = self.cli(run, current, coverage, test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        retained = Path(self.preserve(run, current)["evidence_path"])
        retained_paths = dict(current, request=retained / "review/request.json", receipts=retained / "review/authoritative-receipts.json")
        retained_input = self.write(retained / "review/production-retry.json", fresh)
        result = self.cli(run, retained_paths, retained_input, test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["reused"])
        self.assertEqual(original_dispatch, (run.root / value["literal"]["dispatch_receipt_ref"]).read_bytes())
        self.assertEqual(original_head, json.loads((retained / original_record).read_text())["input"]["source"]["head"])

    def test_production_coverage_rejects_synthetic_predecessor_history(self):
        from workflow_kernel.review_closeout import _source_snapshot
        run, paths = self.prepare()
        self.write_dispatch(run, paths, stub=False)  # Provenance alone must reject.
        synthetic_record = self.lane(run, paths)
        value = json.loads(paths["lanes"]["security"].read_text())
        snapshot = _source_snapshot(self.repo, value["source"]["head"])
        patch_ref, selection_ref = "review/confirmation.patch", "review/confirmation-selection.json"
        (run.root / patch_ref).write_bytes(b"")
        self.write(run.root / selection_ref, {"schema_version": 1, "selected_full_set": ["security"], "applied": True,
            "iteration": {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete",
                          "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref,
                          "selective_rerun": False, "promoted_to_full": False, "full_fanout_override": False,
                          "lanes_rerun": ["security"], "lanes_skipped": [], "rerun_reasons": {"security": ["initial_full_fanout"]}, "selection_fallback_reason": None},
            "finding_owner_lanes": [], "file_trigger_lanes": [], "from_source": snapshot, "to_source": snapshot,
            "changed_paths": [], "patch_ref": patch_ref, "worktree_ref": None})
        companion = json.loads((run.root / value["literal"]["companion_ref"]).read_text())
        value.update(pass_id="production-confirmation", attempt=2)
        value["provenance"].update(kind="live", executed_at="2026-09-01T00:03:00Z")
        value["literal"]["dispatch_receipt_ref"] = "receipts/private/router/confirmation.json"
        self.write(run.root / value["literal"]["dispatch_receipt_ref"], {
            "schemaVersion": 1, "receiptId": "dispatch-" + "d" * 24, "requested": {}, "fallback": False,
            "served": {"model": companion["model"], "provider": companion["provider"], "family": companion["reviewer_family"]},
            "attempts": [{"status": "completed"}], "publication": {"output": "published"}, "transportStub": False})
        value["recheck"] = {"prior_record_ref": synthetic_record, "selection_ref": selection_ref, "repair_refs": [patch_ref]}
        result = self.cli(run, paths, self.write(run.root / "review/confirmation.json", value), test_harness=False)
        self.assertEqual(0, result.returncode, result.stderr)
        record = json.loads(result.stdout)["record_ref"]
        coverage = self.write(run.root / "review/confirmation-coverage.json", {
            "schema_version": 1, "operation": "coverage", "run_id": run.run_id, "pass_id": "final",
            "selection": [{"lane": "security", "record_ref": record, "history_refs": [synthetic_record], "transition_refs": []}],
            "decisions": [], "occurred_at": "2026-09-01T00:04:00Z", "required_case_refs": [], "resolutions": []})
        before = paths["receipts"].read_bytes()
        result = self.cli(run, paths, coverage, test_harness=False)
        self.assertEqual(3, result.returncode, result.stderr)
        self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
        self.assertEqual(before, paths["receipts"].read_bytes())
        self.assertEqual("incomplete", self.preserve(run, paths)["status"])
        # Coverage already sealed by the test-mode assembler stays ineligible.
        self.assertEqual(0, self.cli(run, paths, coverage).returncode)
        self.assert_sealed_production_rejected(run, paths, paths["lanes"]["security"], coverage)

    def assert_sealed_production_rejected(self, run, paths, lane_input, coverage_input):
        """Production retry, coverage, preservation and cleanup all refuse."""
        before = paths["receipts"].read_bytes()
        for path in (lane_input, coverage_input):
            result = self.cli(run, paths, path, test_harness=False)
            self.assertEqual(3, result.returncode, result.stderr)
            self.assertEqual("incomplete_inspection", json.loads(result.stderr)["error"]["details"]["reason"])
            self.assertEqual(before, paths["receipts"].read_bytes())
        self.assert_synthetic_terminal_rejected(run, paths)

    def write_dispatch(self, run, paths, *, stub):
        """Production-shaped fixture dispatch; only `stub` differs."""
        value = json.loads(paths["lanes"]["security"].read_text())
        companion = json.loads((run.root / value["literal"]["companion_ref"]).read_text())
        self.write(run.root / value["literal"]["dispatch_receipt_ref"], {
            "schemaVersion": 1, "receiptId": "dispatch-" + "e" * 24, "requested": {}, "fallback": False,
            "served": {"model": companion["model"], "provider": companion["provider"], "family": companion["reviewer_family"]},
            "attempts": [{"status": "completed"}], "publication": {"output": "published"}, "transportStub": stub})
        return value

    def test_sealed_synthetic_selected_coverage_rejected_by_production(self):
        run, paths = self.prepare()
        self.write_dispatch(run, paths, stub=False)  # Provenance alone must reject.
        record = self.lane(run, paths)
        self.assertEqual(0, self.coverage(run, paths, {"security": record}).returncode)
        self.assert_sealed_production_rejected(run, paths, paths["lanes"]["security"], run.root / "review/aggregate-input.json")

    def test_sealed_old_live_labelled_stub_record_rejected_by_production(self):
        """Synthetic historical bypass fixture, not a live claim: simulates a
        record sealed by older code with a live label over a stub dispatch."""
        from workflow_kernel.review_closeout import _document_digest, _seal_record
        run, paths = self.prepare()
        value = self.write_dispatch(run, paths, stub=True)
        record = json.loads((run.root / self.lane(run, paths)).read_text())
        value["provenance"].update(kind="live", executed_at="2026-09-01T00:01:00Z")
        record.update(input=value, input_digest=_document_digest(value))
        ref = _seal_record(run.root, "lane", record)
        receipts = json.loads(paths["receipts"].read_text())
        receipts[-1]["authoritative_receipt"] = ref
        self.write(paths["receipts"], receipts)
        self.write(paths["lanes"]["security"], value)
        self.assertEqual(0, self.coverage(run, paths, {"security": ref}).returncode)
        self.assert_sealed_production_rejected(run, paths, paths["lanes"]["security"], run.root / "review/aggregate-input.json")

    def test_worktree_inspection_retains_content_and_changed_retry_cannot_relabel_it(self):
        from workflow_kernel.review_closeout import _working_patch
        run, paths = self.prepare()
        (self.repo / 'source.txt').write_text('dirty reviewed source\n')
        value = json.loads(paths['lanes']['security'].read_text())
        value['source']['worktree_ref'] = 'review/worktree.patch'
        (run.root / 'review/worktree.patch').write_bytes(_working_patch(self.repo, value['source']['head']))
        self.write(paths['lanes']['security'], value)
        record_ref = self.lane(run, paths)
        record = json.loads((run.root / record_ref).read_text())
        self.assertEqual(b'dirty reviewed source\n', (run.root / record['source_content']['source.txt']['retained_ref']).read_bytes())
        result = self.coverage(run, paths, {'security': record_ref})
        self.assertEqual(0, result.returncode, result.stderr)
        (self.repo / 'source.txt').write_text('further uncommitted change\n')
        result = self.coverage(run, paths, {'security': record_ref})
        self.assertEqual(3, result.returncode)
        self.assertEqual('source_scope_mismatch', json.loads(result.stderr)['error']['details']['reason'])

    def test_multiple_uncommitted_repairs_validate_history_against_sealed_patches(self):
        lanes = ("security", "patterns")
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _working_patch, _resolve_snapshot
        run, paths = self.prepare(("security", "patterns"))
        records = {lane: self.lane(run, paths, lane) for lane in ("security", "patterns")}
        _, head = source_identity(self.repo)
        snapshots = [_resolve_snapshot(run.root, json.loads((run.root / records["security"]).read_text())["source_snapshot"], shared=True)]
        chain, transitions = [records["security"]], []
        for number in (1, 2):
            (self.repo / "source.txt").write_text(f"uncommitted repair {number}\n")
            snapshots.append(_source_snapshot(self.repo, head, live=True))
            before, after = snapshots[-2], snapshots[-1]
            worktree_ref, patch_ref = f"review/worktree-{number}.patch", f"review/commit-{number}.patch"
            (run.root / worktree_ref).write_bytes(_working_patch(self.repo, head))
            (run.root / patch_ref).write_bytes(b"")
            selection_ref = f"review/selection-{number}.json"
            iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref, "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["security"], "lanes_skipped": [lane for lane in lanes if lane != "security"], "rerun_reasons": {"security": ["a_prior_unresolved_finding", "b_fix_file_trigger"]}, "selection_fallback_reason": None}
            self.write(run.root / selection_ref, {"schema_version": 1, "selected_full_set": list(lanes), "applied": True, "iteration": iteration, "finding_owner_lanes": ["security"], "file_trigger_lanes": ["security"], "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "worktree_ref": worktree_ref})
            transitions.append(f"review/transition-{number}.json")
            self.write(run.root / transitions[-1], {"schema_version": 1, "from_source": before, "to_source": after, "changed_paths": _changed_paths(before, after), "patch_ref": patch_ref, "selection_ref": selection_ref, "worktree_ref": worktree_ref})
            recheck = json.loads(paths["lanes"]["security"].read_text())
            recheck.update(pass_id=f"recheck-{number}", attempt=number + 1)
            recheck["source"]["worktree_ref"] = worktree_ref
            recheck["literal"]["output_ref"] = f"raw/security-recheck-{number}.md"
            (run.root / recheck["literal"]["output_ref"]).write_text(f"No findings after repair {number}.\n")
            recheck["recheck"] = {"prior_record_ref": chain[-1], "selection_ref": selection_ref, "repair_refs": [worktree_ref]}
            result = self.cli(run, paths, self.write(run.root / f"review/recheck-{number}.json", recheck))
            self.assertEqual(0, result.returncode, result.stderr)
            chain.append(json.loads(result.stdout)["record_ref"])
        selection = [{"lane": "security", "record_ref": chain[-1], "history_refs": chain[:-1], "transition_refs": []},
                     {"lane": "patterns", "record_ref": records["patterns"], "history_refs": [], "transition_refs": transitions}]
        # The first dirty repair is no longer live; tampering with its patch must
        # still be caught against the bytes sealed when it was inspected.
        first = run.root / "review/worktree-1.patch"
        sealed = first.read_bytes()
        first.write_bytes(_working_patch(self.repo, head))
        result = self.coverage(run, paths, {}, pass_id="final", selection=selection)
        self.assertEqual(3, result.returncode)
        self.assertEqual("source_scope_mismatch", json.loads(result.stderr)["error"]["details"]["reason"])
        first.write_bytes(sealed)
        result = self.coverage(run, paths, {}, pass_id="final", selection=selection)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_synthetic_terminal_rejected(run, paths)

    def test_nine_lane_pending_two_pass_producer_and_closeout(self):
        """Synthetic 939 -> e605 baseline, then actual e605 -> 64 -> DD."""
        from workflow_kernel.review_closeout import _source_snapshot, _changed_paths, _git_patch, _seal_evidence
        code = ["patterns", "simplicity", "testcoverage", "gobuild"]
        carried = ["security", "architecture", "second"]
        docs = ["docsync", "voice"]
        lanes = code + carried + docs
        doc_paths = ["readiness.md", "receipt.md"]
        voice_paths = doc_paths + ["guide.md"]
        full_paths = ["main_test.go", *voice_paths, "source.txt", "one.txt", "two.txt", "three.txt"]
        for path in full_paths:
            (self.repo / path).write_text("older baseline\n")
        subprocess.run(["git", "-C", str(self.repo), "add", *full_paths], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "synthetic older 939 baseline"], check=True)
        older_base = source_identity(self.repo)[1]
        for path in full_paths:
            (self.repo / path).write_text("original documentation\n")
        subprocess.run(["git", "-C", str(self.repo), "add", *full_paths], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", "synthetic documentation foundation"], check=True)
        run, paths = self.prepare(lanes)
        original_head = source_identity(self.repo)[1]
        originals = {}
        for lane in lanes:
            value = json.loads(paths["lanes"][lane].read_text())
            value["source"]["base"] = older_base
            scope = full_paths if lane == "docsync" else voice_paths if lane == "voice" else ["main_test.go"]
            value["requested"].update(designation="full" if lane == "docsync" else "scoped", paths=scope)
            value["inspected"]["paths"] = scope
            self.write(paths["lanes"][lane], value)
            originals[lane] = self.lane(run, paths, lane)
        original_bytes = {ref: (run.root / ref).read_bytes() for ref in originals.values()}
        before = _source_snapshot(self.repo, original_head)

        def transition(number, before, rerun, skipped, pending, changed):
            for path in changed:
                (self.repo / path).write_text(f"synthetic repair {number}\n")
            subprocess.run(["git", "-C", str(self.repo), "add", *changed], check=True)
            subprocess.run(["git", "-C", str(self.repo), "commit", "--quiet", "-m", f"synthetic repair {number}"], check=True)
            head = source_identity(self.repo)[1]
            after = _source_snapshot(self.repo, head)
            request = json.loads(paths["request"].read_text())
            request["source_head"] = head
            paths["request"] = self.write(run.root / f"review/request-{number}.json", request)
            patch_ref = f"review/patch-{number}.bin"
            (run.root / patch_ref).write_bytes(_git_patch(self.repo, before["head"], head))
            selection_ref = f"review/selection-{number}.json"
            iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": selection_ref, "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": rerun, "lanes_skipped": skipped, "lanes_pending": pending, "rerun_reasons": {lane: ["b_fix_file_trigger"] for lane in rerun}, "selection_fallback_reason": None}
            sources = {"from_source": {"snapshot_ref": _seal_evidence(run.root, "source", before)}, "to_source": {"snapshot_ref": _seal_evidence(run.root, "source", after)}}
            common = dict(schema_version=2, **sources, changed_paths=_changed_paths(before, after), patch_ref=patch_ref, worktree_ref=None)
            selection = dict(common, selected_full_set=lanes, applied=True, iteration=iteration, finding_owner_lanes=pending, file_trigger_lanes=rerun + pending)
            if pending:
                selection["pending_scope_paths"] = {lane: doc_paths for lane in pending}
            self.write(run.root / selection_ref, selection)
            ref = f"review/transition-{number}.json"
            self.write(run.root / ref, dict(common, selection_ref=selection_ref))
            return after, selection_ref, ref

        def recheck(lane, number, selection_ref, pending_refs):
            value = json.loads(paths["lanes"][lane].read_text())
            value.update(pass_id=f"recheck-{number}", attempt=2)
            value["source"].update(head=source_identity(self.repo)[1], base=original_head, request_ref=paths["request"].relative_to(run.root).as_posix())
            scope = doc_paths if lane in docs else ["main_test.go"]
            value["requested"].update(designation="scoped", paths=scope)
            value["inspected"]["paths"] = scope
            output_ref = f"raw/{lane}-{number}.md"
            (run.root / output_ref).write_text(f"Synthetic fresh {lane} judgment at pass {number}.\n")
            value["literal"]["output_ref"] = output_ref
            patch_ref = f"review/{lane}-{number}-cumulative.bin"
            (run.root / patch_ref).write_bytes(_git_patch(self.repo, original_head, value["source"]["head"], value["requested"]["paths"]))
            value["requested"].update(patch_ref=patch_ref)
            value["requested"]["evidence_refs"].append(patch_ref)
            value["requested"]["required_evidence_refs"].append(patch_ref)
            value["inspected"]["basis"] = "patch"
            value["recheck"] = dict(prior_record_ref=originals[lane], selection_ref=selection_ref, repair_refs=[patch_ref], pending_transition_refs=pending_refs)
            path = self.write(run.root / f"review/{lane}-{number}.json", value)
            result = self.cli(run, paths, path)
            self.assertEqual(0, result.returncode, result.stderr)
            return json.loads(result.stdout)["record_ref"], path, value

        middle, first_selection, first_transition = transition(1, before, code, carried, docs, ["main_test.go", *doc_paths])
        current = {lane: recheck(lane, 1, first_selection, [])[0] for lane in code}
        # Pending documentation cannot be carried as skipped, even with CLEAN prose.
        partial = [{"lane": lane, "record_ref": current.get(lane, originals[lane]), "history_refs": [originals[lane]] if lane in code else [], "transition_refs": [] if lane in code else [first_transition]} for lane in lanes]
        result = self.coverage(run, paths, {}, pass_id="unsettled", selection=partial)
        self.assertEqual(3, result.returncode)
        # Selection partition, trigger and overlap invariants fail before append.
        selection_path = run.root / first_selection
        saved_selection = selection_path.read_bytes()
        from workflow_kernel.review_closeout import _validate_selection
        for mutation in ({"lanes_pending": []}, {"lanes_pending": docs + [code[0]]}, {"lanes_skipped": carried + docs, "lanes_pending": []}, {"lanes_pending": docs + ["foreign"]}):
            with self.subTest(mutation=mutation):
                bad = json.loads(saved_selection)
                bad["iteration"].update(mutation)
                self.write(selection_path, bad)
                with self.assertRaises(ValueError):
                    _validate_selection(run.root, first_selection, lanes, before=before, after=middle, repository=self.repo)
        selection_path.write_bytes(saved_selection)
        # Exact pending map, safe unique paths and actual source changes are
        # mechanical requirements; cross-lane path overlap is intentional.
        valid_map = {lane: doc_paths for lane in docs}
        for mapping in (None, {}, {"docsync": doc_paths}, dict(valid_map, patterns=doc_paths),
                        dict(valid_map, foreign=doc_paths), {"docsync": [], "voice": doc_paths},
                        {"docsync": [*doc_paths, "receipt.md"], "voice": doc_paths},
                        {"docsync": ["../receipt.md"], "voice": doc_paths},
                        {"docsync": ["/receipt.md"], "voice": doc_paths},
                        {"docsync": ["guide.md"], "voice": doc_paths}):
            with self.subTest(mapping=mapping):
                bad = json.loads(saved_selection)
                if mapping is None:
                    bad.pop("pending_scope_paths")
                else:
                    bad["pending_scope_paths"] = mapping
                self.write(selection_path, bad)
                with self.assertRaises(ValueError):
                    _validate_selection(run.root, first_selection, lanes, before=before, after=middle, repository=self.repo)
        selection_path.write_bytes(saved_selection)
        final, final_selection, final_transition = transition(2, middle, docs, code + carried, [], ["receipt.md"])
        self.assertEqual(["receipt.md"], _changed_paths(middle, final))
        # A valid skipped/unaffected selection is still invalid in a pending chain.
        from workflow_kernel.review_closeout import _transition_chain
        skipped_doc = json.loads(saved_selection)
        skipped_doc["iteration"].update(lanes_pending=[], lanes_skipped=carried + docs)
        skipped_doc.pop("pending_scope_paths")
        skipped_doc.update(finding_owner_lanes=[], file_trigger_lanes=code)
        self.write(selection_path, skipped_doc)
        with self.assertRaises(ValueError):
            _transition_chain(run.root, [first_transition], before, middle, docs[0], lanes, self.repo, None, pending=True)
        selection_path.write_bytes(saved_selection)
        current_docs = {}
        # A longer pending chain accumulates each actual selection's affected
        # paths, rather than taking only the last transition's scope.
        first_map = json.loads(saved_selection)
        first_map["pending_scope_paths"] = {lane: ["readiness.md"] for lane in docs}
        self.write(selection_path, first_map)
        final_selection_path = run.root / final_selection
        saved_final_selection = final_selection_path.read_bytes()
        next_pending = json.loads(saved_final_selection)
        next_pending["iteration"].update(lanes_rerun=[], lanes_skipped=code + carried, lanes_pending=docs, rerun_reasons={})
        next_pending.update(pending_scope_paths={lane: ["receipt.md"] for lane in docs}, file_trigger_lanes=docs)
        self.write(final_selection_path, next_pending)
        for lane in docs:
            self.assertEqual(set(doc_paths), _transition_chain(run.root, [first_transition, final_transition], before, final, lane, lanes, self.repo, None, pending=True))
        selection_path.write_bytes(saved_selection)
        final_selection_path.write_bytes(saved_final_selection)
        for lane in docs:
            record, input_path, value = recheck(lane, 2, final_selection, [first_transition])
            current_docs[lane] = record
            receipt_bytes = paths["receipts"].read_bytes()
            # Same logical attempt with a changed pending chain is an append conflict.
            value["recheck"]["pending_transition_refs"] = []
            self.write(input_path, value)
            rejected = self.cli(run, paths, input_path)
            self.assertEqual("append_conflict", json.loads(rejected.stderr)["error"]["details"]["reason"])
            self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
            # A fresh attempt cannot omit, reverse, duplicate or carry a pending chain.
            for refs in ([final_transition], [first_transition, final_transition], [first_transition, first_transition]):
                bad = json.loads(json.dumps(value))
                bad.update(pass_id="invalid-pending", attempt=3)
                bad["recheck"]["pending_transition_refs"] = refs
                rejected = self.cli(run, paths, self.write(input_path, bad))
                self.assertEqual(2 if len(refs) != len(set(refs)) else 3, rejected.returncode, rejected.stderr)
                self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
            for mutation in ("wrong_selection", "older_base", "middle_base", "relabelled_source",
                             "requested_readiness", "requested_receipt", "inspected_readiness", "inspected_receipt",
                             "outside_baseline", "wrong_patch"):
                with self.subTest(mutation=mutation):
                    bad = json.loads(json.dumps(value))
                    bad.update(pass_id="invalid-pending-" + mutation, attempt=3)
                    bad["recheck"]["pending_transition_refs"] = [first_transition]
                    if mutation == "wrong_selection":
                        bad["recheck"]["selection_ref"] = first_selection
                    elif mutation in {"older_base", "middle_base"}:
                        bad["source"]["base"] = older_base if mutation == "older_base" else middle["head"]
                        (run.root / bad["requested"]["patch_ref"]).write_bytes(_git_patch(self.repo, bad["source"]["base"], final["head"], doc_paths))
                    elif mutation == "relabelled_source":
                        bad["source"]["head"] = middle["head"]
                    elif mutation.startswith(("requested_", "inspected_")):
                        field, omitted = mutation.split("_")
                        bad[field]["paths"] = [path for path in doc_paths if path != omitted + ".md"]
                        (run.root / bad["requested"]["patch_ref"]).write_bytes(_git_patch(self.repo, original_head, final["head"], bad["requested"]["paths"]))
                        from workflow_kernel.review_closeout import _validate_recheck, _read_source_record
                        with self.assertRaises(ValueError):
                            _validate_recheck(run.root, bad, _read_source_record(run.root, originals[lane], "lane"), final, lanes, self.repo, None)
                    elif mutation == "outside_baseline":
                        if lane != "voice":
                            continue
                        mapped = json.loads(saved_selection)
                        mapped["pending_scope_paths"][lane] = ["main_test.go"]
                        self.write(selection_path, mapped)
                    elif mutation == "wrong_patch":
                        (run.root / bad["requested"]["patch_ref"]).write_bytes(_git_patch(self.repo, middle["head"], final["head"], doc_paths))
                    rejected = self.cli(run, paths, self.write(input_path, bad))
                    self.assertEqual(2 if mutation.startswith("inspected_") else 3, rejected.returncode, rejected.stderr)
                    self.assertEqual(receipt_bytes, paths["receipts"].read_bytes())
                    selection_path.write_bytes(saved_selection)
                    (run.root / bad["requested"]["patch_ref"]).write_bytes(_git_patch(self.repo, original_head, final["head"], doc_paths))
        final_rows = [{"lane": lane, "record_ref": current_docs.get(lane, current.get(lane, originals[lane])), "history_refs": [originals[lane]] if lane in code + docs else [], "transition_refs": [] if lane in docs else [final_transition] if lane in code else [first_transition, final_transition]} for lane in lanes]
        # Neither a partial roster nor an unresolved original judgment can settle.
        self.assertEqual(2, self.coverage(run, paths, {}, pass_id="final", selection=final_rows[:-1]).returncode)
        unresolved = json.loads(json.dumps(final_rows))
        unresolved[-1].update(record_ref=originals[docs[-1]], history_refs=[], transition_refs=[first_transition, final_transition])
        self.assertEqual(3, self.coverage(run, paths, {}, pass_id="final", selection=unresolved).returncode)
        # Sealed pending dependencies remain hash-bound even after lane append.
        transition_path = run.root / first_transition
        saved_transition = transition_path.read_bytes()
        transition_path.write_bytes(saved_transition + b"\n")
        rejected = self.coverage(run, paths, {}, pass_id="final", selection=final_rows)
        self.assertEqual("digest_mismatch", json.loads(rejected.stderr)["error"]["details"]["reason"])
        transition_path.write_bytes(saved_transition)
        altered_map = json.loads(saved_selection)
        altered_map["pending_scope_paths"]["voice"] = ["receipt.md"]
        self.write(selection_path, altered_map)
        rejected = self.coverage(run, paths, {}, pass_id="final", selection=final_rows)
        self.assertEqual("digest_mismatch", json.loads(rejected.stderr)["error"]["details"]["reason"])
        selection_path.write_bytes(saved_selection)
        result = self.coverage(run, paths, {}, pass_id="final", selection=final_rows)
        self.assertEqual(0, result.returncode, result.stderr)
        # Test-mode coverage settles; production preservation stays incomplete.
        preserved = self.assert_synthetic_terminal_rejected(run, paths)
        retained = Path(preserved["evidence_path"])
        for ref, data in original_bytes.items():
            self.assertEqual(data, (retained / ref).read_bytes())
        self.assertEqual(saved_transition, (retained / first_transition).read_bytes())
        self.assertEqual(saved_selection, (retained / first_selection).read_bytes())
        for lane in docs:
            original = json.loads((retained / originals[lane]).read_text())
            self.assertEqual(older_base, original["input"]["source"]["base"])
            self.assertEqual(full_paths if lane == "docsync" else voice_paths, original["input"]["inspected"]["paths"])
        for ref in current_docs.values():
            record = json.loads((retained / ref).read_text())
            self.assertEqual(original_head, record["input"]["source"]["base"])
            self.assertEqual(doc_paths, record["input"]["inspected"]["paths"])
            for binding in record["bindings"].values():
                self.assertEqual(binding["digest"], "sha256:" + hashlib.sha256((retained / binding["retained_ref"]).read_bytes()).hexdigest())
        print("SYNTHETIC pending lifecycle: nine lanes; rerun4/skipped3/pending2 then rerun2/skipped7; original bytes retained; no live Governance claim.")

    def test_pending_optional_fields_leave_original_envelopes_unchanged(self):
        from workflow_kernel.dm_review_adapter import validate_evidence_input, ReviewRequest, translate_review_receipts
        run, paths = self.prepare()
        value = json.loads(paths["lanes"]["security"].read_text())
        original = json.loads(json.dumps(value))
        request = ReviewRequest.from_mapping(json.loads(paths["request"].read_text()))
        validate_evidence_input(value, request)
        self.assertEqual(original, value)
        value["recheck"]["pending_transition_refs"] = []
        validate_evidence_input(value, request)
        value["recheck"]["pending_transition_refs"] = ["review/transition.json"]
        with self.assertRaises(ValueError):
            validate_evidence_input(value, request)
        iteration = {"run_id": run.run_id, "sequence": 0, "stage": "review_iteration", "status": "complete", "occurred_at": "2026-09-01T00:03:00Z", "authoritative_receipt": "review/selection.json", "selective_rerun": True, "promoted_to_full": False, "full_fanout_override": False, "lanes_rerun": ["code"], "lanes_skipped": ["security"], "rerun_reasons": {"code": ["b_fix_file_trigger"]}, "selection_fallback_reason": None}
        translate_review_receipts([iteration])
        self.assertNotIn("lanes_pending", iteration)
        pending = dict(iteration, lanes_pending=["docs"])
        events = translate_review_receipts([pending])
        self.assertEqual(("docs",), events[0].payload["lanes_pending"])
        for lanes_pending in (["code"], ["security"], ["docs", "docs"], None, "docs"):
            with self.subTest(lanes_pending=lanes_pending), self.assertRaises(ValueError):
                translate_review_receipts([dict(iteration, lanes_pending=lanes_pending)])

    def test_interruption_after_append_reconstructs_missing_companions(self):
        from unittest import mock
        from workflow_kernel.review_closeout import assemble_review_evidence, EvidenceAssemblyError
        from workflow_kernel import cli
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        before = paths['receipts'].read_bytes()
        for key in ('lane_receipts', 'raw_lane_outputs', 'raw_findings', 'decisions'):
            paths[key].unlink()
        real_write = cli._write_json
        def interrupted(path, value):
            if Path(path).name == 'raw-lane-outputs.json':
                raise OSError('synthetic post-append interruption')
            return real_write(path, value)
        args = dict(run_root=run.root, repository_root=self.repo, request_path=paths['request'], receipts_path=paths['receipts'], input_path=run.root / 'review/aggregate-input.json', test_harness=True)
        with mock.patch('workflow_kernel.cli._write_json', side_effect=interrupted):
            with self.assertRaises(EvidenceAssemblyError):
                assemble_review_evidence(**args)
        self.assertEqual(before, paths['receipts'].read_bytes())
        result = assemble_review_evidence(**args)
        self.assertTrue(result['reused'])
        self.assertTrue(paths['decisions'].is_file())
        self.assertEqual(before, paths['receipts'].read_bytes())

    def test_unicode_host_extraction_seals_and_reconstructs_byte_identically(self):
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        value['inspected']['limitations'] = ['Static café example; runtime remains outside scope']
        self.write(paths['lanes']['security'], value)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_synthetic_terminal_rejected(run, paths)

    def test_committed_coverage_reconstruction_works_from_retained_scope(self):
        from workflow_kernel.review_closeout import assemble_review_evidence
        run, paths = self.prepare()
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        # Production preservation keeps the synthetic scope as INCOMPLETE
        # diagnostics; only test-mode assembly reconstructs from it below.
        self.assert_synthetic_terminal_rejected(run, paths)
        scope = next((run.root / 'diagnostic/review').iterdir())
        run.finish('failed', retain_diagnostics=True, reason='synthetic report repair', contains='committed source-bound history')
        input_value = json.loads((run.root / 'diagnostic/review' / scope.name / json.loads((scope / 'review/authoritative-receipts.json').read_text())[-1]['authoritative_receipt']).read_text())['input']
        recovery_input = self.write(scope / 'review/reconstructed-input.json', input_value)
        (scope / 'review/raw-lane-outputs.json').unlink()
        result = assemble_review_evidence(run_root=run.root, repository_root=self.repo, request_path=scope / 'review/request.json', receipts_path=scope / 'review/authoritative-receipts.json', input_path=recovery_input, test_harness=True)
        self.assertTrue(result['reused'])
        self.assertTrue((scope / 'review/raw-lane-outputs.json').is_file())
        self.assertEqual(3, len(json.loads((scope / 'review/authoritative-receipts.json').read_text())))

    def test_receipts_preserve_bound_bug_class_execution_and_decision_context(self):
        run, paths = self.prepare()
        request = json.loads(paths['request'].read_text())
        request.update(workflow_class='bug', workflow_class_defaulted=False,
                       execution_mode='codex_native', decision_profile={'uncertainty': 'medium', 'consequence': 'high', 'rationale': 'Source-bound closeout must fail safely'},
                       decision_profile_defaulted=False)
        self.write(paths['request'], request)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        for receipt in json.loads(paths['receipts'].read_text()):
            for field in ('workflow_class', 'workflow_class_defaulted', 'execution_mode', 'decision_profile', 'decision_profile_defaulted'):
                self.assertEqual(request[field], receipt[field])
        self.assert_synthetic_terminal_rejected(run, paths)

    def test_router_public_companion_is_consumed_without_hand_materialized_lane_row(self):
        run, paths = self.prepare()
        value = json.loads(paths['lanes']['security'].read_text())
        private = json.loads((run.root / value['literal']['dispatch_receipt_ref']).read_text())
        private.update(participantId='security', transportStub=True,
                       requested={'role': 'review-deep', 'candidate': {'provider': 'openai'}},
                       served={'provider': 'openai', 'transport': 'codex', 'model': 'gpt-6.1-sol', 'family': 'openai'})
        self.write(run.root / value['literal']['dispatch_receipt_ref'], private)
        public = {'role': 'review-deep', 'capabilities': ['read-repository'], 'requestedEffort': 'high',
                  'normalizedEffort': 'high', 'effectiveEffort': 'high', 'transmittedEffort': 'high',
                  'effortStatus': 'transmitted', 'participantId': 'security', 'disposition': 'completed',
                  'fallback': False, 'evidenceSource': 'fixture', 'transportStub': True,
                  'familyIndependence': {'humanAuthored': False, 'excludedFamilyCount': 0}, 'output': 'raw/security.md'}
        self.write(run.root / value['literal']['companion_ref'], public)
        record = self.lane(run, paths)
        result = self.coverage(run, paths, {'security': record})
        self.assertEqual(0, result.returncode, result.stderr)
        self.assert_synthetic_terminal_rejected(run, paths)
