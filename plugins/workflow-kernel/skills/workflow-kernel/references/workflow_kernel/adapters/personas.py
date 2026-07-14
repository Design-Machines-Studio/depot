"""Project-local Assembly persona and task discovery."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Protocol

from .base import invalid_policy
from .._files import PinnedDirectory
from ..limits import parse_json_document
from ..policies import PolicyDocument, _snapshot_policy_document, load_policy
from ..verification import (
    EvidenceRef, PersonaCase, VerificationProfile, digest_target_origin,
    validate_viewport, _snapshot_evidence_ref, _snapshot_persona_case,
    _snapshot_verification_profile,
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


class _DeclarationTree:
    """One pinned UX root with descriptor-relative, no-follow descendant reads."""

    def __init__(self, root):
        self.root = root
        self._pinned_root = PinnedDirectory.open(root)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self._pinned_root.close()

    def _parts(self, path):
        try:
            relative = path.absolute().relative_to(self.root.absolute())
        except (OSError, ValueError):
            _fail()
        if relative.is_absolute() or not relative.parts or any(
                part in {"", ".", ".."} for part in relative.parts):
            _fail()
        return relative.parts

    def _open_parent(self, path):
        parts = self._parts(path)
        descriptors = [os.dup(self._pinned_root.descriptor)]
        chain = []
        current = descriptors[0]
        current_path = self.root
        try:
            for part in parts[:-1]:
                flags = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                         | getattr(os, "O_NOFOLLOW", 0))
                child = os.open(part, flags, dir_fd=current)
                descriptors.append(child)
                opened = os.fstat(child)
                entry = os.stat(part, dir_fd=current, follow_symlinks=False)
                identity = (opened.st_dev, opened.st_ino)
                if (not stat.S_ISDIR(opened.st_mode)
                        or not stat.S_ISDIR(entry.st_mode)
                        or identity != (entry.st_dev, entry.st_ino)):
                    _fail()
                chain.append((current, part, child, identity))
                current = child
                current_path = current_path / part
            return parts[-1], current_path, descriptors, chain
        except BaseException:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise

    def _revalidate(self, chain):
        for parent, name, child, identity in chain:
            opened = os.fstat(child)
            entry = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (not stat.S_ISDIR(opened.st_mode)
                    or not stat.S_ISDIR(entry.st_mode)
                    or (opened.st_dev, opened.st_ino) != identity
                    or (entry.st_dev, entry.st_ino) != identity):
                _fail()
        self._pinned_root.revalidate()

    def revalidate(self):
        self._pinned_root.revalidate()

    def regular_exists(self, path):
        descriptors = []
        try:
            name, _parent_path, descriptors, chain = self._open_parent(path)
            try:
                entry = os.stat(name, dir_fd=descriptors[-1], follow_symlinks=False)
            except FileNotFoundError:
                self._revalidate(chain)
                return False
            if (not stat.S_ISREG(entry.st_mode) or entry.st_nlink != 1):
                _fail()
            self._revalidate(chain)
            return True
        except (OSError, ValueError):
            _fail()
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def read_text(self, path):
        descriptors = []
        file_descriptor = None
        try:
            name, parent_path, descriptors, chain = self._open_parent(path)
            parent_stat = os.fstat(descriptors[-1])
            parent = PinnedDirectory(
                parent_path, descriptors[-1],
                (parent_stat.st_dev, parent_stat.st_ino),
            )
            file_descriptor = parent.open_regular(name, os.O_RDONLY)
            chunks = []
            total = 0
            while True:
                chunk = os.read(
                    file_descriptor,
                    min(65_536, _MAX_DECLARATION_BYTES + 1 - total),
                )
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > _MAX_DECLARATION_BYTES:
                    _fail()
            parent.require_identity(file_descriptor, name)
            self._revalidate(chain)
            os.close(file_descriptor)
            file_descriptor = None
            return b"".join(chunks).decode("utf-8")
        except (OSError, UnicodeError, ValueError):
            _fail()
        finally:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError:
                    pass
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass


def _read_owned_text(path, declarations):
    try:
        return declarations.read_text(path)
    except Exception:
        _fail()


def _frontmatter(path, declarations, *, optional=False):
    text = _read_owned_text(path, declarations)
    if not text.startswith("---\n"):
        if optional:
            return None
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
    inline = [
        line for line in lines
        if re.match(r"^" + re.escape(key) + r":\s+.+$", line) is not None
    ]
    if inline:
        _fail()
    starts = [index for index, line in enumerate(lines) if line == key + ":"]
    if len(starts) > 1:
        _fail()
    if not starts:
        return []
    start = starts[0] + 1
    result = []
    for line in lines[start:]:
        if line.startswith("  - "):
            value = line[4:].strip().strip('"\'')
            if not value:
                _fail()
            result.append(value)
        elif not line.strip():
            continue
        elif line.startswith(" "):
            _fail()
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
        match = re.fullmatch(r"    (expected|required|reason):\s*(.+)", line)
        if match is None or current is None or match.group(1) in current:
            _fail()
        value = match.group(2).strip()
        if not value or len(value) > 4_096:
            _fail()
        current[match.group(1)] = value
    if current is not None:
        result.append(current)
    normalized = []
    for item in result:
        if (set(item) - {"id", "expected", "required", "reason"}
                or item.get("expected") not in {"SUCCESS", "FRICTION", "BLOCKED", "PARTIAL"}
                or "required" in item and item["required"] not in {"true", "false"}):
            _fail()
        normalized.append((
            item["id"], item["expected"], item.get("required", "true") == "true",
        ))
    if not normalized:
        _fail()
    return normalized


def _task_at(path, declarations):
    frontmatter = _frontmatter(path, declarations, optional=True)
    if frontmatter is None:
        return None
    values = _scalars(frontmatter)
    assignments = _assignments(frontmatter)
    if not {"id", "title", "route", "requires_auth"} <= set(values) or not assignments:
        _fail()
    if values["requires_auth"] not in {"true", "false"}:
        _fail()
    status = values.get("implementation_status")
    if status is not None and status not in _KNOWN_STATUSES:
        _fail()
    requires_auth = values["requires_auth"] == "true"
    return {"id": values["id"].lower(), "route": values["route"],
            "role": values.get("requires_role", "member" if requires_auth else "public"),
            "requires_auth": requires_auth,
            "status": status, "legacy": "implementation_status" not in values,
            "personas": assignments, "tags": _list(frontmatter, "tags"),
            "preconditions": _list(frontmatter, "preconditions"),
            "auth_fields": _list(frontmatter, "auth_fields")}


def _persona_index(root, declarations):
    directory = root / "personas"
    _owned_path(directory, root, directory=True)
    index = directory / "_index.md"
    _owned_path(index, root)
    text = _read_owned_text(index, declarations)
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


def _persona_defaults(declarations, persona_paths):
    result = {}
    for path in persona_paths:
        values = _scalars(_frontmatter(path, declarations)); persona_id = values.get("id")
        if not persona_id or persona_id in result or path.stem != persona_id:
            _fail()
        viewport = None
        match = re.search(r"width:\s*([0-9]+),\s*height:\s*([0-9]+)", values.get("viewport", ""))
        if match:
            viewport = match.group(1) + "x" + match.group(2); validate_viewport(viewport)
        result[persona_id] = (values.get("device", ""), viewport)
    return result


def _coverage_matrix_diagnostics(root, tasks, declarations):
    path = root / "coverage-matrix.md"
    if path.is_symlink():
        _fail()
    if not declarations.regular_exists(path):
        return ()
    _owned_path(path, root)
    lines = _read_owned_text(path, declarations).splitlines()
    direct_rows, indexed_rows = set(), {}
    mismatch = False
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
                mismatch = True
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
                    mismatch = True
                    continue
                persona_rows.add((task_id, persona_id, outcome))
            if persona_rows:
                if task_id in indexed_rows:
                    mismatch = True
                indexed_rows[task_id] = persona_rows
    expected = {
        (task["id"], persona_id, outcome)
        for task in tasks for persona_id, outcome, _required in task["personas"]
    }
    if direct_rows and direct_rows != expected:
        mismatch = True
    for task_id, rows in indexed_rows.items():
        authoritative = {row for row in expected if row[0] == task_id}
        if not authoritative or rows != authoritative:
            mismatch = True
    if indexed_rows and set().union(*indexed_rows.values()) != expected:
        mismatch = True
    if not direct_rows and not indexed_rows:
        mismatch = True
    return ("coverage_matrix_mismatch",) if mismatch else ()


def _suite(root, suite_id, declarations):
    matches = []
    for path in sorted((root / "suites").glob("*.md")) if (root / "suites").is_dir() else ():
        frontmatter = _frontmatter(path, declarations)
        if _scalars(frontmatter).get("id") == suite_id:
            matches.append({item.lower() for item in _list(frontmatter, "task_ids")})
    if len(matches) != 1 or not matches[0]:
        _fail()
    return matches[0]


class PersonaAdapter(Protocol):
    def discover(self, project_root: Path) -> VerificationProfile: ...
    def execute(self, case: PersonaCase) -> EvidenceRef: ...


class ProjectPersonaAdapter:
    def __init__(self, *, policy_path=None, policy_document=None, executor=None):
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
        if executor is not None and not callable(getattr(executor, "execute", None)):
            _fail()
        self._executor = executor
        self._profile = None

    def discover(self, project_root, *, target_origin=None, declaration_root=None):
        try:
            profile = self._discover(
                project_root, target_origin=target_origin,
                declaration_root=declaration_root,
            )
            self._profile = _snapshot_verification_profile(profile)
            return _snapshot_verification_profile(profile)
        except Exception:
            _fail()

    def execute(self, case):
        try:
            if self._executor is None or self._profile is None:
                raise ValueError
            profile = _snapshot_verification_profile(self._profile)
            supplied = _snapshot_persona_case(case)
            if profile.target_origin_digest is None:
                raise ValueError
            matches = tuple(
                item for item in profile.cases if item.case_id == supplied.case_id
            )
            if (len(matches) != 1
                    or matches[0]._origin_primitives() != supplied._origin_primitives()):
                raise ValueError
            bound_case = _snapshot_persona_case(matches[0])
            result = _snapshot_evidence_ref(
                self._executor.execute(bound_case, profile),
            )
            if (
                result.case_id != bound_case.case_id
                or result.persona_id != bound_case.persona_id
                or result.scenario_id != bound_case.scenario_id
                or result.route != bound_case.route
                or result.browser_engine != bound_case.browser_engine
                or result.viewport != bound_case.viewport
                or result.evaluation != bound_case.expected_outcome
                or result.authenticated != bound_case.requires_auth
                or result.proof_kind != "browser"
                or result.verification_profile_id != profile.profile_id
                or result.configured_engines != profile.configured_engines
                or result.target_origin_digest != profile.target_origin_digest
            ):
                raise ValueError
            return result
        except Exception:
            raise invalid_policy("invalid_verification_evidence")

    def _discover(self, project_root, *, target_origin=None, declaration_root=None):
        project = Path(project_root)
        if declaration_root is None:
            declared_root = project / "tests" / "ux"
            explicit_root = False
        else:
            if type(declaration_root) is not str:
                _fail()
            relative = Path(declaration_root)
            if (relative.is_absolute() or any(part == ".." for part in relative.parts)
                    or str(relative) not in {"."}):
                _fail()
            declared_root = project
            explicit_root = True
        if declared_root.is_symlink():
            _fail()
        if declared_root.exists():
            _owned_path(declared_root, project, directory=True)
            ux = declared_root
        elif explicit_root:
            _fail()
        else:
            profile = VerificationProfile(
                1, "not_declared", (), (), "not_declared", "not_declared", (),
            )
            return profile if target_origin is None else profile.bind_target_origin(target_origin)
        _owned_path(ux, project if ux == declared_root else ux, directory=True)
        _owned_path(ux / "tasks", ux, directory=True)
        _owned_path(ux / "personas", ux, directory=True)
        _reject_symlinks(ux)
        with _DeclarationTree(ux) as declarations:
            return self._discover_declarations(
                ux, declarations, target_origin=target_origin,
            )

    def _discover_declarations(self, ux, declarations, *, target_origin=None):
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
        config_exists = declarations.regular_exists(config_path)
        if config_exists:
            _owned_path(config_path, ux)
            try:
                config = parse_json_document(_read_owned_text(config_path, declarations))
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
        defaults = _persona_defaults(
            declarations, _persona_index(ux, declarations),
        )
        selected = _suite(ux, selected_suite, declarations) if selected_suite else None
        task_paths = sorted((ux / "tasks").rglob("*.md"))
        for path in task_paths:
            _owned_path(path, ux)
        declarations.revalidate()
        tasks = [
            task for path in task_paths
            if (task := _task_at(path, declarations)) is not None
        ]
        if not tasks:
            _fail()
        ids = [task["id"] for task in tasks]
        if len(ids) != len(set(ids)):
            _fail()
        coverage_diagnostics = _coverage_matrix_diagnostics(
            ux, tasks, declarations,
        )
        if selected is None and config_exists and "include_statuses" in config:
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
            runtime_origin or configured_origin, coverage_diagnostics,
        )
