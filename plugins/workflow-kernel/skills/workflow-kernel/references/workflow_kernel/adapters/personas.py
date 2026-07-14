"""Project-local Assembly persona and task discovery."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Protocol

from .base import invalid_policy
from .._files import PinnedDirectory
from ..limits import parse_json_document
from ..policies import PolicyDocument, _snapshot_policy_document, load_policy
from ..verification import (
    EvidenceRef, PersonaCase, VerificationProfile, digest_target_origin,
    validate_viewport,
)

_TOP = re.compile(r"^([a-z_]+):\s*(.*?)\s*$", re.M)
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
_MAX_DECLARATION_BYTES = 1_048_576


def _fail():
    raise invalid_policy("invalid_verification_declaration")


def _owned_path(path, root, *, directory=False):
    try:
        lexical_root = root.absolute()
        lexical_path = path.absolute()
        if lexical_path != lexical_root and lexical_root not in lexical_path.parents:
            _fail()
        current = lexical_root
        if current.is_symlink():
            _fail()
        for part in lexical_path.relative_to(lexical_root).parts:
            current = current / part
            if current.is_symlink():
                _fail()
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        _fail()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        _fail()
    if directory and not path.is_dir():
        _fail()
    if not directory and not path.is_file():
        _fail()
    return path


def _reject_symlinks(root):
    try:
        for path in root.rglob("*"):
            if path.is_symlink():
                _fail()
    except OSError:
        _fail()


def _read_owned_text(path, root):
    _owned_path(path, root)
    descriptor = None
    try:
        with PinnedDirectory.open(path.parent) as directory:
            descriptor = directory.open_regular(path.name, os.O_RDONLY)
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65_536, _MAX_DECLARATION_BYTES + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > _MAX_DECLARATION_BYTES:
                    _fail()
            directory.require_identity(descriptor, path.name)
            directory.revalidate()
            os.close(descriptor)
            descriptor = None
        return b"".join(chunks).decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        _fail()
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _frontmatter(path, root):
    text = _read_owned_text(path, root)
    if not text.startswith("---\n"):
        _fail()
    pieces = text.split("---\n", 2)
    if len(pieces) != 3:
        _fail()
    frontmatter = pieces[1]
    keys = [
        match.group(1)
        for line in frontmatter.splitlines()
        if (match := re.match(r"^([a-z_]+):(?:\s|$)", line)) is not None
    ]
    if len(keys) != len(set(keys)):
        _fail()
    return frontmatter


def _scalars(frontmatter):
    pairs = _TOP.findall(frontmatter)
    keys = [key for key, _value in pairs]
    if len(keys) != len(set(keys)):
        _fail()
    return {key: value.strip().strip('"\'') for key, value in pairs}


def _list(frontmatter, key):
    lines = frontmatter.splitlines()
    starts = [index for index, line in enumerate(lines) if line == key + ":"]
    if len(starts) > 1:
        _fail()
    if not starts:
        return []
    start = starts[0] + 1
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
    lines = frontmatter.splitlines()
    starts = [index for index, line in enumerate(lines) if line == "personas:"]
    if len(starts) != 1:
        _fail()
    section = []
    for line in lines[starts[0] + 1:]:
        if line and not line.startswith(" "):
            break
        if line.strip():
            section.append(line)
    result = []
    current = None
    seen_ids = set()
    for line in section:
        match = re.fullmatch(r"  - id:\s*([a-z0-9][a-z0-9._-]*)", line)
        if match is not None:
            if current is not None:
                result.append(current)
            persona_id = match.group(1)
            if persona_id in seen_ids:
                _fail()
            seen_ids.add(persona_id)
            current = {"id": persona_id}
            continue
        match = re.fullmatch(r"    (expected|required):\s*(\S+)", line)
        if match is None or current is None or match.group(1) in current:
            _fail()
        current[match.group(1)] = match.group(2)
    if current is not None:
        result.append(current)
    normalized = []
    for item in result:
        if (set(item) - {"id", "expected", "required"}
                or item.get("expected") not in {"SUCCESS", "FRICTION", "BLOCKED", "PARTIAL"}
                or "required" in item and item["required"] not in {"true", "false"}):
            _fail()
        normalized.append((
            item["id"], item["expected"], item.get("required", "true") == "true",
        ))
    if not normalized:
        _fail()
    return normalized


def _task_at(path, root):
    frontmatter = _frontmatter(path, root); values = _scalars(frontmatter)
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
    _owned_path(directory, root, directory=True)
    index = directory / "_index.md"
    _owned_path(index, root)
    text = _read_owned_text(index, root)
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
    persona_files = tuple(directory.glob("*.md"))
    for path in persona_files:
        _owned_path(path, root)
    actual = {path.name for path in persona_files if path.name != "_index.md"}
    if set(declared) != actual:
        _fail()
    return tuple(directory / name for name in sorted(declared))


def _persona_defaults(root, persona_paths):
    result = {}
    for path in persona_paths:
        values = _scalars(_frontmatter(path, root)); persona_id = values.get("id")
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
    if path.is_symlink():
        _fail()
    if not path.exists():
        return
    _owned_path(path, root)
    lines = _read_owned_text(path, root).splitlines()
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
    if indexed_rows and set().union(*indexed_rows.values()) != expected:
        _fail()
    if not direct_rows and not indexed_rows:
        _fail()


def _suite(root, suite_id):
    matches = []
    for path in sorted((root / "suites").glob("*.md")) if (root / "suites").is_dir() else ():
        frontmatter = _frontmatter(path, root)
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
        if policy_document is not None:
            try:
                self._policy_document = _snapshot_policy_document(policy_document)
            except Exception:
                _fail()
        else:
            self._policy_document = None

    def discover(self, project_root, *, target_origin=None):
        try:
            return self._discover(project_root, target_origin=target_origin)
        except Exception:
            _fail()

    def _discover(self, project_root, *, target_origin=None):
        project = Path(project_root)
        declared_root = project / "tests" / "ux"
        if declared_root.is_symlink():
            _fail()
        if declared_root.exists():
            _owned_path(declared_root, project, directory=True)
            ux = declared_root
        elif any((project / name).exists() for name in ("tasks", "personas", "coverage-matrix.md")):
            ux = project
        else:
            profile = VerificationProfile(
                1, "not_declared", (), (), "not_declared", "not_declared", (),
            )
            return profile if target_origin is None else profile.bind_target_origin(target_origin)
        _owned_path(ux, project if ux == declared_root else ux, directory=True)
        _owned_path(ux / "tasks", ux, directory=True)
        _owned_path(ux / "personas", ux, directory=True)
        _reject_symlinks(ux)
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
        selected_suite = None; statuses = set(_RUNNABLE); configured_origin = None
        config_path = ux / "verification.json"
        if config_path.is_symlink():
            _fail()
        if config_path.exists():
            _owned_path(config_path, ux)
            try:
                config = parse_json_document(_read_owned_text(config_path, ux))
            except Exception:
                _fail()
            allowed = {
                "schema_version", "suite", "browser_engines", "viewports",
                "include_statuses", "target_origin",
            }
            if (type(config) is not dict or set(config) - allowed
                    or type(config.get("schema_version")) is not int
                    or config.get("schema_version") != 1):
                _fail()
            selected_suite = config.get("suite")
            if selected_suite is not None and (type(selected_suite) is not str or not selected_suite):
                _fail()
            if "browser_engines" in config:
                engines = config["browser_engines"]; browser_source = "project_config"
            if "viewports" in config:
                viewports = config["viewports"]; viewport_source = "project_config"
            if "include_statuses" in config:
                configured_statuses = config["include_statuses"]
                if (type(configured_statuses) is not list or not configured_statuses
                        or any(type(item) is not str or item not in _KNOWN_STATUSES
                               for item in configured_statuses)
                        or len(configured_statuses) != len(set(configured_statuses))):
                    _fail()
                statuses = set(configured_statuses)
            if "target_origin" in config:
                if type(config["target_origin"]) is not str:
                    _fail()
                configured_origin = digest_target_origin(config["target_origin"])
        if (type(engines) is not list or not engines
                or any(type(item) is not str or item not in {"chromium", "firefox", "webkit"} for item in engines)
                or len(engines) != len(set(engines))):
            _fail()
        if viewports is not None:
            if type(viewports) is not list or not viewports:
                _fail()
            for item in viewports: validate_viewport(item)
        else:
            validate_viewport(policy.get("desktop_viewport")); validate_viewport(policy.get("mobile_viewport"))
        defaults = _persona_defaults(ux, _persona_index(ux))
        selected = _suite(ux, selected_suite) if selected_suite else None
        task_paths = sorted((ux / "tasks").rglob("*.md"))
        for path in task_paths:
            _owned_path(path, ux)
        tasks = [_task_at(path, ux) for path in task_paths]
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
        runtime_origin = None if target_origin is None else digest_target_origin(target_origin)
        if configured_origin is not None and runtime_origin is not None and configured_origin != runtime_origin:
            _fail()
        return VerificationProfile(
            1, "project_declaration", tuple(cases), tuple(sorted(auth_names)),
            "declared", selection_status, tuple(engines),
            runtime_origin or configured_origin,
        )
