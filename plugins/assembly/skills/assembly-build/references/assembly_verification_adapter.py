"""Assembly-owned adapter for Workflow Kernel repository verification policy."""

from __future__ import annotations

import json
import re
from pathlib import Path

from workflow_kernel.browser_target import _validate_route, validate_viewport
from workflow_kernel.redaction import contains_high_confidence_secret, normalize_durable_string
from workflow_kernel.repository_verification import (
    derive_verification_plan,
    repository_profile_digest,
    resolve_repository_profile,
)
from workflow_kernel.schema import InvalidSchemaError


PROFILE_PATH = Path(__file__).with_name("assembly-baseplate-verification-profile.json")
PROJECT_PROFILE_PATH = Path(".assembly/verification-profile.json")
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_TASKS = 1024
MAX_SCREENSHOTS = 128
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_RUNNABLE_STATUSES = frozenset({"current", "redirected-current"})
_KNOWN_STATUSES = _RUNNABLE_STATUSES | frozenset({
    "current-gap", "future-product", "future-fixture-ui",
})
_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_OUTCOMES = frozenset({"SUCCESS", "FRICTION", "BLOCKED"})
_SERVICE_FIELDS = frozenset({
    "status", "service", "profile_digest", "repository_scope_id",
    "compose_project", "state_generation", "commit_sha",
})
_MISSING = object()


def _result(status, reason, **values):
    return {"status": status, "reason": reason, **values}


def _safe_text(value, name, maximum=2048):
    if (
        type(value) is not str or not value or len(value) > maximum
        or contains_high_confidence_secret(value)
    ):
        raise ValueError(f"invalid {name}")
    try:
        if normalize_durable_string(value) != value:
            raise ValueError
    except ValueError:
        raise ValueError(f"invalid {name}") from None
    return value


def _pairs_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _load_json(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError("verification profile unavailable")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("invalid JSON")),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("verification profile unavailable") from None


def _repository_supported(repository_root):
    root = Path(repository_root)
    if root.is_symlink() or not root.is_dir():
        return False
    markers = (
        (root / "go.mod", "file"),
        (root / "docker-compose.yml", "file"),
        (root / "cmd/assembly", "directory"),
    )
    return all(
        not path.is_symlink()
        and (path.is_file() if kind == "file" else path.is_dir())
        for path, kind in markers
    )


def resolve_assembly_profile(repository_root, *, project_profile=_MISSING, plugin_profile=None):
    """Resolve project > Assembly profile, returning unavailable on invalid input."""
    root = Path(repository_root)
    if not _repository_supported(root):
        return _result("unavailable", "unsupported_repository", source="none", profile=None)
    try:
        if project_profile is _MISSING:
            project_path = root / PROJECT_PROFILE_PATH
            project_profile = _load_json(project_path) if project_path.exists() else None
        if plugin_profile is None:
            plugin_profile = _load_json(PROFILE_PATH)
        resolved = resolve_repository_profile(
            project_profile=project_profile, plugin_profile=plugin_profile,
        )
    except (OSError, ValueError):
        return _result("unavailable", "invalid_repository_profile", source="none", profile=None)
    return _result(
        "resolved", "profile_resolved", source=resolved["source"],
        profile=resolved["profile"],
    )


def _exec_service_valid(argv, evidence, profile, repository, repository_root):
    if type(evidence) is not dict or set(evidence) != _SERVICE_FIELDS:
        return False
    if len(argv) < 4 or argv[:3] != ["docker", "compose", "exec"]:
        return True
    return evidence == {
        "status": "running",
        "service": argv[3],
        "profile_digest": repository_profile_digest(profile),
        "repository_scope_id": repository["scope_id"],
        "compose_project": Path(repository_root).name,
        "state_generation": "current",
        "commit_sha": repository["commit_sha"],
    }


def _exec_service(argv):
    if "exec" not in argv:
        return None
    if len(argv) < 4 or argv[:3] != ["docker", "compose", "exec"]:
        raise ValueError("unsupported exec argv")
    if _ID.fullmatch(argv[3]) is None:
        raise ValueError("invalid exec service")
    return argv[3]


def plan_assembly_verification(
    repository_root, repository, *, changed_paths, changed_packages, risk_inputs,
    required_lane_ids=(), generated_at, project_profile=_MISSING,
    plugin_profile=None, compose_service_evidence=None,
):
    """Return a Kernel-derived safe argv plan or an explicit fail-closed result."""
    resolved = resolve_assembly_profile(
        repository_root, project_profile=project_profile, plugin_profile=plugin_profile,
    )
    if resolved["status"] != "resolved":
        return {**resolved, "plan": None, "selected_argv": []}
    ux = discover_ux_tasks(repository_root)
    if ux["status"] == "blocked":
        return _result(
            "blocked", "invalid_ux_declaration", source=resolved["source"],
            profile=resolved["profile"], plan=None, selected_argv=[], ux=ux,
        )
    try:
        plan = derive_verification_plan(
            resolved["profile"], repository,
            changed_paths=changed_paths, changed_packages=changed_packages,
            risk_inputs=risk_inputs, required_lane_ids=required_lane_ids,
            generated_at=generated_at,
        )
    except ValueError:
        return _result(
            "unavailable", "invalid_verification_inputs", source=resolved["source"],
            profile=resolved["profile"], plan=None, selected_argv=[], ux=ux,
        )
    selected = [item for item in plan["lanes"] if item["selected"]]
    unavailable = [item["id"] for item in selected if not item["runnable"]]
    if unavailable:
        return _result(
            "unavailable", "selected_lane_unavailable", source=resolved["source"],
            profile=resolved["profile"], plan=plan, selected_argv=[],
            unavailable_lane_ids=unavailable, ux=ux,
        )
    for lane in selected:
        argv = lane["argv"]
        try:
            exec_service = _exec_service(argv)
        except ValueError:
            return _result(
                "unavailable", "unsupported_exec_argv",
                source=resolved["source"], profile=resolved["profile"],
                plan=plan, selected_argv=[], ux=ux,
            )
        if exec_service is not None:
            if not _exec_service_valid(
                argv, compose_service_evidence, resolved["profile"],
                plan["repository"], repository_root,
            ):
                return _result(
                    "unavailable", "compose_service_proof_unavailable",
                    source=resolved["source"], profile=resolved["profile"],
                    plan=plan, selected_argv=[], ux=ux,
                )
    return _result(
        "resolved", "verification_plan_resolved", source=resolved["source"],
        profile=resolved["profile"], plan=plan,
        selected_argv=[
            {"lane_id": item["id"], "argv": list(item["argv"])} for item in selected
        ], ux=ux,
    )


def _yaml_scalar(value, name):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    if not value or value[0] in "[{&*!>|@`" or value in {"null", "~"}:
        raise ValueError(f"invalid {name}")
    return _safe_text(value, name)


def _frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing task frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ValueError("unterminated task frontmatter") from None
    values, personas, screenshots = {}, [], []
    section = None
    current_persona = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ ](.*))?", line)
        if top:
            key, raw = top.groups()
            if key in values:
                raise ValueError("duplicate task field")
            values[key] = None if raw is None else _yaml_scalar(raw, key)
            section = key if raw is None else None
            current_persona = None
            continue
        if section == "personas":
            start = re.fullmatch(r"  - id:[ ](.+)", line)
            expected = re.fullmatch(r"    expected:[ ](.+)", line)
            if start:
                current_persona = {"id": _yaml_scalar(start.group(1), "persona id")}
                personas.append(current_persona)
            elif expected and current_persona is not None:
                if "expected" in current_persona:
                    raise ValueError("duplicate persona outcome")
                current_persona["expected"] = _yaml_scalar(expected.group(1), "persona outcome")
            continue
        if section == "screenshot_points":
            item = re.fullmatch(r"  -[ ](.+)", line)
            if item:
                screenshots.append(_yaml_scalar(item.group(1), "screenshot point"))
            continue
    values["personas"] = personas
    values["screenshot_points"] = screenshots
    return values


def _validate_task(values):
    status = values.get("implementation_status")
    if status not in _KNOWN_STATUSES:
        raise ValueError("invalid implementation status")
    if status not in _RUNNABLE_STATUSES:
        return None
    route = _validate_route(values.get("route"))
    auth = values.get("requires_auth")
    if auth not in {"true", "false"}:
        raise ValueError("invalid authentication declaration")
    viewport = validate_viewport(values.get("viewport"))
    engine = values.get("engine")
    if engine not in _ENGINES:
        raise ValueError("invalid browser engine")
    personas = values.get("personas")
    if not personas or len(personas) > MAX_TASKS:
        raise ValueError("missing personas")
    normalized_personas = []
    ids = set()
    for persona in personas:
        if set(persona) != {"id", "expected"}:
            raise ValueError("incomplete persona declaration")
        identifier = persona["id"]
        if _ID.fullmatch(identifier) is None or identifier in ids:
            raise ValueError("invalid persona id")
        if persona["expected"] not in _OUTCOMES:
            raise ValueError("invalid persona outcome")
        ids.add(identifier)
        normalized_personas.append(dict(persona))
    screenshots = values.get("screenshot_points")
    if not screenshots or len(screenshots) > MAX_SCREENSHOTS:
        raise ValueError("missing screenshot points")
    return {
        "implementation_status": status, "route": route,
        "requires_auth": auth == "true", "personas": normalized_personas,
        "viewport": viewport, "engine": engine,
        "screenshot_points": list(screenshots),
    }


def discover_ux_tasks(repository_root):
    """Read authoritative task frontmatter; never infer from coverage matrices."""
    root = Path(repository_root)
    tasks_root = root / "tests/ux/tasks"
    if tasks_root.is_symlink():
        return _result("blocked", "invalid_task_directory", tasks=[])
    if not tasks_root.is_dir():
        return _result("not_declared", "task_directory_absent", tasks=[])
    paths = sorted(tasks_root.rglob("*.md"))
    if not paths:
        return _result("not_declared", "task_declarations_absent", tasks=[])
    if len(paths) > MAX_TASKS:
        return _result("blocked", "too_many_task_declarations", tasks=[])
    tasks = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_DOCUMENT_BYTES:
                raise ValueError("invalid task file")
            values = _frontmatter(path.read_text(encoding="utf-8"))
            task = _validate_task(values)
        except (OSError, UnicodeError, ValueError, InvalidSchemaError):
            return _result(
                "blocked", "invalid_task_declaration", tasks=[], path=relative,
            )
        if task is not None:
            tasks.append({"path": relative, **task})
    return _result(
        "declared", "task_frontmatter_authority", tasks=tasks,
    )
