#!/usr/bin/env python3
"""Offline behavioral validator for the neutral workflow kernel."""

from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
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

sys.path.insert(0, str(REFERENCES))


class ValidationFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationFailure(message)


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
    require(completed.returncode == 0, completed.stderr[-4000:] or "unittest failed")
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


def check_docker_safety(context):
    violations = []
    for path in sorted((REFERENCES / "workflow_kernel").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = " ".join(node.value.lower().split())
                if ("docker system prune" in lowered
                        or "docker container prune" in lowered
                        or "docker network prune" in lowered
                        or "docker volume prune" in lowered
                        or "label!=" in lowered):
                    violations.append(f"{path.name}:{node.lineno}:broad-prune")
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        violations.append(f"{path.name}:{node.lineno}:shell-true")
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
    fixture = tuple(PromotionEvidence(name, True, EvidenceOrigin.FIXTURE) for name in ENFORCE_CRITERIA)
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
    for command in sorted(expected):
        completed = run([sys.executable, "-m", "workflow_kernel", command, "--help"])
        require(completed.returncode == 0, f"{command} help failed")
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
        "workflow_classes": context["workflow_classes"],
        "persona_layouts": context["persona_layouts"],
    }
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--evidence-output", metavar="PATH", help="write deterministic fixture-only compatibility and promotion evidence")
    args = parser.parse_args(argv)
    context = {}
    for number, (name, check) in enumerate(zip(SECTIONS, CHECKS), 1):
        try:
            check(context)
        except Exception as error:
            print(f"FAIL {number:02d} {name}: {type(error).__name__}: {error}")
            return 1
        detail = ""
        if args.verbose and name == "scenario replay":
            detail = f" ({context['scenario_count']} scenarios)"
        print(f"PASS {number:02d} {name}{detail}")
    if args.evidence_output:
        try:
            write_evidence(args.evidence_output, context)
        except (OSError, TypeError, ValueError) as error:
            print(f"FAIL evidence output: {type(error).__name__}")
            return 1
        print("PASS evidence output (fixture-only; no real-run evidence claimed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
