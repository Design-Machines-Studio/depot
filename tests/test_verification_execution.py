import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests import KERNEL_REFERENCES, schema_matches
from workflow_kernel.repository_verification import derive_verification_plan
from workflow_kernel.verification_execution import (
    execute_selected_lane, parse_go_test_json, repository_doctor_checks,
)
from tests.test_repository_verification import DIGEST, lane, profile, repository


class VerificationExecutionTests(unittest.TestCase):
    def plan(self, profile_value=None, repository_value=None):
        return derive_verification_plan(
            profile_value or profile(), repository_value or repository(),
            changed_paths=["pkg/file.go"], changed_packages=["./pkg"], risk_inputs=[],
            generated_at="2026-07-22T00:00:00Z",
        )

    def test_doctor_reports_each_binding_and_prerequisite(self):
        value = self.plan()
        checks = repository_doctor_checks(value, profile(), repository(), {"tool:git": "available"})
        by_id = {item["id"]: item for item in checks}
        self.assertEqual(by_id["diff_check"]["status"], "pending")
        self.assertEqual(by_id["generator_drift"]["status"], "unavailable")
        self.assertTrue(all(item["status"] == "passed" for item in checks if item["id"] not in {"diff_check", "generator_drift"}))
        changed = repository(); changed["branch"] = "other"
        blocked = repository_doctor_checks(value, profile(), changed, {"tool:git": "missing"})
        by_id = {item["id"]: item for item in blocked}
        self.assertEqual(by_id["branch_worktree_binding"]["status"], "blocked")
        self.assertEqual(by_id["prerequisite:tool:git"]["reason"], "missing")

    def test_go_json_parser_records_packages_failures_coverage_and_malformed(self):
        events = [
            {"Action": "run", "Package": "example/pkg", "Test": "TestOne"},
            {"Action": "fail", "Package": "example/pkg", "Test": "TestOne", "Elapsed": 0.1},
            {"Action": "output", "Package": "example/pkg", "Output": "coverage: 82.5% of statements\n"},
            {"Action": "fail", "Package": "example/pkg", "Elapsed": 0.2},
        ]
        raw = b"\n".join(json.dumps(item).encode() for item in events)
        parsed = parse_go_test_json(raw, command_digest=DIGEST, exit_code=1)
        self.assertEqual(parsed["packages"][0]["status"], "failed")
        self.assertEqual(parsed["packages"][0]["failures"], ["TestOne"])
        self.assertEqual(parsed["packages"][0]["coverage_basis_points"], 8250)
        malformed = parse_go_test_json(raw + b"\n{", command_digest=DIGEST, exit_code=1)
        self.assertEqual((malformed["parser_status"], malformed["parser_reason"]), ("malformed", "malformed_go_json"))
        truncated = parse_go_test_json(raw, command_digest=DIGEST, exit_code=1, max_events=1)
        self.assertEqual(truncated["parser_status"], "truncated")

    def test_execution_uses_bound_lane_and_clean_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "pkg").mkdir()
            profile_value = profile()
            focused = next(item for item in profile_value["lanes"] if item["id"] == "focused")
            focused.update(
                argv=[sys.executable, "-c", "import json; print(json.dumps({'Action':'pass','Package':'example/pkg','Elapsed':0.1}))"],
                workdir=".", prerequisites=[],
            )
            plan = self.plan(profile_value)
            result = execute_selected_lane(
                plan, profile_value, lane_id="focused", repo_root=root,
                current_repository=repository(), prerequisite_states={"tool:git": "available"},
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["packages"][0]["package"], "example/pkg")
            schema = json.loads((KERNEL_REFERENCES / "verification-result-schema.json").read_text())
            self.assertTrue(schema_matches(result, schema))

    def test_stale_profile_remote_lane_missing_tool_and_output_limit_block(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = self.plan()
            changed_profile = profile(); changed_profile["profile_version"] = 2
            blocked = execute_selected_lane(value, changed_profile, lane_id="focused", repo_root=root,
                                            current_repository=repository(), prerequisite_states={"tool:git": "available"})
            self.assertEqual(blocked["status"], "blocked")
            remote_plan = derive_verification_plan(profile(), repository(), changed_paths=[], changed_packages=[],
                                                   risk_inputs=["concurrency"], generated_at="2026-07-22T00:00:00Z")
            remote = execute_selected_lane(remote_plan, profile(), lane_id="race", repo_root=root,
                                           current_repository=repository(), prerequisite_states={"tool:git": "available"})
            self.assertEqual(remote["parser_reason"], "lane_not_runnable")

    def test_output_limit_and_timeout_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command, expected in (
                ([sys.executable, "-c", "print('x' * 10000)"], "output_limit_exceeded"),
                ([sys.executable, "-c", "import time; time.sleep(2)"], "timeout"),
            ):
                value = profile()
                focused = next(item for item in value["lanes"] if item["id"] == "focused")
                focused.update(argv=command, parser="exit-code", prerequisites=[],
                               max_output_bytes=100, timeout_seconds=1)
                plan = self.plan(value)
                result = execute_selected_lane(plan, value, lane_id="focused", repo_root=root,
                                               current_repository=repository(), prerequisite_states={"tool:git": "available"})
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["parser_reason"], expected)


if __name__ == "__main__":
    unittest.main()
