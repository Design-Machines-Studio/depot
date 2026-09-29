"""Preserve and validate the evidence that supports a dm-review result."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit

from .dm_review_adapter import (
    ReviewRequest,
    _LANE_FIELDS,
    _RAW_FINDING_FIELDS,
    _RAW_LANE_OUTPUT_FIELDS,
    _document_digest,
    export_finding_contributions,
    required_text,
    translate_review_receipts,
)
from .owned_run import (
    ExactOwnedRun, _MAX_DIAGNOSTIC_BYTES, _MAX_DIAGNOSTIC_FILES,
    _bounded_diagnostic,
)
from ._translation import safe_reference


_REVIEW_WORKFLOWS = frozenset({"dm-review", "dm-review-loop", "pipeline", "pipeline-run"})
_HEAD_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REVIEW_SCOPE_RE = re.compile(r"repo-[0-9a-f]{12}-head-(?:[0-9a-f]{40}|[0-9a-f]{64})")


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(repository_root), *args),
        check=False, capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise ValueError("review source repository is unavailable")
    return result.stdout.strip()


def source_identity(repository_root: str | Path) -> tuple[str, str]:
    """Return a credential-free repository identity and the exact current HEAD."""
    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("review source repository is unavailable")
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if _HEAD_RE.fullmatch(head) is None:
        raise ValueError("review source head is invalid")
    probe = subprocess.run(
        ("git", "-C", str(root), "remote", "get-url", "origin"),
        check=False, capture_output=True, text=True, timeout=10,
    )
    remote = probe.stdout.strip() if probe.returncode == 0 else ""
    if remote:
        if "@" in remote and ":" in remote.split("@", 1)[-1] and not remote.startswith(("http://", "https://", "ssh://", "git://")):
            host, path = remote.split("@", 1)[-1].split(":", 1)
        else:
            parsed = urlsplit(remote)
            host, path = parsed.hostname or "", parsed.path.lstrip("/")
        path = path.removesuffix(".git").strip("/")
        identity = f"{host.lower()}/{path}" if host and path else ""
    else:
        common = Path(_git(root, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = root / common
        identity = "local-" + hashlib.sha256(
            str(common.resolve(strict=True)).encode("utf-8")
        ).hexdigest()
    if not identity:
        common = Path(_git(root, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = root / common
        identity = "local-" + hashlib.sha256(
            str(common.resolve(strict=True)).encode("utf-8")
        ).hexdigest()
    safe_reference(identity)
    return identity, head


def _regular_file(path: Path) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        value = os.fstat(descriptor)
        if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
            raise ValueError("review evidence is not an owned regular file")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65536, _MAX_DIAGNOSTIC_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_DIAGNOSTIC_BYTES:
                raise ValueError("review evidence exceeds bounded retention limits")
            chunks.append(chunk)
        final = os.fstat(descriptor)
        if (final.st_dev, final.st_ino) != (value.st_dev, value.st_ino):
            raise ValueError("review evidence identity changed while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _load_json(path: Path) -> object:
    try:
        return json.loads(_regular_file(path).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid review evidence JSON") from None


def bind_review_source(
    *,
    run_root: str | Path,
    repository_root: str | Path,
    request_path: str | Path,
    required_browser_cases: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Bind the existing review request to the exact source before dispatch."""
    run = ExactOwnedRun.open(Path(run_root))
    if run.workflow not in _REVIEW_WORKFLOWS:
        raise ValueError("exact-owned root is not a review owner")
    request_file = _source_path(request_path, run.root)
    parsed = _load_json(request_file)
    request = ReviewRequest.from_mapping(parsed)  # type: ignore[arg-type]
    if request.run_id != run.run_id:
        raise ValueError("review request does not match its exact-owned run")
    repository, head = source_identity(repository_root)
    if (
        request.source_repository is not None
        and (request.source_repository != repository or request.source_head != head)
    ):
        raise ValueError("review request source scope is stale")
    cases = request.required_browser_cases
    if required_browser_cases is not None:
        if (
            cases and tuple(required_browser_cases) != cases
        ):
            raise ValueError("review browser case scope changed")
        cases = tuple(required_browser_cases)
    bound = replace(
        request, source_repository=repository, source_head=head,
        required_browser_cases=cases,
    )
    original = os.lstat(request_file)
    encoded = (json.dumps(bound.to_dict(), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix="review-request-", dir=request_file.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        pending = memoryview(encoded)
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("review request write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        current = os.lstat(request_file)
        if (
            stat.S_ISLNK(current.st_mode)
            or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
        ):
            raise ValueError("review request changed while binding its source")
        os.replace(temporary, request_file)
        directory = os.open(request_file.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    validated = ReviewRequest.from_mapping(_load_json(request_file))
    if validated != bound:
        raise ValueError("review request source binding did not persist")
    return {
        "run_id": bound.run_id,
        "source_repository": repository,
        "source_head": head,
        "required_lanes": list(bound.required_lanes),
        "required_browser_cases": list(bound.required_browser_cases),
    }


def _validate_lane_source_coverage(
    request: ReviewRequest,
    lane_document: object,
    outputs_document: object,
) -> None:
    if (
        type(lane_document) is not dict
        or set(lane_document) != {"schema_version", "artifact_role", "run_id", "lanes"}
        or lane_document.get("schema_version") != 1
        or lane_document.get("artifact_role") != "review_lane_receipts"
        or lane_document.get("run_id") != request.run_id
        or type(lane_document.get("lanes")) is not list
        or type(outputs_document) is not dict
        or set(outputs_document) != {"schema_version", "artifact_role", "run_id", "outputs"}
        or outputs_document.get("schema_version") != 1
        or outputs_document.get("artifact_role") != "review_lane_raw_outputs"
        or outputs_document.get("run_id") != request.run_id
        or type(outputs_document.get("outputs")) is not list
    ):
        raise ValueError("required review lane evidence is missing or mismatched")

    outputs: dict[tuple[str, str], dict] = {}
    lane_names: set[str] = set()
    for raw in outputs_document["outputs"]:
        if type(raw) is not dict or set(raw) != _RAW_LANE_OUTPUT_FIELDS:
            raise ValueError("required review lane evidence is invalid")
        reviewer, lane = raw.get("reviewer"), raw.get("lane")
        findings = raw.get("findings")
        if (
            type(reviewer) is not str or not reviewer
            or type(lane) is not str or not lane
            or type(findings) is not list or lane in lane_names
        ):
            raise ValueError("required review lane evidence is invalid")
        lane_names.add(lane)
        for finding in findings:
            if (
                type(finding) is not dict or set(finding) != _RAW_FINDING_FIELDS
                or finding.get("reviewer") != reviewer or finding.get("lane") != lane
            ):
                raise ValueError("required review lane output is invalid")
        outputs[(reviewer, lane)] = raw

    lane_receipts: dict[tuple[str, str], dict] = {}
    for receipt in lane_document["lanes"]:
        if type(receipt) is not dict or set(receipt) != _LANE_FIELDS:
            raise ValueError("required review lane receipt is invalid")
        key = (receipt.get("reviewer"), receipt.get("lane"))
        output = outputs.get(key)
        evidence_refs = receipt.get("evidence_refs")
        if (
            output is None or key in lane_receipts
            or type(evidence_refs) is not list or not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
            or receipt.get("raw_output_ref") != (
                "contribution-inputs/raw-lane-output-sha256-"
                + _document_digest(output).removeprefix("sha256:") + ".json"
            )
            or receipt.get("raw_output_digest") != _document_digest(output)
            or type(receipt.get("finding_count")) is not int
            or receipt["finding_count"] != len(output["findings"])
        ):
            raise ValueError("required review lane receipt does not match its output")
        for reference in evidence_refs:
            safe_reference(reference)
        lane_receipts[key] = receipt

    if (
        lane_names != set(request.required_lanes)
        or len(lane_receipts) != len(request.required_lanes)
        or set(outputs) != set(lane_receipts)
    ):
        raise ValueError("required review lane coverage is incomplete")


def _validate_finding_result_sources(
    request: ReviewRequest,
    lane_document: object,
    outputs_document: object,
    findings_document: object,
    decisions_document: object,
) -> None:
    if (
        type(findings_document) is not dict
        or set(findings_document) != {"schema_version", "artifact_role", "run_id", "findings"}
        or findings_document.get("schema_version") != 1
        or findings_document.get("artifact_role") != "raw_finding_inventory"
        or findings_document.get("run_id") != request.run_id
        or type(findings_document.get("findings")) is not list
        or type(decisions_document) is not dict
        or set(decisions_document) != {
            "schema_version", "artifact_role", "run_id", "source_finding_count",
            "occurred_at", "decisions",
        }
        or decisions_document.get("schema_version") != 1
        or decisions_document.get("artifact_role") != "synthesis_decisions"
        or decisions_document.get("run_id") != request.run_id
        or type(decisions_document.get("source_finding_count")) is not int
        or type(decisions_document.get("decisions")) is not list
    ):
        raise ValueError("required finding result artifacts are invalid")
    raw = findings_document["findings"]
    decisions = decisions_document["decisions"]
    if decisions_document["source_finding_count"] != len(raw) or len(decisions) != len(raw):
        raise ValueError("synthesis decisions do not cover the raw findings")
    required_text(decisions_document["occurred_at"], "synthesis timestamp")
    lane_refs = {
        (item["reviewer"], item["lane"]): {
            safe_reference(value) for value in item["evidence_refs"]
        }
        for item in lane_document["lanes"]
    }
    output_findings = {}
    for output in outputs_document["outputs"]:
        for finding in output["findings"]:
            source_id = finding["source_finding_id"]
            if source_id in output_findings:
                raise ValueError("duplicate raw lane finding")
            output_findings[source_id] = finding
    raw_findings = {}
    for finding in raw:
        if type(finding) is not dict or set(finding) != _RAW_FINDING_FIELDS:
            raise ValueError("raw finding inventory is invalid")
        for field in _RAW_FINDING_FIELDS:
            required_text(finding[field], field.replace("_", " "))
        key = (finding["reviewer"], finding["lane"])
        evidence_ref = safe_reference(finding["evidence_ref"])
        if (
            finding["source_finding_id"] in raw_findings
            or evidence_ref not in lane_refs.get(key, set())
        ):
            raise ValueError("raw finding evidence is not bound to a selected lane")
        raw_findings[finding["source_finding_id"]] = {
            **finding, "evidence_ref": evidence_ref,
        }
    if raw_findings != output_findings:
        raise ValueError("raw finding inventory does not match selected lane outputs")
    roles = {
        "decisions": "synthesis-decisions",
        "raw_findings": "raw-finding-inventory",
        "lane_receipts": "lane-receipts",
        "raw_lane_outputs": "raw-lane-outputs",
    }
    documents = {
        "decisions": decisions_document,
        "raw_findings": findings_document,
        "lane_receipts": lane_document,
        "raw_lane_outputs": outputs_document,
    }
    references = {
        key: "contribution-inputs/" + roles[key] + "-sha256-"
        + _document_digest(document).removeprefix("sha256:") + ".json"
        for key, document in documents.items()
    }
    # Reuse the existing strict source-to-decision validator in memory. This
    # does not write optional contribution artifacts or receipts.
    export_finding_contributions(
        request, decisions_document, findings_document, lane_document,
        outputs_document, (), references,
    )


def _case_ids(value: object) -> set[str]:
    found: set[str] = set()
    pending = [value]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > 10000:
            raise ValueError("browser evidence exceeds bounded case inventory")
        if type(current) is dict:
            candidate = current.get("case_id")
            if type(candidate) is str:
                found.add(candidate)
            candidates = current.get("case_ids")
            if type(candidates) is list:
                found.update(item for item in candidates if type(item) is str)
            pending.extend(current.values())
        elif type(current) is list:
            pending.extend(current)
    return found


def _validate_browser_coverage(request: ReviewRequest, receipts: list[dict]) -> None:
    if not request.required_browser_cases:
        return
    evidence = set()
    for receipt in receipts:
        if receipt.get("stage") != "browser_verification":
            continue
        if receipt.get("status") not in {"complete", "completed", "succeeded"}:
            continue
        if (
            receipt.get("source_repository") != request.source_repository
            or receipt.get("source_head") != request.source_head
        ):
            continue
        evidence.update(_case_ids(receipt))
    if evidence != set(request.required_browser_cases):
        raise ValueError("required browser evidence does not match the selected cases")


def required_review_evidence_references(
    request: ReviewRequest,
    receipts: list[dict],
    lane_document: Mapping[str, object],
    outputs_document: Mapping[str, object],
) -> tuple[str, ...]:
    """Return only the source references required by the selected review scope."""
    references: set[str] = set()

    def add(value: object) -> None:
        if type(value) is str:
            references.add(safe_reference(value))

    request_rows = [
        value for value in receipts if value.get("stage") == "review_request"
    ]
    coverage_rows = [
        value for value in receipts if value.get("stage") == "coverage_matrix"
    ]
    if request_rows:
        add(request_rows[-1].get("authoritative_receipt"))
    if coverage_rows:
        add(coverage_rows[-1].get("authoritative_receipt"))
    for receipt in receipts:
        if (
            receipt.get("stage") != "browser_verification"
            or receipt.get("status") not in {"complete", "completed", "succeeded"}
            or receipt.get("source_repository") != request.source_repository
            or receipt.get("source_head") != request.source_head
            or not (_case_ids(receipt) & set(request.required_browser_cases))
        ):
            continue
        add(receipt.get("authoritative_receipt"))
        add(receipt.get("evidence_ref"))
        values = receipt.get("evidence_refs")
        if type(values) is list:
            for value in values:
                add(value)
    for lane in lane_document.get("lanes", ()):
        if type(lane) is not dict:
            continue
        values = lane.get("evidence_refs")
        if type(values) is list:
            for value in values:
                add(value)
    for output in outputs_document.get("outputs", ()):
        if type(output) is not dict:
            continue
        for finding in output.get("findings", ()):
            if type(finding) is dict:
                add(finding.get("evidence_ref"))
    return tuple(sorted(references))


_MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
_MARKDOWN_REFERENCE = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(<[^>]+>|\S+)", re.MULTILINE)


def _validate_retained_report(scope: Path) -> None:
    report = _regular_file(scope / "report.md").decode("utf-8")
    root = scope.resolve(strict=True)
    for match in (*_MARKDOWN_LINK.finditer(report), *_MARKDOWN_REFERENCE.finditer(report)):
        target = match.group(1)
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if target.startswith("#"):
            continue
        parsed = urlsplit(target)
        if (
            parsed.scheme == "mailto"
            or parsed.scheme in {"http", "https"} and parsed.netloc
            or not parsed.scheme and parsed.netloc and target.startswith("//")
        ):
            continue
        if parsed.scheme or parsed.netloc:
            raise ValueError("retained report contains an unsupported link")
        path = unquote(parsed.path) or "report.md"
        try:
            linked = (scope / path).resolve(strict=True)
        except OSError:
            raise ValueError("retained report link is missing") from None
        if not linked.is_relative_to(root):
            raise ValueError("retained report link escapes its evidence scope")
        _regular_file(linked)


def validate_review_source_coverage(
    request_document: object,
    receipts_document: object,
    lane_document: object,
    outputs_document: object,
    findings_document: object,
    decisions_document: object,
    *,
    repository: str,
    head: str,
) -> ReviewRequest:
    """Validate required source coverage independently of optional observers."""
    request = ReviewRequest.from_mapping(request_document)  # type: ignore[arg-type]
    if request.source_repository != repository or request.source_head != head:
        raise ValueError("review evidence repository or head changed")
    if type(receipts_document) is not list:
        raise ValueError("required review receipts are invalid")
    # Optional contribution observations may sit between review iterations.
    # Keep every required source row, including later rechecks, while excluding
    # optional rows whose failed export cannot determine required coverage.
    source_receipts = []
    for index, value in enumerate(receipts_document):
        if type(value) is dict and value.get("stage") in {
            "finding_contribution", "finding_contribution_coverage",
        }:
            continue
        if type(value) is not dict or value.get("sequence") != index:
            raise ValueError("required review receipt sequence is invalid")
        source_receipts.append({**value, "sequence": len(source_receipts)})
    coverage_positions = [
        index for index, value in enumerate(source_receipts)
        if value.get("stage") == "coverage_matrix"
    ]
    if not coverage_positions:
        raise ValueError("required review coverage receipt is missing")
    translate_review_receipts(source_receipts)
    request_rows = [
        value for value in source_receipts if value.get("stage") == "review_request"
    ]
    if not request_rows or (
        request_rows[-1].get("source_repository") != request.source_repository
        or request_rows[-1].get("source_head") != request.source_head
    ):
        raise ValueError("review request receipt does not bind this repository and HEAD")
    final_coverage = source_receipts[coverage_positions[-1]]
    expected = final_coverage.get("expected_lanes")
    completed = final_coverage.get("completed_lanes")
    degraded = final_coverage.get("degraded_lanes", [])
    unavailable = final_coverage.get("unavailable_lanes", [])
    if (
        type(expected) is not list or set(expected) != set(request.required_lanes)
        or type(completed) is not list or type(degraded) is not list
        or type(unavailable) is not list
        or set(completed) | set(degraded) != set(expected)
        or unavailable
        or final_coverage.get("source_repository") != request.source_repository
        or final_coverage.get("source_head") != request.source_head
        or final_coverage.get("required_browser_cases", []) != list(request.required_browser_cases)
    ):
        raise ValueError("required review lane coverage is incomplete")
    _validate_lane_source_coverage(request, lane_document, outputs_document)
    _validate_finding_result_sources(
        request, lane_document, outputs_document,
        findings_document, decisions_document,
    )
    _validate_browser_coverage(request, source_receipts)
    return request


def _source_path(path: str | Path, root: Path, *, allow_repository: bool = False, repository: Path | None = None) -> Path:
    candidate = Path(path)
    lexical = candidate.absolute()
    boundaries = [root] + ([repository] if allow_repository and repository is not None else [])
    for boundary in boundaries:
        try:
            relative = lexical.relative_to(boundary)
        except ValueError:
            continue
        cursor = boundary
        for segment in relative.parts:
            cursor = cursor / segment
            if cursor.is_symlink():
                raise ValueError("review evidence source path is unsafe")
        break
    resolved = candidate.resolve(strict=True)
    if candidate.is_symlink() or not resolved.is_file():
        raise ValueError("review evidence source path is unsafe")
    if resolved.is_relative_to(root):
        return resolved
    if allow_repository and repository is not None and resolved.is_relative_to(repository):
        return resolved
    raise ValueError("review evidence source is outside its owned boundary")


def _copy_file(source: Path, target: Path) -> int:
    data = _regular_file(source)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if target.exists():
        if _regular_file(target) != data:
            raise ValueError("retained review evidence conflicts with this retry")
        return len(data)
    descriptor = os.open(
        target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    identity = os.fstat(descriptor)
    try:
        pending = memoryview(data)
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("review evidence copy made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if hashlib.sha256(_regular_file(target)).digest() != hashlib.sha256(data).digest():
            raise ValueError("review evidence copy verification failed")
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            current = os.lstat(target)
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                target.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return len(data)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree(root: Path) -> None:
    for current, _directories, _files in os.walk(root, topdown=False, followlinks=False):
        _fsync_directory(Path(current))


def _replace_file_durably(source: Path, target: Path) -> None:
    data = _regular_file(source)
    descriptor, temporary_name = tempfile.mkstemp(prefix="review-update-", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        pending = memoryview(data)
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("review evidence update made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _merge_staged_evidence(staging: Path, destination: Path) -> None:
    files = sorted(
        path for path in staging.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    updates: list[tuple[Path, Path, bool]] = []
    for staged in files:
        relative = staged.relative_to(staging)
        target = destination / relative
        if not target.exists():
            updates.append((staged, target, False))
            continue
        previous = _regular_file(target)
        current = _regular_file(staged)
        if previous == current:
            continue
        if (
            relative.as_posix() == "report.md"
        ):
            updates.append((staged, target, True))
            continue
        if (
            relative.as_posix() != "review/authoritative-receipts.json"
            or not _receipt_append_only(target, staged)
        ):
            raise ValueError("retained review evidence conflicts with this retry")
        updates.append((staged, target, True))
    for staged, target, replace_existing in updates:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if replace_existing:
            _replace_file_durably(staged, target)
        else:
            _copy_file(staged, target)
            _fsync_directory(target.parent)
    _fsync_tree(destination)
    _fsync_directory(destination.parent)


def _remove_superseded_review_scopes(
    review_root: Path, destination: Path,
) -> None:
    """Remove only prior helper-created scopes after the new copy validates."""
    for child in tuple(review_root.iterdir()):
        if child == destination:
            continue
        if (
            child.name != "unbound"
            and _REVIEW_SCOPE_RE.fullmatch(child.name) is None
        ):
            raise ValueError("unexpected review recovery scope exists")
        if child.is_symlink() or not child.is_dir():
            raise ValueError("superseded review scope is unsafe")
        _bounded_diagnostic(child)
        shutil.rmtree(child)
    _fsync_directory(review_root)


def _receipt_append_only(existing: Path, candidate: Path) -> bool:
    try:
        previous = json.loads(_regular_file(existing).decode("utf-8"))
        updated = json.loads(_regular_file(candidate).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        return False
    return (
        type(previous) is list and type(updated) is list
        and len(updated) >= len(previous)
        and updated[:len(previous)] == previous
        and sum(
            1 for value in updated
            if type(value) is dict and value.get("stage") == "finding_contribution_coverage"
        ) <= 1
    )


def _copy_router_tree(source: Path, target: Path) -> tuple[int, int]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("private router receipt directory is unsafe")
    _validate_router_receipts(source)
    files = 0
    size = 0
    for current, directories, names in os.walk(source, followlinks=False):
        current_path = Path(current)
        for name in tuple(directories):
            child = current_path / name
            value = os.lstat(child)
            if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
                raise ValueError("private router receipt directory is unsafe")
        for name in names:
            child = current_path / name
            if child.suffix != ".json":
                raise ValueError("private router receipt directory has an unexpected file")
            relative = child.relative_to(source)
            copied = _copy_file(child, target / relative)
            files += 1
            size += copied
            if files > _MAX_DIAGNOSTIC_FILES or size > _MAX_DIAGNOSTIC_BYTES:
                raise ValueError("private router receipts exceed bounded retention limits")
    if not (target / "terminal-receipt-index.json").is_file():
        raise ValueError("private router receipt index is missing")
    _validate_router_receipts(target)
    return files, size


def _validate_router_receipts(directory: Path) -> None:
    """Require the indexed private dispatch receipts used by terminal reporting."""
    index = _load_json(directory / "terminal-receipt-index.json")
    if (
        type(index) is not dict or set(index) != {"schemaVersion", "receiptFiles"}
        or type(index["schemaVersion"]) is not int or index["schemaVersion"] != 1
        or type(index["receiptFiles"]) is not list
        or not index["receiptFiles"]
    ):
        raise ValueError("private router receipt index is invalid")
    for name in index["receiptFiles"]:
        if (
            type(name) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}\.json", name) is None
            or name == "terminal-receipt-index.json"
        ):
            raise ValueError("private router receipt index is invalid")
        receipt = _load_json(directory / name)
        if (
            type(receipt) is not dict or type(receipt.get("schemaVersion")) is not int
            or receipt["schemaVersion"] != 1
            or type(receipt.get("receiptId")) is not str
            or re.fullmatch(r"dispatch-[a-f0-9]{24}", receipt["receiptId"]) is None
            or type(receipt.get("requested")) is not dict
            or type(receipt.get("attempts")) is not list
            or any(type(attempt) is not dict for attempt in receipt["attempts"])
            or (receipt.get("served") is not None and type(receipt["served"]) is not dict)
            or type(receipt.get("fallback")) is not bool
        ):
            raise ValueError("private router receipt is invalid")


def _diagnostic(run: ExactOwnedRun) -> Path:
    registered = next((
        item for item in run._metadata["resources"] if item["kind"] == "diagnostic"
    ), None)
    if registered is None:
        return run.create_path("diagnostic", "diagnostic")
    path = run.root / registered["relative_path"]
    value = os.lstat(path)
    if (value.st_dev, value.st_ino) != (registered["device"], registered["inode"]):
        raise ValueError("review recovery directory identity changed")
    return path


def preserve_review_evidence(
    *,
    run_root: str | Path,
    repository_root: str | Path,
    request_path: str | Path,
    receipts_path: str | Path,
    lane_receipts_path: str | Path,
    raw_lane_outputs_path: str | Path,
    raw_findings_path: str | Path | None = None,
    decisions_path: str | Path | None = None,
    private_router_directory: str | Path | None = None,
    report_path: str | Path,
) -> dict[str, object]:
    """Copy exact review evidence into the run's bounded diagnostic root.

    Copying and byte verification finish before any source or worktree cleanup.
    Repeated calls are safe: matching files are reused and conflicting files
    fail without replacing the first sealed copy.
    """
    run = ExactOwnedRun.open(Path(run_root))
    if run.workflow not in _REVIEW_WORKFLOWS:
        raise ValueError("exact-owned root is not a review owner")
    repository = Path(repository_root).resolve(strict=True)
    repository_identity, head = source_identity(repository)
    sources: dict[str, Path] = {}
    for name, path in (
        ("review/request.json", request_path),
        ("review/authoritative-receipts.json", receipts_path),
        ("review/review-lane-receipts.json", lane_receipts_path),
        ("review/raw-lane-outputs.json", raw_lane_outputs_path),
        ("review/raw-finding-inventory.json", raw_findings_path),
        ("review/synthesis-decisions.json", decisions_path),
        ("report.md", report_path),
    ):
        if path is None:
            continue
        sources[name] = _source_path(
            path, run.root, allow_repository=name == "report.md",
            repository=repository,
        )

    parsed: dict[str, object] = {}
    for name in (
        "review/request.json", "review/authoritative-receipts.json",
        "review/review-lane-receipts.json", "review/raw-lane-outputs.json",
        "review/raw-finding-inventory.json", "review/synthesis-decisions.json",
        "report.md",
    ):
        path = sources.get(name)
        if path is not None:
            try:
                parsed[name] = json.loads(_regular_file(path).decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError, RecursionError):
                parsed[name] = None

    missing: list[str] = []
    for name in (
        "review/request.json", "review/authoritative-receipts.json",
        "review/review-lane-receipts.json", "review/raw-lane-outputs.json",
        "review/raw-finding-inventory.json", "review/synthesis-decisions.json",
    ):
        if name not in sources or parsed.get(name) is None:
            missing.append(name)
    router_source: Path | None = None
    if private_router_directory is not None:
        router_candidate = Path(private_router_directory).absolute()
        try:
            relative = router_candidate.relative_to(run.root)
        except ValueError:
            raise ValueError("private router receipts are outside the owned run") from None
        cursor = run.root
        for segment in relative.parts:
            cursor = cursor / segment
            if cursor.is_symlink():
                raise ValueError("private router receipt directory is unsafe")
        router_source = router_candidate.resolve(strict=True)
        if not router_source.is_relative_to(run.root):
            raise ValueError("private router receipts are outside the owned run")
    else:
        missing.append("private model-router receipts")

    recovery = _diagnostic(run)
    request = None
    scope = "unbound"
    # A parseable request can already prove an exact repository/HEAD even when
    # later coverage validation fails. Keep recoverable inputs under that
    # scope so a corrected closeout can reuse them without creating a second,
    # unbound recovery scope.
    try:
        candidate_request = ReviewRequest.from_mapping(parsed["review/request.json"])
        if (
            candidate_request.run_id == run.run_id
            and candidate_request.source_repository is not None
            and candidate_request.source_head is not None
        ):
            digest = hashlib.sha256(
                candidate_request.source_repository.encode("utf-8"),
            ).hexdigest()[:12]
            scope = f"repo-{digest}-head-{candidate_request.source_head}"
    except (KeyError, TypeError, ValueError):
        pass
    if not missing:
        try:
            request = validate_review_source_coverage(
                parsed["review/request.json"],
                parsed["review/authoritative-receipts.json"],
                parsed["review/review-lane-receipts.json"],
                parsed["review/raw-lane-outputs.json"],
                parsed["review/raw-finding-inventory.json"],
                parsed["review/synthesis-decisions.json"],
                repository=repository_identity, head=head,
            )
            if request.run_id != run.run_id:
                raise ValueError("review request does not match its exact-owned run")
        except (TypeError, ValueError):
            missing.append("required lane, browser, repository, or head coverage")

    if request is not None:
        try:
            references = required_review_evidence_references(
                request,
                parsed["review/authoritative-receipts.json"],
                parsed["review/review-lane-receipts.json"],
                parsed["review/raw-lane-outputs.json"],
            )
        except (TypeError, ValueError):
            references = ()
            missing.append("required evidence references are invalid")
        for reference in references:
            if reference.startswith(("url-sha256:", "sha256:")):
                continue
            if reference in sources:
                continue
            source = None
            for candidate in (
                run.root / reference, repository / reference,
                recovery / "review" / scope / reference,
            ):
                try:
                    source = _source_path(
                        candidate, run.root, allow_repository=True,
                        repository=repository,
                    )
                    break
                except (OSError, ValueError):
                    continue
            if source is None:
                missing.append("required evidence reference: " + reference)
            else:
                sources[reference] = source

    destination = recovery / "review" / scope
    parent = destination.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="review-stage-", dir=parent))
    copied_files = 0
    copied_bytes = 0
    try:
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError("retained review evidence path is unsafe")
            for current, directories, names in os.walk(destination, followlinks=False):
                current_path = Path(current)
                for name in tuple(directories):
                    child = current_path / name
                    value = os.lstat(child)
                    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
                        raise ValueError("retained review evidence contains an unsafe entry")
                for name in names:
                    child = current_path / name
                    relative = child.relative_to(destination)
                    copied_bytes += _copy_file(child, staging / relative)
                    copied_files += 1
        for relative, source in sources.items():
            target = staging / relative
            before = target.exists()
            if (
                before and relative in {"review/authoritative-receipts.json", "report.md"}
                and _regular_file(target) != _regular_file(source)
            ):
                if (
                    relative == "review/authoritative-receipts.json"
                    and not _receipt_append_only(target, source)
                ):
                    raise ValueError("authoritative review receipts changed outside append-only closeout")
                target.unlink()
                before = False
            copied_bytes += _copy_file(source, target)
            if not before:
                copied_files += 1
        if private_router_directory is not None:
            if router_source is None:
                raise ValueError("private router receipt directory is unavailable")
            _copy_router_tree(
                router_source, staging / router_source.relative_to(run.root),
            )
        copied_files, copied_bytes = _bounded_diagnostic(staging)
        if copied_files > _MAX_DIAGNOSTIC_FILES or copied_bytes > _MAX_DIAGNOSTIC_BYTES:
            raise ValueError("review evidence exceeds bounded retention limits")
        if destination.exists():
            _merge_staged_evidence(staging, destination)
            shutil.rmtree(staging)
        else:
            _fsync_tree(staging)
            os.replace(staging, destination)
            _fsync_directory(parent)
        if not missing and request is not None:
            # Re-read the durable copy before it can authorize cleanup.
            validate_review_source_coverage(
                _load_json(destination / "review/request.json"),
                _load_json(destination / "review/authoritative-receipts.json"),
                _load_json(destination / "review/review-lane-receipts.json"),
                _load_json(destination / "review/raw-lane-outputs.json"),
                _load_json(destination / "review/raw-finding-inventory.json"),
                _load_json(destination / "review/synthesis-decisions.json"),
                repository=repository_identity, head=head,
            )
            for reference in required_review_evidence_references(
                request,
                _load_json(destination / "review/authoritative-receipts.json"),
                _load_json(destination / "review/review-lane-receipts.json"),
                _load_json(destination / "review/raw-lane-outputs.json"),
            ):
                if reference.startswith(("url-sha256:", "sha256:")):
                    continue
                _regular_file(destination / reference)
            _validate_retained_report(destination)
            _remove_superseded_review_scopes(recovery / "review", destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    return {
        "status": "complete" if not missing else "incomplete",
        "recovery_path": str(recovery),
        "evidence_path": str(destination),
        "files": copied_files,
        "bytes": copied_bytes,
        "missing": missing,
    }


def has_preserved_review_evidence(diagnostic: Path) -> bool:
    """Revalidate the sealed required evidence before successful root cleanup."""
    review_root = diagnostic / "review"
    if not review_root.is_dir() or review_root.is_symlink():
        return False
    scopes = [path for path in review_root.iterdir() if path.is_dir() and not path.is_symlink()]
    if len(scopes) != 1:
        return False
    scope = scopes[0]
    try:
        request = _load_json(scope / "review/request.json")
        receipts = _load_json(scope / "review/authoritative-receipts.json")
        lane_receipts = _load_json(scope / "review/review-lane-receipts.json")
        raw_outputs = _load_json(scope / "review/raw-lane-outputs.json")
        raw_findings = _load_json(scope / "review/raw-finding-inventory.json")
        decisions = _load_json(scope / "review/synthesis-decisions.json")
        parsed_request = ReviewRequest.from_mapping(request)  # type: ignore[arg-type]
        if parsed_request.source_repository is None or parsed_request.source_head is None:
            return False
        expected_scope = (
            "repo-" + hashlib.sha256(parsed_request.source_repository.encode("utf-8")).hexdigest()[:12]
            + "-head-" + parsed_request.source_head
        )
        if scope.name != expected_scope:
            return False
        validate_review_source_coverage(
            request, receipts, lane_receipts, raw_outputs, raw_findings, decisions,
            repository=parsed_request.source_repository,
            head=parsed_request.source_head,
        )
        for reference in required_review_evidence_references(
            parsed_request, receipts, lane_receipts, raw_outputs,
        ):
            if reference.startswith(("url-sha256:", "sha256:")):
                continue
            _regular_file(scope / reference)
        private_router = scope / "receipts/private/router"
        if not private_router.is_dir() or private_router.is_symlink():
            return False
        _validate_router_receipts(private_router)
        report = scope / "report.md"
        if not _regular_file(report).strip():
            return False
        _validate_retained_report(scope)
        return True
    except (OSError, TypeError, ValueError):
        return False
