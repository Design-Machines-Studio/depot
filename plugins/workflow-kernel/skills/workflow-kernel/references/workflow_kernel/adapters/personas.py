"""Project-local Assembly persona and task discovery."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from .base import invalid_policy
from ..limits import load_json_document
from ..policies import PolicyDocument, load_policy
from ..verification import EvidenceRef, PersonaCase, VerificationProfile, validate_viewport

_TOP = re.compile(r"^([a-z_]+):\s*(.*?)\s*$", re.M)
_PERSONA = re.compile(r"^  - id:\s*([a-z0-9-]+)\s*$", re.M)
_VIEWPORT = re.compile(r"([1-9][0-9]{1,4})x([1-9][0-9]{1,4})")
_RUNNABLE = frozenset({"current", "redirected-current"})
_KNOWN_STATUSES = frozenset({
    "current", "redirected-current", "current-gap", "future-product",
    "future-fixture-ui",
})
_INDEX_LINK = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)\Z")
_MATRIX_PERSONAS = {
    "EC": "engaged-chair", "PS": "power-secretary",
    "RB": "reluctant-board-member", "CM": "casual-member",
    "NP": "new-probationary", "NT": "numbers-treasurer",
}
_MATRIX_OUTCOMES = {"S": "SUCCESS", "F": "FRICTION", "B": "BLOCKED", "P": "PARTIAL"}


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
    status = values.get("implementation_status")
    if status is not None and status not in _KNOWN_STATUSES:
        _fail()
    return {"id": values["id"].lower(), "route": values["route"],
            "role": values["requires_role"], "requires_auth": values["requires_auth"] == "true",
            "status": status, "legacy": "implementation_status" not in values,
            "personas": assignments, "tags": _list(frontmatter, "tags"),
            "preconditions": _list(frontmatter, "preconditions"),
            "auth_fields": _list(frontmatter, "auth_fields")}


def _persona_index(root):
    directory = root / "personas"
    index = directory / "_index.md"
    try:
        text = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        _fail()
    declared = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        first_cell = line.strip().strip("|").split("|", 1)[0].strip()
        match = _INDEX_LINK.fullmatch(first_cell)
        if match is not None:
            declared.append(match.group(1))
    if (not declared or len(declared) != len(set(declared))
            or any(Path(name).name != name or name == "_index.md" for name in declared)):
        _fail()
    actual = {path.name for path in directory.glob("*.md") if path.name != "_index.md"}
    if set(declared) != actual:
        _fail()
    return tuple(directory / name for name in sorted(declared))


def _persona_defaults(root, persona_paths):
    result = {}
    for path in persona_paths:
        values = _scalars(_frontmatter(path)); persona_id = values.get("id")
        if not persona_id or persona_id in result or path.stem != persona_id:
            _fail()
        viewport = None
        match = re.search(r"width:\s*([0-9]+),\s*height:\s*([0-9]+)", values.get("viewport", ""))
        if match:
            viewport = match.group(1) + "x" + match.group(2); validate_viewport(viewport)
        result[persona_id] = (values.get("device", ""), viewport)
    return result


def _validate_coverage_matrix(root, tasks):
    path = root / "coverage-matrix.md"
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        _fail()
    direct_rows, indexed_rows = set(), {}
    header = None
    for line in lines:
        if not line.lstrip().startswith("|"):
            header = None
            continue
        cells = tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        if cells[:3] == ("Task", "Persona", "Expected") or cells[0] == "Task ID":
            header = cells
            continue
        if header == ("Task", "Persona", "Expected") and len(cells) >= 3:
            row = (cells[0].lower(), cells[1], cells[2])
            if row in direct_rows:
                _fail()
            direct_rows.add(row)
            continue
        if header is not None and header[0] == "Task ID" and len(cells) == len(header):
            task_id = cells[0].lower()
            persona_rows = set()
            for index, column in enumerate(header):
                persona_id = _MATRIX_PERSONAS.get(column)
                if persona_id is None or cells[index] == "-":
                    continue
                outcome = _MATRIX_OUTCOMES.get(cells[index])
                if outcome is None:
                    _fail()
                persona_rows.add((task_id, persona_id, outcome))
            if persona_rows:
                if task_id in indexed_rows:
                    _fail()
                indexed_rows[task_id] = persona_rows
    expected = {
        (task["id"], persona_id, outcome)
        for task in tasks for persona_id, outcome, _required in task["personas"]
    }
    if direct_rows and direct_rows != expected:
        _fail()
    for task_id, rows in indexed_rows.items():
        authoritative = {row for row in expected if row[0] == task_id}
        if not authoritative or rows != authoritative:
            _fail()
    if not direct_rows and not indexed_rows:
        _fail()


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
    def __init__(self, *, policy_path=None, policy_document=None):
        if (policy_path is None) == (policy_document is None):
            _fail()
        if policy_document is not None and type(policy_document) is not PolicyDocument:
            _fail()
        self._policy_path = Path(policy_path) if policy_path is not None else None
        self._policy_document = policy_document

    def discover(self, project_root):
        project = Path(project_root)
        declared_root = project / "tests" / "ux"
        if declared_root.exists():
            if not declared_root.is_dir():
                _fail()
            ux = declared_root
        elif any((project / name).exists() for name in ("tasks", "personas", "coverage-matrix.md")):
            ux = project
        else:
            return VerificationProfile(
                1, "not_declared", (), (), "not_declared", "not_declared",
            )
        if not ux.is_dir() or not (ux / "tasks").is_dir() or not (ux / "personas").is_dir():
            _fail()
        try:
            document = self._policy_document or load_policy(self._policy_path)
            defaults_map = document.verification_defaults
            policy = {
                "browser_engines": list(defaults_map["browser_engines"]),
                "desktop_viewport": defaults_map["desktop_viewport"],
                "mobile_viewport": defaults_map["mobile_viewport"],
            }
        except Exception:
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
                configured_statuses = config["include_statuses"]
                if (type(configured_statuses) is not list or not configured_statuses
                        or len(configured_statuses) != len(set(configured_statuses))
                        or any(type(item) is not str or item not in _KNOWN_STATUSES
                               for item in configured_statuses)):
                    _fail()
                statuses = set(configured_statuses)
        if type(engines) is not list or not engines or len(engines) != len(set(engines)) or any(item not in {"chromium", "firefox", "webkit"} for item in engines):
            _fail()
        if viewports is not None:
            if type(viewports) is not list or not viewports:
                _fail()
            for item in viewports: validate_viewport(item)
        else:
            validate_viewport(policy.get("desktop_viewport")); validate_viewport(policy.get("mobile_viewport"))
        defaults = _persona_defaults(ux, _persona_index(ux))
        selected = _suite(ux, selected_suite) if selected_suite else None
        tasks = [_task(path) for path in sorted((ux / "tasks").rglob("*.md"))]
        if not tasks:
            _fail()
        ids = [task["id"] for task in tasks]
        if len(ids) != len(set(ids)):
            _fail()
        _validate_coverage_matrix(ux, tasks)
        if selected is None and config_path.exists() and "include_statuses" in config:
            runnable_present = {
                task["status"] or "current" for task in tasks
                if (task["status"] or "current") in _RUNNABLE
            }
            if not runnable_present <= statuses:
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
        if not cases:
            selection_status = "no_runnable_tasks"
        elif any(case.required for case in cases):
            selection_status = "runnable_cases"
        else:
            selection_status = "optional_cases_only"
        return VerificationProfile(
            1, "project_declaration", tuple(cases), tuple(sorted(auth_names)),
            "declared", selection_status,
        )
