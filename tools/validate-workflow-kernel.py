#!/usr/bin/env python3
"""Offline behavioral validator for the neutral workflow kernel."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "plugins" / "workflow-kernel" / "skills" / "workflow-kernel" / "references"
TESTS = REFERENCES / "tests"
SCENARIOS = TESTS / "fixtures" / "scenarios"
RECEIPTS = TESTS / "fixtures" / "receipts"
PERSONAS = TESTS / "fixtures" / "ux" / "assembly"
SECTIONS = (
    "canonical runtime", "JSON schemas and policy", "unittest suite",
    "scenario replay", "state reconstruction and event ordering",
    "terminal cleanup", "Docker cleanup safety", "secret leakage",
    "host compatibility", "promotion and shadow default",
    "runtime CLI commands", "workflow classes", "persona layouts",
)
SECRET_SENTINEL = "sk-fixture-persona-password-must-not-survive"
DEFAULT_EVIDENCE_OUTPUT = (
    ROOT / "plans" / "ai-developer-workflow-kernel" / "receipts" /
    "06-workflow-kernel-release-evidence.json"
)
PROMOTION_CHECK_SOURCES = {
    "zero_unexplained_receipt_gaps": ("host compatibility",),
    "illegal_transition_scenarios_passed": (
        "scenario replay", "state reconstruction and event ordering",
    ),
    "terminal_cleanup_scenarios_passed": ("scenario replay", "terminal cleanup"),
    "host_fixture_claude_passed": ("host compatibility",),
    "host_fixture_codex_passed": ("host compatibility",),
    "host_fixture_generic_passed": ("host compatibility",),
    "persona_completeness_scenarios_passed": ("scenario replay",),
    "browser_recovery_scenarios_passed": ("scenario replay",),
    "provider_security_boundaries_unchanged": ("scenario replay",),
}
BEHAVIORAL_CLI_CASES = {
    "init": ("<run>", "--run-id", "validator-cli", "--occurred-at", "2026-07-14T00:00:00Z"),
    "validate": ("<run>",),
    "append": ("<run>", "--event", "<event>"),
    "replay": ("<run>",),
    "status": ("<run>",),
    "bind-prediction": ("--type", "pipeline", "--manifest", "<missing>", "--prediction-receipts", "<missing>", "--state-dir", "<state>"),
    "observe-pipeline": ("--manifest", "<missing>", "--receipts", "<missing>", "--state-dir", "<state>"),
    "observe-review": ("--request", "<missing>", "--receipts", "<missing>", "--state-dir", "<state>"),
    "compare": ("--state-dir", "<state>", "--authoritative-receipts", "<missing>", "--output", "<output>"),
    "metrics": ("--events", "<missing>", "--output", "<output>"),
    "plan-create": ("--state-dir", "<state>", "--run-id", "validator-cli", "--node-id", "node", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", "<missing>", "--output", "<output>"),
    "plan-compose": ("--state-dir", "<state>", "--run-id", "validator-cli", "--node-id", "node", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove", "--argv-json", "<missing>", "--output", "<output>"),
    "record-create": ("--state-dir", "<state>", "--plan", "<missing>", "--result", "<missing>", "--before-inventory", "<missing>", "--after-inventory", "<missing>"),
    "plan-cleanup": ("--state-dir", "<state>", "--run-id", "validator-cli", "--node-id", "node", "--output", "<output>"),
    "next-cleanup-step": ("--state-dir", "<state>", "--plan", "<missing>", "--outcomes", "<missing>", "--output", "<output>"),
    "execute-cleanup-step": ("--state-dir", "<state>", "--plan", "<missing>", "--step-index", "0", "--inventory", "<missing>", "--node-statuses", "<missing>", "--outcomes", "<missing>", "--output", "<output>"),
    "record-cleanup": ("--state-dir", "<state>", "--plan", "<missing>", "--outcomes", "<missing>"),
    "plan-reconcile": ("--state-dir", "<state>", "--run-id", "validator-cli", "--output", "<output>"),
}
SUCCESSFUL_CLI_COMMANDS = frozenset(BEHAVIORAL_CLI_CASES)

sys.path.insert(0, str(REFERENCES))


class ValidationFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationFailure(message)


def safe_failure_text(error):
    """Return correlation-only failure text without republishing raw output."""
    raw = str(error).encode("utf-8", errors="replace")
    return "value-sha256:" + hashlib.sha256(raw).hexdigest()


def deterministic_env():
    result = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": str(REFERENCES),
        "PYTHONHASHSEED": "0", "TZ": "UTC", "LANG": "C", "LC_ALL": "C",
    }
    for name in ("HOME", "TMPDIR"):
        if name in os.environ:
            result[name] = os.environ[name]
    return result


def run(command):
    return subprocess.run(
        command, cwd=ROOT, env=deterministic_env(), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def check_canonical_runtime(context):
    from workflow_kernel.cli import resolve_workflow_kernel_runtime
    resolved = resolve_workflow_kernel_runtime(ROOT / "plugins" / "pipeline")
    require(resolved == REFERENCES.resolve(), "canonical runtime did not resolve first")
    require((resolved / "workflow_kernel" / "__main__.py").is_file(), "runtime entrypoint missing")


def _resolve_pointer(document, pointer):
    current = document
    for raw in pointer.lstrip("#/").split("/") if pointer != "#" else ():
        key = raw.replace("~1", "/").replace("~0", "~")
        require(type(current) is dict and key in current, "unresolved local schema reference")
        current = current[key]


def check_documents(context):
    from workflow_kernel.policies import load_policy
    from workflow_kernel.workflows import WorkflowTemplates
    schemas = sorted(REFERENCES.glob("*-schema.json"))
    require(len(schemas) == 7, "unexpected schema document count")
    for path in schemas:
        document = json.loads(path.read_text(encoding="utf-8"))
        require(type(document) is dict, f"{path.name} is not an object")
        require(document.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{path.name} draft mismatch")
        require(type(document.get("$id")) is str and document["$id"], f"{path.name} id missing")
        def visit(value):
            if type(value) is dict:
                reference = value.get("$ref")
                if type(reference) is str and reference.startswith("#"):
                    _resolve_pointer(document, reference)
                for child in value.values():
                    visit(child)
            elif type(value) is list:
                for child in value:
                    visit(child)
        visit(document)
    load_policy(REFERENCES / "workflow-policy.json")
    WorkflowTemplates(REFERENCES / "workflow-classes.json")
    context["schema_documents"] = [path.name for path in schemas]


def check_unittests(context):
    command = [
        sys.executable, "-m", "unittest", "discover", "-s", str(TESTS),
        "-t", str(REFERENCES), "-p", "test_*.py",
    ]
    completed = run(command)
    require(
        completed.returncode == 0,
        safe_failure_text(completed.stderr or "unittest failed"),
    )
    context["unittest_summary"] = completed.stderr.strip().splitlines()[-1]


def check_scenarios(context):
    from tests.test_failure_scenarios import load_suites, replay
    scenarios = [scenario for suite in load_suites() for scenario in suite["scenarios"]]
    require(scenarios, "scenario matrix empty")
    for scenario in scenarios:
        require(replay(scenario) == scenario["expected"], f"scenario mismatch: {scenario['id']}")
    context["scenario_count"] = len(scenarios)
    context["scenario_ids"] = [scenario["id"] for scenario in scenarios]


def check_state(context):
    from workflow_kernel.schema import SequenceConflictError, WorkflowEvent
    from workflow_kernel.transitions import TransitionEngine
    events = (
        WorkflowEvent(1, 0, "validator-run", None, "run.initialized", "2026-07-14T00:00:00Z", {}),
        WorkflowEvent(1, 1, "validator-run", None, "run.started", "2026-07-14T00:00:01Z", {}),
    )
    state = TransitionEngine().reconstruct(events)
    require(state.revision == 2 and state.status.value == "running", "state reconstruction mismatch")
    gap = WorkflowEvent(1, 2, "validator-run", None, "run.started", "2026-07-14T00:00:02Z", {})
    try:
        TransitionEngine().reconstruct((events[0], gap))
    except SequenceConflictError:
        pass
    else:
        raise ValidationFailure("gapped event accepted")


def check_terminal_cleanup(context):
    from tests.test_failure_scenarios import load_suites
    scenarios = [scenario for suite in load_suites() for scenario in suite["scenarios"]]
    terminal = {"succeeded", "failed", "blocked", "cancelled", "interrupted"}
    require(all(
        scenario["expected"]["cleanup_invocations"] == 1
        for scenario in scenarios if scenario["expected"]["final_state"] in terminal
    ), "terminal path skipped or repeated cleanup")
    required = {"success", "failure", "blocked", "cancelled", "interrupted"}
    require(required <= {scenario["id"] for scenario in scenarios}, "terminal outcomes incomplete")


def _literal_tokens(node):
    return tuple(
        child.value.lower()
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    )


def docker_safety_violations_from_source(name, source):
    violations = []
    tree = ast.parse(source, filename=name)
    for node in ast.walk(tree):
        tokens = _literal_tokens(node)
        joined = " ".join(" ".join(token.split()) for token in tokens)
        docker_prune = (
            "docker" in tokens and "prune" in tokens
        ) or any(
            phrase in joined for phrase in (
                "docker system prune", "docker container prune",
                "docker network prune", "docker volume prune",
            )
        )
        if docker_prune or "label!=" in joined:
            violations.append(f"{name}:{getattr(node, 'lineno', 0)}:broad-prune")
        if isinstance(node, ast.Call):
            function = node.func
            shell_builder = (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "os"
                and function.attr in {"system", "popen"}
                and "docker" in joined
            )
            shell_true = any(
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
            if shell_builder:
                violations.append(f"{name}:{node.lineno}:shell-built-command")
            if shell_true:
                violations.append(f"{name}:{node.lineno}:shell-true")
    return tuple(sorted(set(violations)))


def check_docker_safety(context):
    violations = []
    for path in sorted((REFERENCES / "workflow_kernel").rglob("*.py")):
        violations.extend(docker_safety_violations_from_source(
            path.name, path.read_text(encoding="utf-8"),
        ))
    require(not violations, ", ".join(violations))


def check_secrets(context):
    from tests.test_failure_scenarios import load_suites, replay
    rendered = json.dumps(
        [replay(scenario) for suite in load_suites() for scenario in suite["scenarios"]],
        sort_keys=True,
    )
    require(SECRET_SENTINEL not in rendered, "secret sentinel leaked from scenario output")


def check_hosts(context):
    from workflow_kernel.pipeline_adapter import translate_pipeline_receipts
    from workflow_kernel.shadow import ReceiptSet, ShadowComparator
    sets = {}
    for host in ("claude", "codex", "generic"):
        document = json.loads((RECEIPTS / f"pipeline-{host}.json").read_text(encoding="utf-8"))
        sets[host] = ReceiptSet.from_events(translate_pipeline_receipts(document))
    results = {}
    for host in ("codex", "generic"):
        report = ShadowComparator().compare_receipt_sets(sets[host], sets["claude"])
        require(report.semantic_match and not report.safe_to_promote, f"{host} compatibility mismatch")
        results[host] = report.reason
    context["host_compatibility"] = {"claude": "reference", **results}


def derive_promotion_evidence(completed_checks):
    from workflow_kernel.promotion import EvidenceOrigin, PromotionEvidence
    return tuple(
        PromotionEvidence(
            criterion,
            all(completed_checks.get(name, False) for name in sources),
            EvidenceOrigin.FIXTURE,
        )
        for criterion, sources in PROMOTION_CHECK_SOURCES.items()
    )


def check_promotion(context):
    from workflow_kernel.promotion import (
        ENFORCE_CRITERIA, EvidenceOrigin, NATIVE_CRITERIA, PromotionEvidence,
        evaluate_promotion,
    )
    from workflow_kernel.schema import RunMode
    require(RunMode.SHADOW.value == "shadow", "default mode is not shadow")
    from workflow_kernel.cli import parser as runtime_parser
    parsed = runtime_parser().parse_args([
        "init", "/offline", "--run-id", "validator", "--occurred-at",
        "2026-07-14T00:00:00Z",
    ])
    require(parsed.mode == "shadow", "runtime CLI default is not shadow")
    fixture = derive_promotion_evidence(context.get("completed_checks", {}))
    require(
        tuple(item.criterion for item in fixture) == ENFORCE_CRITERIA,
        "promotion criterion sources drifted",
    )
    enforce = evaluate_promotion("shadow", "enforce_available", fixture)
    require(enforce.allowed, "complete shadow fixture criteria rejected")
    native_fixture = fixture + tuple(
        PromotionEvidence(name, True, EvidenceOrigin.FIXTURE) for name in NATIVE_CRITERIA
        if name not in ENFORCE_CRITERIA
    )
    native = evaluate_promotion("enforce_available", "native_available", native_fixture)
    require(not native.allowed and all(name.startswith("real_shadow_run:") for name in native.missing_evidence), "fixture masqueraded as real-run evidence")
    default = evaluate_promotion("native_available", "native_default", ())
    require(default.reason_codes == ("separate_human_approval_required",), "native default was not blocked")
    context["promotion"] = {
        "shadow_to_enforce_fixture": enforce.to_dict(),
        "enforce_to_native_fixture": native.to_dict(),
        "native_to_default": default.to_dict(),
    }
    context["promotion_criteria"] = [
        {
            "criterion": item.criterion, "satisfied": item.satisfied,
            "origin": item.origin.value,
            "sources": list(PROMOTION_CHECK_SOURCES[item.criterion]),
        }
        for item in fixture
    ]


def check_cli(context):
    from workflow_kernel import cli
    expected = {
        "init", "validate", "append", "replay", "status", "bind-prediction",
        "observe-pipeline", "observe-review", "compare", "metrics", "plan-create",
        "plan-compose", "record-create", "plan-cleanup", "next-cleanup-step",
        "execute-cleanup-step", "record-cleanup", "plan-reconcile",
    }
    choices = next(
        action.choices for action in cli.parser()._actions
        if getattr(action, "choices", None)
    )
    require(set(choices) == expected, "runtime command set changed")
    require(set(BEHAVIORAL_CLI_CASES) == expected, "behavioral CLI cases incomplete")
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix=".workflow-kernel-validator-", dir=ROOT) as directory:
        root = Path(directory)
        initialized = subprocess.run(
            ("git", "init", "-q", str(root)), env=deterministic_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        require(initialized.returncode == 0, "temporary git fixture initialization failed")
        run_root = root / ".workflow-kernel" / "runs" / "validator-cli"
        state_dir = run_root
        replacements = {
            "<run>": str(run_root), "<state>": str(state_dir),
            "<missing>": str(root / "missing.json"),
            "<event>": json.dumps({
                "schema_version": 1, "sequence": 1, "run_id": "validator-cli",
                "node_id": None, "kind": "run.started",
                "occurred_at": "2026-07-14T00:00:01Z", "payload": {},
            }, sort_keys=True),
        }
        for command, template in BEHAVIORAL_CLI_CASES.items():
            argv = [
                str(root / f"{command}-output.json") if item == "<output>"
                else replacements.get(item, item)
                for item in template
            ]
            completed = run([sys.executable, "-m", "workflow_kernel", command, *argv])
            if command in {
                "init", "validate", "append", "replay", "status",
                "plan-cleanup",
            }:
                require(completed.returncode == 0, f"{command} behavioral execution failed")
            else:
                require(
                    completed.returncode in {
                        cli.EXIT_INVALID, cli.EXIT_UNSAFE_PLAN,
                        cli.EXIT_RUNTIME_UNAVAILABLE, cli.EXIT_PARITY_GAP,
                        cli.EXIT_CONFLICT,
                    },
                    f"{command} did not fail safely",
                )
            outcomes[command] = completed.returncode

        def successful(command, *arguments):
            completed = run([sys.executable, "-m", "workflow_kernel", command, *map(str, arguments)])
            require(completed.returncode == 0, f"{command} valid fixture execution failed")
            outcomes[command] = completed.returncode

        def initialize(run_id):
            directory = root / ".workflow-kernel" / "runs" / run_id
            successful(
                "init", directory, "--run-id", run_id,
                "--occurred-at", "2026-07-14T00:00:00Z",
            )
            return directory

        def start(directory, run_id):
            event = json.dumps({
                "schema_version": 1, "sequence": 2, "run_id": run_id,
                "node_id": None, "kind": "run.started",
                "occurred_at": "2026-07-14T00:00:02Z", "payload": {},
            }, sort_keys=True)
            successful("append", directory, "--event", event)

        pipeline_run = initialize("pipeline-1")
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({
            "feature": "pipeline-1", "workflowClass": "feature",
            "executionMode": "codex_native", "chunks": [],
        }), encoding="utf-8")
        pipeline_receipts = json.loads((RECEIPTS / "pipeline-codex.json").read_text(encoding="utf-8"))
        prediction = root / "pipeline-prediction.json"
        prediction.write_text(json.dumps([
            {**item, "prediction_basis": "pre-action"} for item in pipeline_receipts
        ]), encoding="utf-8")
        successful(
            "bind-prediction", "--type", "pipeline", "--manifest", manifest,
            "--prediction-receipts", prediction, "--state-dir", root,
        )
        start(pipeline_run, "pipeline-1")
        successful(
            "observe-pipeline", "--manifest", manifest,
            "--receipts", RECEIPTS / "pipeline-codex.json", "--state-dir", root,
        )
        successful(
            "compare", "--state-dir", root,
            "--authoritative-receipts", RECEIPTS / "pipeline-codex.json",
            "--output", root / "parity.json",
        )

        review_run = initialize("review-1")
        request = root / "review-request.json"
        request.write_text(json.dumps({
            "run_id": "review-1", "requested_lanes": ["security", "architecture", "visual"],
            "mode": "full", "workflow_class": "bug", "executionMode": "generic",
        }), encoding="utf-8")
        review_receipts = json.loads((RECEIPTS / "dm-review.json").read_text(encoding="utf-8"))
        review_prediction = root / "review-prediction.json"
        review_prediction.write_text(json.dumps([
            {**item, "prediction_basis": "pre-action"} for item in review_receipts
        ]), encoding="utf-8")
        successful(
            "bind-prediction", "--type", "review", "--request", request,
            "--prediction-receipts", review_prediction, "--state-dir", root,
        )
        start(review_run, "review-1")
        successful(
            "observe-review", "--request", request,
            "--receipts", RECEIPTS / "dm-review.json", "--state-dir", root,
        )
        successful(
            "metrics", "--events", RECEIPTS / "pipeline-codex.json",
            "--output", root / "metrics.json",
        )

        argv = root / "create-argv.json"
        argv.write_text(json.dumps(["docker", "run", "--name", "validator-box", "busybox:latest"]), encoding="utf-8")
        create_plan = root / "create-plan.json"
        successful(
            "plan-create", "--state-dir", run_root, "--run-id", "validator-cli",
            "--node-id", "node", "--lifecycle", "chunk", "--cleanup-policy", "stop-remove",
            "--argv-json", argv, "--output", create_plan,
        )
        compose_file = root / "compose.yml"
        compose_file.write_text("services:\n  app:\n    image: busybox:latest\n", encoding="utf-8")
        compose_argv = root / "compose-argv.json"
        compose_argv.write_text(json.dumps(["docker", "compose", "-f", str(compose_file), "up"]), encoding="utf-8")
        from workflow_kernel.cli import command_plan_compose
        from workflow_kernel.resources import CommandResult
        class OfflineComposeRunner:
            def run(self, argv):
                return CommandResult(
                    tuple(argv), 0,
                    json.dumps({"services": {"app": {"image": "busybox:latest"}}, "networks": {}, "volumes": {}}),
                    "",
                )
        with mock.patch("workflow_kernel.cli._SubprocessRunner", OfflineComposeRunner):
            compose_status = command_plan_compose(SimpleNamespace(
                state_dir=run_root, run_id="validator-cli", node_id="node",
                lifecycle="chunk", cleanup_policy="stop-remove",
                dependent_node_ids_json=None, argv_json=compose_argv,
                output=root / "compose-plan.json",
            ))
        require(compose_status == 0, "plan-compose valid fixture execution failed")
        outcomes["plan-compose"] = 0
        plan_document = json.loads(create_plan.read_text(encoding="utf-8"))
        command_result = root / "command-result.json"
        command_result.write_text(json.dumps({
            "schema_version": 1, "argv": plan_document["argv"], "exit_code": 0,
            "stdout": "", "stderr": "",
        }), encoding="utf-8")
        from workflow_kernel.adapters.docker import DockerInventory
        from workflow_kernel.cli import _inventory_dict
        empty_inventory = root / "empty-inventory.json"
        empty_inventory.write_text(json.dumps(_inventory_dict(DockerInventory(()))), encoding="utf-8")
        successful(
            "record-create", "--state-dir", run_root, "--plan", create_plan,
            "--result", command_result, "--before-inventory", empty_inventory,
            "--after-inventory", empty_inventory,
        )
        cleanup_plan = root / "cleanup-plan.json"
        successful(
            "plan-cleanup", "--state-dir", run_root, "--run-id", "validator-cli",
            "--node-id", "node", "--output", cleanup_plan,
        )
        outcomes_path = root / "cleanup-outcomes.json"
        outcomes_path.write_text("[]", encoding="utf-8")
        successful(
            "next-cleanup-step", "--state-dir", run_root, "--plan", cleanup_plan,
            "--outcomes", outcomes_path, "--output", root / "next-cleanup.json",
        )
        successful(
            "record-cleanup", "--state-dir", run_root, "--plan", cleanup_plan,
            "--outcomes", outcomes_path,
        )

        from tests.test_runtime_cli import RuntimeCliTests
        for command, method in (
            ("execute-cleanup-step", "test_stale_cli_action_executes_under_old_run_guard_without_current_run_node_witness"),
            ("plan-reconcile", "test_canonical_run_init_is_reachable_from_shared_lease_root"),
        ):
            result = unittest.TestResult()
            RuntimeCliTests(method).run(result)
            require(result.wasSuccessful(), f"{command} valid fixture execution failed")
            outcomes[command] = 0
        require(set(outcomes) == SUCCESSFUL_CLI_COMMANDS, "successful CLI coverage incomplete")
    invalid = run([sys.executable, "-m", "workflow_kernel", "not-a-command"])
    require(invalid.returncode == cli.EXIT_INVALID, "invalid CLI exit code changed")
    quiet = io.StringIO()
    with mock.patch.object(cli, "command_status", side_effect=cli.RuntimeUnavailableError()), \
            contextlib.redirect_stderr(quiet), contextlib.redirect_stdout(quiet):
        unavailable = cli.main(["status", "/offline-fixture"])
    require(unavailable == cli.EXIT_RUNTIME_UNAVAILABLE, "unavailable CLI exit code changed")
    with mock.patch.object(cli, "command_status", return_value=cli.EXIT_UNSAFE_PLAN), \
            contextlib.redirect_stderr(quiet), contextlib.redirect_stdout(quiet):
        blocked = cli.main(["status", "/blocked-fixture"])
    require(blocked == cli.EXIT_UNSAFE_PLAN, "blocked CLI exit code changed")
    context["cli_commands"] = sorted(expected)
    context["cli_execution"] = outcomes


def check_workflow_classes(context):
    from workflow_kernel.adapters.base import HostCapabilities, WorkflowClass
    from workflow_kernel.pipeline_adapter import translate_manifest
    validated = []
    for host in ("claude", "codex", "generic"):
        for kind in WorkflowClass:
            spec = translate_manifest({
                "feature": f"validator-{host}-{kind.value}",
                "workflowClass": kind.value, "executionMode": "generic", "chunks": [],
            }, HostCapabilities(host, frozenset()))
            require(spec.nodes and spec.nodes[-1].node_id == "cleanup", "workflow cleanup invariant missing")
            validated.append(f"{host}:{kind.value}")
    context["workflow_classes"] = validated


def check_persona_layouts(context):
    from workflow_kernel.adapters.personas import ProjectPersonaAdapter
    adapter = lambda: ProjectPersonaAdapter(policy_path=REFERENCES / "workflow-policy.json")
    direct = adapter().discover(PERSONAS, declaration_root=".")
    require(direct.cases, "Assembly declaration-root layout empty")
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "tests" / "ux"
        shutil.copytree(PERSONAS, target)
        nested = adapter().discover(Path(directory))
    require(nested.cases and nested.to_dict() == direct.to_dict(), "Assembly-baseplate layout mismatch")
    context["persona_layouts"] = ["declaration_root", "tests/ux"]


CHECKS = (
    check_canonical_runtime, check_documents, check_unittests, check_scenarios,
    check_state, check_terminal_cleanup, check_docker_safety, check_secrets,
    check_hosts, check_promotion, check_cli, check_workflow_classes,
    check_persona_layouts,
)


def write_evidence(path, context):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": 1, "evidence_origin": "fixture",
        "real_run_evidence": False, "default_mode": "shadow",
        "checks": list(SECTIONS), "scenario_count": context["scenario_count"],
        "host_compatibility": context["host_compatibility"],
        "promotion": context["promotion"],
        "promotion_criteria": context["promotion_criteria"],
        "workflow_classes": context["workflow_classes"],
        "persona_layouts": context["persona_layouts"],
    }
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--evidence-output", metavar="PATH", default=str(DEFAULT_EVIDENCE_OUTPUT),
        help="write deterministic fixture-only compatibility and promotion evidence",
    )
    args = parser.parse_args(argv)
    context = {"completed_checks": {}}
    for number, (name, check) in enumerate(zip(SECTIONS, CHECKS), 1):
        try:
            check(context)
        except Exception as error:
            print(
                f"FAIL {number:02d} {name}: {type(error).__name__}: "
                f"{safe_failure_text(error)}"
            )
            return 1
        context["completed_checks"][name] = True
        detail = ""
        if args.verbose and name == "scenario replay":
            detail = f" ({context['scenario_count']} scenarios)"
        print(f"PASS {number:02d} {name}{detail}")
    try:
        write_evidence(args.evidence_output, context)
    except (OSError, TypeError, ValueError) as error:
        print(f"FAIL evidence output: {type(error).__name__}: {safe_failure_text(error)}")
        return 1
    print("PASS evidence output (fixture-only; no real-run evidence claimed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
