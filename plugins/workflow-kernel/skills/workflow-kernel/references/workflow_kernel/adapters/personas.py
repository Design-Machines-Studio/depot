"""Project-local Assembly persona and task discovery."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from .base import invalid_policy
from ..limits import load_json_document
from ..verification import EvidenceRef, PersonaCase, VerificationProfile, validate_viewport

_TOP = re.compile(r"^([a-z_]+):\s*(.*?)\s*$", re.M)
_PERSONA = re.compile(r"^  - id:\s*([a-z0-9-]+)\s*$", re.M)
_VIEWPORT = re.compile(r"([1-9][0-9]{1,4})x([1-9][0-9]{1,4})")
_RUNNABLE = frozenset({"current", "redirected-current"})


def _fail():
    raise invalid_policy("invalid_verification_declaration")


def _frontmatter(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _fail()
    if not text.startswith("---\n"):
        _fail()
    pieces = text.split("---\n", 2)
    if len(pieces) != 3:
        _fail()
    return pieces[1]


def _scalars(frontmatter):
    return {key: value.strip().strip('"\'') for key, value in _TOP.findall(frontmatter)}


def _list(frontmatter, key):
    lines = frontmatter.splitlines()
    try:
        start = lines.index(key + ":") + 1
    except ValueError:
        return []
    result = []
    for line in lines[start:]:
        if line.startswith("  - "):
            result.append(line[4:].strip().strip('"\''))
        elif line.startswith(" ") or not line.strip():
            continue
        else:
            break
    return result


def _assignments(frontmatter):
    starts = list(_PERSONA.finditer(frontmatter)); result = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(frontmatter)
        block = frontmatter[match.start():end]
        expected = re.search(r"^    expected:\s*([A-Z]+)\s*$", block, re.M)
        required = re.search(r"^    required:\s*(true|false)\s*$", block, re.M)
        if expected is None:
            _fail()
        result.append((match.group(1), expected.group(1), required is None or required.group(1) == "true"))
    return result


def _task(path):
    frontmatter = _frontmatter(path); values = _scalars(frontmatter)
    assignments = _assignments(frontmatter)
    if not {"id", "title", "route", "requires_auth", "requires_role"} <= set(values) or not assignments:
        _fail()
    if values["requires_auth"] not in {"true", "false"}:
        _fail()
    return {"id": values["id"].lower(), "route": values["route"],
            "role": values["requires_role"], "requires_auth": values["requires_auth"] == "true",
            "status": values.get("implementation_status"), "legacy": "implementation_status" not in values,
            "personas": assignments, "tags": _list(frontmatter, "tags"),
            "preconditions": _list(frontmatter, "preconditions"),
            "auth_fields": _list(frontmatter, "auth_fields")}


def _persona_defaults(root):
    result = {}
    for path in sorted((root / "personas").glob("*.md")):
        if path.name == "_index.md":
            continue
        values = _scalars(_frontmatter(path)); persona_id = values.get("id")
        if not persona_id or persona_id in result:
            _fail()
        viewport = None
        match = re.search(r"width:\s*([0-9]+),\s*height:\s*([0-9]+)", values.get("viewport", ""))
        if match:
            viewport = match.group(1) + "x" + match.group(2); validate_viewport(viewport)
        result[persona_id] = (values.get("device", ""), viewport)
    return result


def _suite(root, suite_id):
    matches = []
    for path in sorted((root / "suites").glob("*.md")) if (root / "suites").is_dir() else ():
        frontmatter = _frontmatter(path)
        if _scalars(frontmatter).get("id") == suite_id:
            matches.append({item.lower() for item in _list(frontmatter, "task_ids")})
    if len(matches) != 1 or not matches[0]:
        _fail()
    return matches[0]


class PersonaAdapter(Protocol):
    def discover(self, project_root: Path) -> VerificationProfile: ...
    def execute(self, case: PersonaCase) -> EvidenceRef: ...


class ProjectPersonaAdapter:
    def __init__(self, *, policy_path):
        self._policy_path = Path(policy_path)

    def discover(self, project_root):
        project = Path(project_root)
        ux = project / "tests" / "ux" if (project / "tests" / "ux").is_dir() else project
        if not ux.is_dir() or not (ux / "tasks").is_dir() or not (ux / "personas").is_dir():
            return VerificationProfile(1, "not_declared", (), (), "not_declared")
        try:
            policy = load_json_document(self._policy_path)["verification"]
        except Exception:
            _fail()
        if type(policy) is not dict or set(policy) != {"browser_engines", "desktop_viewport", "mobile_viewport"}:
            _fail()
        engines = policy["browser_engines"]; viewports = None
        browser_source = "workflow_policy_default"; viewport_source = "workflow_policy_default"
        selected_suite = None; statuses = set(_RUNNABLE)
        config_path = ux / "verification.json"
        if config_path.exists():
            try:
                config = load_json_document(config_path)
            except Exception:
                _fail()
            allowed = {"schema_version", "suite", "browser_engines", "viewports", "include_statuses"}
            if type(config) is not dict or set(config) - allowed or config.get("schema_version") != 1:
                _fail()
            selected_suite = config.get("suite")
            if "browser_engines" in config:
                engines = config["browser_engines"]; browser_source = "project_config"
            if "viewports" in config:
                viewports = config["viewports"]; viewport_source = "project_config"
            if "include_statuses" in config:
                statuses = set(config["include_statuses"])
        if type(engines) is not list or not engines or len(engines) != len(set(engines)) or any(item not in {"chromium", "firefox", "webkit"} for item in engines):
            _fail()
        if viewports is not None:
            if type(viewports) is not list or not viewports:
                _fail()
            for item in viewports: validate_viewport(item)
        else:
            validate_viewport(policy.get("desktop_viewport")); validate_viewport(policy.get("mobile_viewport"))
        defaults = _persona_defaults(ux); selected = _suite(ux, selected_suite) if selected_suite else None
        tasks = [_task(path) for path in sorted((ux / "tasks").rglob("*.md"))]
        ids = [task["id"] for task in tasks]
        if len(ids) != len(set(ids)):
            _fail()
        cases, auth_names = [], set()
        for task in tasks:
            if selected is not None and task["id"] not in selected: continue
            if selected is None and (task["status"] or "current") not in statuses: continue
            auth_names.update(task["auth_fields"])
            for persona_id, expected, required in task["personas"]:
                if persona_id not in defaults: _fail()
                device, persona_viewport = defaults[persona_id]
                match = _VIEWPORT.search(" ".join(task["preconditions"]))
                task_viewport = match.group(1) + "x" + match.group(2) if match else None
                if viewports is not None: case_viewports, source = viewports, viewport_source
                elif task_viewport: case_viewports, source = [task_viewport], "task_declaration"
                elif persona_viewport: case_viewports, source = [persona_viewport], "persona_default"
                elif device == "mobile" or set(task["tags"]) & {"mobile", "responsive"}: case_viewports, source = [policy["mobile_viewport"]], "workflow_policy_default"
                else: case_viewports, source = [policy["desktop_viewport"]], "workflow_policy_default"
                for engine in engines:
                    for viewport in case_viewports:
                        cases.append(PersonaCase(persona_id, task["id"], task["role"], task["route"], engine,
                                                 viewport, required, expected, task["requires_auth"], browser_source,
                                                 source, task["legacy"]))
        if selected is not None and not selected <= set(ids): _fail()
        cases.sort(key=lambda item: item.case_id)
        return VerificationProfile(1, "project_declaration", tuple(cases), tuple(sorted(auth_names)))
