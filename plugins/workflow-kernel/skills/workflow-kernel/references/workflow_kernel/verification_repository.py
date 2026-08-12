"""Profile validation, Git identity, and filesystem fingerprinting primitives."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .verification_errors import VerificationPlannerError
from .verification_contract import (
    BOUNDARIES, BOUNDARY_CHOICES, CACHE_POLICIES, COMMIT_PATTERN, OWNERS,
    TIERS,
)
from .verification_execution import (
    BASE_EXECUTION_ENVIRONMENT, FIXED_SUBPROCESS_PATH, MAX_COMMAND_SECONDS,
    run_bounded_capture,
)
from .verification_receipts import (
    digest as _digest,
)


PROFILE_SCHEMA_VERSION = 1
PLAN_SCHEMA_VERSION = 1
RISK_CHOICES = ("low", "medium", "high")
RISKS = frozenset(RISK_CHOICES)
PACKAGE_SELECTORS = frozenset({"none", "go_changed"})
PROFILE_KEYS = frozenset({"schema_version", "profile_id", "lanes"})
LANE_KEYS = frozenset({
    "id", "tier", "cadences", "owner", "argv", "changed_paths",
    "input_paths", "package_selector", "declared_dependents", "required",
    "cache", "risks", "cache_environment", "required_environment",
    "execution_paths", "execution_environment", "after",
    "mutates_repository", "timeout_seconds",
})
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ENV_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
MAX_LANES = 64
MAX_PATHS = 100_000
MAX_ARGUMENTS = 256
MAX_ITEMS = 256
MAX_STRING = 4096
MAX_GIT_SECONDS = 30
MAX_TREE_OUTPUT_BYTES = 16 * 1024 * 1024
def _closed(document, allowed, label):
    if type(document) is not dict:
        raise VerificationPlannerError(f"{label} must be an object")
    extra = set(document) - set(allowed)
    if extra:
        raise VerificationPlannerError(f"{label} contains unknown fields")


def _string(value, label, *, pattern=None):
    if (
        type(value) is not str or not value or len(value) > MAX_STRING
        or "\x00" in value
    ):
        raise VerificationPlannerError(f"{label} must be a bounded string")
    if pattern is not None and not pattern.fullmatch(value):
        raise VerificationPlannerError(f"{label} has an invalid format")
    return value


def _relative_path(value, label):
    value = _string(value, label)
    if (
        value.startswith(("/", "\\", "-")) or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise VerificationPlannerError(f"{label} must be a safe relative path")
    return value


def _glob(value, label):
    value = _string(value, label)
    if (
        value.startswith(("/", "\\", "-")) or "\\" in value
        or any(part == ".." for part in value.split("/"))
        or any(character in value for character in "[]{}")
    ):
        raise VerificationPlannerError(f"{label} must be a safe relative glob")
    return value


def _string_list(value, label, validator=_string, *, unique=True):
    if type(value) is not list or len(value) > MAX_ITEMS:
        raise VerificationPlannerError(f"{label} must be a bounded array")
    result = [validator(item, f"{label} item") for item in value]
    if unique and len(result) != len(set(result)):
        raise VerificationPlannerError(f"{label} contains duplicates")
    return result


def _environment_names(lane, field, label):
    names = _string_list(
        lane.get(field, []), f"{label} {field}",
        lambda value, item_label: _string(
            value, item_label, pattern=ENV_PATTERN,
        ),
    )
    if any(name not in BASE_EXECUTION_ENVIRONMENT for name in names):
        raise VerificationPlannerError(
            f"{label} requests an unapproved environment name",
        )
    return names


def _validate_lane(lane, index):
    label = f"lane {index}"
    _closed(lane, LANE_KEYS, label)
    lane_id = _string(lane.get("id"), f"{label} id", pattern=ID_PATTERN)
    tier = lane.get("tier")
    owner = lane.get("owner")
    cache = lane.get("cache", "content")
    package_selector = lane.get("package_selector", "none")
    if tier not in TIERS or owner not in OWNERS:
        raise VerificationPlannerError(f"{label} has an invalid tier or owner")
    if cache not in CACHE_POLICIES or package_selector not in PACKAGE_SELECTORS:
        raise VerificationPlannerError(f"{label} has an invalid cache or selector")
    cadences = _string_list(lane.get("cadences"), f"{label} cadences")
    if not cadences or any(value not in BOUNDARIES for value in cadences):
        raise VerificationPlannerError(f"{label} has invalid cadences")
    argv = _string_list(lane.get("argv"), f"{label} argv", unique=False)
    if len(argv) > MAX_ARGUMENTS or owner == "local" and not argv:
        raise VerificationPlannerError(f"{label} requires bounded local argv")
    placeholder_count = argv.count("{packages}")
    if package_selector == "go_changed" and placeholder_count != 1:
        raise VerificationPlannerError(
            f"{label} go_changed lane requires one packages placeholder",
        )
    if package_selector != "go_changed" and placeholder_count:
        raise VerificationPlannerError(
            f"{label} packages placeholder requires go_changed selector",
        )
    changed_paths = _string_list(
        lane.get("changed_paths", []), f"{label} changed_paths", _glob,
    )
    input_paths = _string_list(
        lane.get("input_paths", []), f"{label} input_paths", _glob,
    )
    execution_paths = _string_list(
        lane.get("execution_paths", []), f"{label} execution_paths", _glob,
    )
    if cache == "content" and owner == "local" and not input_paths:
        raise VerificationPlannerError(
            f"{label} content cache requires input_paths",
        )
    if owner == "local" and not execution_paths:
        raise VerificationPlannerError(
            f"{label} local execution requires execution_paths",
        )
    dependents = lane.get("declared_dependents", {})
    if type(dependents) is not dict or len(dependents) > MAX_ITEMS:
        raise VerificationPlannerError(f"{label} dependents must be bounded")
    canonical_dependents = {
        _package(package, f"{label} dependent key"): _string_list(
            values, f"{label} dependents for {package}", _package,
        )
        for package, values in dependents.items()
    }
    required = lane.get("required", True)
    if type(required) is not bool:
        raise VerificationPlannerError(f"{label} required must be boolean")
    risks = _string_list(lane.get("risks", list(RISK_CHOICES)), f"{label} risks")
    if not risks or any(value not in RISKS for value in risks):
        raise VerificationPlannerError(f"{label} has invalid risks")
    cache_environment = _environment_names(
        lane, "cache_environment", label,
    )
    required_environment = _environment_names(
        lane, "required_environment", label,
    )
    execution_environment = _environment_names(
        lane, "execution_environment", label,
    )
    if not set(required_environment) <= set(cache_environment):
        raise VerificationPlannerError(
            f"{label} required environment must also bind the cache key",
        )
    if not set(execution_environment) <= set(cache_environment):
        raise VerificationPlannerError(
            f"{label} execution environment must also bind the cache key",
        )
    if (
        owner == "local"
        and not (
            tier == "doctor" and argv == ["git", "diff", "--check"]
        )
        and (
            "DM_VERIFICATION_SUBSTRATE" not in required_environment
            or "DM_VERIFICATION_SUBSTRATE" not in execution_environment
        )
    ):
        raise VerificationPlannerError(
            f"{label} candidate execution requires a host containment substrate",
        )
    after = _string_list(
        lane.get("after", []), f"{label} after",
        lambda value, item_label: _string(
            value, item_label, pattern=ID_PATTERN,
        ),
    )
    mutates_repository = lane.get("mutates_repository", False)
    timeout_seconds = lane.get("timeout_seconds", MAX_COMMAND_SECONDS)
    if type(mutates_repository) is not bool:
        raise VerificationPlannerError(
            f"{label} mutates_repository must be boolean",
        )
    if (
        type(timeout_seconds) is not int or timeout_seconds < 1
        or timeout_seconds > MAX_COMMAND_SECONDS
    ):
        raise VerificationPlannerError(
            f"{label} timeout_seconds must be a bounded integer",
        )
    return {
        "id": lane_id, "tier": tier, "cadences": cadences, "owner": owner,
        "argv": argv, "changed_paths": changed_paths,
        "input_paths": input_paths, "execution_paths": execution_paths,
        "package_selector": package_selector,
        "declared_dependents": canonical_dependents, "required": required,
        "cache": cache, "risks": risks,
        "cache_environment": cache_environment,
        "required_environment": required_environment,
        "execution_environment": execution_environment, "after": after,
        "mutates_repository": mutates_repository,
        "timeout_seconds": timeout_seconds,
    }


def validate_profile(document):
    """Validate and return the closed canonical repository profile."""
    _closed(document, PROFILE_KEYS, "verification profile")
    if document.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise VerificationPlannerError("unsupported verification profile schema")
    profile_id = _string(document.get("profile_id"), "profile_id", pattern=ID_PATTERN)
    lanes = document.get("lanes")
    if type(lanes) is not list or not lanes or len(lanes) > MAX_LANES:
        raise VerificationPlannerError("lanes must be a non-empty bounded array")
    canonical_lanes = [
        _validate_lane(lane, index) for index, lane in enumerate(lanes)
    ]
    lane_ids = [lane["id"] for lane in canonical_lanes]
    if len(lane_ids) != len(set(lane_ids)):
        raise VerificationPlannerError("lane ids must be unique")
    lanes_by_id = {lane["id"]: lane for lane in canonical_lanes}
    if any(
        dependency not in lanes_by_id or dependency == lane["id"]
        for lane in canonical_lanes for dependency in lane["after"]
    ):
        raise VerificationPlannerError("lane dependency is unknown or self-referential")
    ordered = []
    pending = list(canonical_lanes)
    while pending:
        ready = [
            lane for lane in pending
            if set(lane["after"]) <= {item["id"] for item in ordered}
        ]
        if not ready:
            raise VerificationPlannerError("lane dependencies contain a cycle")
        for lane in ready:
            ordered.append(lane)
            pending.remove(lane)
    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "profile_id": profile_id,
        "lanes": ordered,
    }


def _package(value, label):
    value = _string(value, label)
    if value == "." or value == "./...":
        return value
    if not value.startswith("./"):
        raise VerificationPlannerError(f"{label} must be a relative Go package")
    _relative_path(value[2:], label)
    return value


@lru_cache(maxsize=1024)
def _glob_regex(pattern):
    result = ["^"]
    index = 0
    while index < len(pattern):
        if pattern[index:index + 3] == "**/":
            result.append("(?:.*/)?")
            index += 3
        elif pattern[index:index + 2] == "**":
            result.append(".*")
            index += 2
        elif pattern[index] == "*":
            result.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            result.append("[^/]")
            index += 1
        else:
            result.append(re.escape(pattern[index]))
            index += 1
    result.append("$")
    return re.compile("".join(result))


def _matches(path, patterns):
    return any(_glob_regex(pattern).fullmatch(path) for pattern in patterns)


def normalize_changed_paths(paths):
    if type(paths) not in {list, tuple} or len(paths) > MAX_PATHS:
        raise VerificationPlannerError("changed paths must be a bounded array")
    return sorted({
        _relative_path(path, "changed path")
        for path in paths
    })


def git_changed_paths(repository_root, base_ref, *, head_ref="HEAD",
                      include_worktree=False):
    """Return normalized Git changes without invoking a shell."""
    repository = Path(repository_root).resolve(strict=True)
    refs = [base_ref, head_ref]
    for ref in refs:
        _string(ref, "git ref")
        if ref.startswith("-"):
            raise VerificationPlannerError("git refs may not be options")
    commands = [[
        "git", "-C", str(repository), "diff", "--name-only", "-z",
        "--diff-filter=ACMRD", f"{base_ref}...{head_ref}",
    ]]
    if include_worktree:
        commands.extend([
            ["git", "-C", str(repository), "diff", "--name-only", "-z"],
            ["git", "-C", str(repository), "diff", "--cached", "--name-only", "-z"],
            ["git", "-C", str(repository), "ls-files", "--others",
             "--exclude-standard", "-z"],
        ])
    paths = []
    for command in commands:
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode != 0:
            raise VerificationPlannerError("unable to resolve changed paths")
        try:
            paths.extend(
                item.decode("utf-8")
                for item in result.stdout.split(b"\0") if item
            )
        except UnicodeDecodeError:
            raise VerificationPlannerError("changed path is not UTF-8") from None
    return normalize_changed_paths(paths)


def _resolve_commit(repository, value, label):
    value = _string(value, label)
    if value.startswith("-"):
        raise VerificationPlannerError(f"{label} may not be an option")
    result = subprocess.run(
        [
            "git", "-C", str(repository), "rev-parse", "--verify",
            f"{value}^{{commit}}",
        ],
        capture_output=True, check=False, text=True,
    )
    commit = result.stdout.strip()
    if (
        result.returncode != 0
        or COMMIT_PATTERN.fullmatch(commit) is None
    ):
        raise VerificationPlannerError(f"{label} is not a commit")
    return commit


def _go_packages(changed_paths, dependents):
    if any(path in {"go.mod", "go.sum", "go.work", "go.work.sum"} for path in changed_paths):
        return ["./..."]
    packages = set()
    for path in changed_paths:
        if not path.endswith((".go", ".templ")):
            continue
        parent = str(Path(path).parent).replace("\\", "/")
        packages.add("." if parent == "." else "./" + parent)
    pending = list(packages)
    while pending:
        package = pending.pop()
        for dependent in dependents.get(package, []):
            if dependent not in packages:
                packages.add(dependent)
                pending.append(dependent)
    return sorted(packages)


def _expanded_argv(lane, changed_paths):
    packages = []
    if lane["package_selector"] == "go_changed":
        packages = _go_packages(changed_paths, lane["declared_dependents"])
        if not packages:
            return [], []
    argv = []
    for argument in lane["argv"]:
        if argument == "{packages}":
            argv.extend(packages)
        else:
            argv.append(argument)
    return argv, packages


def _directory_may_contain(relative, patterns):
    return any(
        pattern == relative or pattern.startswith(relative + "/")
        or "**" in pattern
        for pattern in patterns
    )


def _hash_repository_contents(repository_fd, relative, object_format):
    parts = relative.split("/")
    opened = []
    parent_fd = repository_fd
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        for part in parts[:-1]:
            parent_fd = os.open(
                part, flags | getattr(os, "O_DIRECTORY", 0), dir_fd=parent_fd,
            )
            opened.append(parent_fd)
        descriptor = os.open(parts[-1], flags, dir_fd=parent_fd)
        opened.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise VerificationPlannerError(
                "verification inputs must be regular files",
            )
        digest = (
            hashlib.sha256()
            if object_format == "raw-sha256"
            else hashlib.new(object_format)
        )
        if object_format != "raw-sha256":
            digest.update(
                f"blob {metadata.st_size}\0".encode("ascii"),
            )
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        # Git records regular files as either 100644 or 100755; group/other
        # write bits are not part of a tree entry. Normalize the live mode to
        # the same representation so cooperative umasks (for example 0002)
        # do not make an unchanged checkout differ from its committed tree.
        git_mode = 0o755 if metadata.st_mode & stat.S_IXUSR else 0o644
        return git_mode, digest.hexdigest()
    except (FileNotFoundError, NotADirectoryError, OSError):
        raise VerificationPlannerError(
            "verification input identity changed during hashing",
        ) from None
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def _hash_repository_file(repository_fd, relative):
    return _hash_repository_contents(
        repository_fd, relative, "raw-sha256",
    )


def _hash_repository_blob(repository_fd, relative, object_format):
    return _hash_repository_contents(
        repository_fd, relative, object_format,
    )


def _input_digests(repository, pattern_sets):
    pattern_sets = sorted(set(pattern_sets))
    records = {patterns: [] for patterns in pattern_sets}
    if not pattern_sets:
        return {}
    count = 0
    object_format = _repository_object_format(repository)
    repository_fd = os.open(
        repository, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        for root, directories, filenames in os.walk(
            repository, topdown=True, followlinks=False,
        ):
            relative_root = Path(root).relative_to(repository)
            directories.sort()
            filenames.sort()
            if relative_root == Path("."):
                directories[:] = [name for name in directories if name != ".git"]
                filenames = [name for name in filenames if name != ".git"]
            for directory in tuple(directories):
                path = Path(root) / directory
                relative = path.relative_to(repository).as_posix()
                if path.is_symlink() and any(
                    _directory_may_contain(relative, patterns)
                    for patterns in pattern_sets
                ):
                    raise VerificationPlannerError(
                        "verification input directories may not be symlinks",
                    )
            for filename in filenames:
                path = Path(root) / filename
                relative = path.relative_to(repository).as_posix()
                matched = [
                    patterns for patterns in pattern_sets
                    if _matches(relative, patterns)
                ]
                if not matched:
                    continue
                count += 1
                if count > MAX_PATHS:
                    raise VerificationPlannerError(
                        "verification input set is too large",
                    )
                mode, digest = _hash_repository_blob(
                    repository_fd, relative, object_format,
                )
                for patterns in matched:
                    records[patterns].append([relative, mode, digest])
    finally:
        os.close(repository_fd)
    return {
        patterns: _digest(sorted(items, key=lambda item: item[0]))
        for patterns, items in records.items()
    }


def _git_file(repository, commit, relative, label):
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise VerificationPlannerError(
            f"{label} is unavailable from the trusted base commit",
        )
    return result.stdout


@lru_cache(maxsize=32)
def _repository_object_format(repository):
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--show-object-format"],
            capture_output=True, check=False, text=True,
            timeout=MAX_COMMAND_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise VerificationPlannerError(
            "unable to inspect repository object format",
        ) from None
    object_format = result.stdout.strip()
    if result.returncode != 0 or object_format not in {"sha1", "sha256"}:
        raise VerificationPlannerError(
            "unable to inspect repository object format",
        )
    return object_format


def _tree_input_digests(repository, commit, pattern_sets):
    pattern_sets = sorted(set(pattern_sets))
    records = {patterns: [] for patterns in pattern_sets}
    if not pattern_sets:
        return {}
    result = run_bounded_capture(
        ["git", "-C", str(repository), "ls-tree", "-r", "-z", commit],
        repository, {"PATH": FIXED_SUBPROCESS_PATH}, MAX_GIT_SECONDS,
        max_output_bytes=MAX_TREE_OUTPUT_BYTES,
        inspect_descendants=False,
    )
    if result["exit_code"] != 0 or result["reason"] != "command_completed":
        raise VerificationPlannerError("unable to inspect trusted base commit")
    entries = []
    total_entries = 0
    for entry in result["stdout"].split(b"\0"):
        if not entry:
            continue
        total_entries += 1
        if total_entries > MAX_PATHS:
            raise VerificationPlannerError(
                "verification repository tree is too large",
            )
        try:
            metadata, encoded_path = entry.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
            relative = encoded_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise VerificationPlannerError(
                "trusted base tree contains an invalid entry",
            ) from None
        matched = [
            patterns for patterns in pattern_sets
            if _matches(relative, patterns)
        ]
        if object_type != "blob" or not matched:
            continue
        entries.append((relative, mode, object_id, matched))
    for relative, mode, object_id, matched in entries:
        record = [
            relative, int(mode, 8) & 0o7777,
            object_id,
        ]
        for patterns in matched:
            records[patterns].append(record)
    return {
        patterns: _digest(sorted(items, key=lambda item: item[0]))
        for patterns, items in records.items()
    }


def _tree_input_digest(repository, commit, patterns):
    return _tree_input_digests(repository, commit, {patterns})[patterns]


def _environment_digest(names, environment):
    return _digest([
        [name, hashlib.sha256(environment.get(name, "").encode("utf-8")).hexdigest()]
        for name in names
    ])


def _repository_scope_digest(repository):
    return _digest({"repository_root": str(Path(repository).resolve(strict=True))})


def _repository_file(repository, relative, label):
    relative = _relative_path(relative, label)
    candidate = repository / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(repository)
    except (OSError, ValueError):
        raise VerificationPlannerError(
            f"{label} must resolve inside the repository",
        ) from None
    current = repository
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise VerificationPlannerError(f"{label} may not traverse symlinks")
    if not resolved.is_file():
        raise VerificationPlannerError(f"{label} must be a regular file")
    return relative


def _timestamp(value, label):
    value = _string(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise VerificationPlannerError(f"{label} must be ISO-8601") from None
    if parsed.tzinfo is None:
        raise VerificationPlannerError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _execution_patterns(profile):
    return tuple(sorted({
        pattern
        for lane in profile["lanes"]
        for pattern in lane["execution_paths"]
    }))


def _execution_digest(
    profile, repository, environment, *, path_digest=None,
):
    patterns = _execution_patterns(profile)
    if path_digest is None:
        path_digest = _input_digests(repository, {patterns}).get(
            patterns, _digest([]),
        )
    environment_names = sorted({
        name
        for lane in profile["lanes"]
        for name in lane["execution_environment"]
    })
    return _digest({
        "paths": path_digest,
        "environment": _environment_digest(environment_names, environment),
    })


def _execution_digest_at_commit(profile, repository, commit, environment):
    return _execution_digest(
        profile, repository, environment,
        path_digest=_tree_input_digest(
            repository, commit, _execution_patterns(profile),
        ),
    )


# Public lower-layer interfaces consumed by planning and execution.
closed_document = _closed
bounded_string = _string
repository_file = _repository_file
resolve_commit = _resolve_commit
git_file = _git_file
hash_repository_file = _hash_repository_file
input_digests = _input_digests
tree_input_digests = _tree_input_digests
timestamp = _timestamp
execution_digest = _execution_digest
execution_digest_at_commit = _execution_digest_at_commit
execution_patterns = _execution_patterns
environment_digest = _environment_digest
expanded_argv = _expanded_argv
matches = _matches
repository_scope_digest = _repository_scope_digest
