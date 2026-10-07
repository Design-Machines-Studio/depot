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
    _LANE_FIELDS, _LANE_V2_FIELDS, validate_evidence_input,
    _RAW_FINDING_FIELDS,
    _RAW_LANE_OUTPUT_FIELDS,
    _document_digest,
    export_finding_contributions,
    required_text,
    translate_review_receipts,
)
from .owned_run import (
    ExactOwnedRun, _MAX_DIAGNOSTIC_BYTES, _MAX_DIAGNOSTIC_FILES,
    _bounded_diagnostic, BoundedDiagnosticLimitError,
)
from .schema import (
    ErrorMessage,
)
from ._translation import safe_reference
from .redaction import contains_secret_shape


_REVIEW_WORKFLOWS = frozenset({"dm-review", "dm-review-loop", "pipeline", "pipeline-run"})
_HEAD_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_REVIEW_SCOPE_RE = re.compile(r"repo-[0-9a-f]{12}-head-(?:[0-9a-f]{40}|[0-9a-f]{64})")


_REPORT_LINK_FAILURES = {
    "review_report_link_missing": (
        "missing_evidence", ErrorMessage.REVIEW_REPORT_LINK_MISSING.value,
    ),
    "review_report_link_unsupported": (
        "invalid_schema", ErrorMessage.REVIEW_REPORT_LINK_UNSUPPORTED.value,
    ),
    "review_report_link_escapes_scope": (
        "unsafe_payload", ErrorMessage.REVIEW_REPORT_LINK_ESCAPES_SCOPE.value,
    ),
    "review_report_link_target_unsafe": (
        "unsafe_payload", ErrorMessage.REVIEW_REPORT_LINK_UNSAFE.value,
    ),
}


class ReviewCloseoutValidationError(ValueError):
    """Closed, redacted report-link failure for the preservation CLI."""

    def __init__(self, reason_code: str, reference: str | None = None):
        if reason_code not in _REPORT_LINK_FAILURES:
            raise ValueError("unknown review report validation reason")
        self.reason_code = reason_code
        self.code, self.message = _REPORT_LINK_FAILURES[reason_code]
        self.reference = None
        if reference is not None:
            try:
                normalized = safe_reference(reference)
            except (TypeError, ValueError):
                pass
            else:
                if not contains_secret_shape(normalized):
                    self.reference = normalized
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        details: dict[str, object] = {
            "reason_code": self.reason_code,
            "field": "report.md",
        }
        if self.reference is not None:
            details["path"] = self.reference
        return {"error": {
            "code": self.code,
            "message": self.message,
            "details": details,
        }}


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
                raise BoundedDiagnosticLimitError("review evidence exceeds bounded retention limits")
            chunks.append(chunk)
        final = os.fstat(descriptor)
        if (final.st_dev, final.st_ino) != (value.st_dev, value.st_ino):
            raise ValueError("review evidence identity changed while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _unique_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid review evidence JSON")
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError("invalid review evidence JSON")


def _load_json(path: Path) -> object:
    try:
        return json.loads(_regular_file(path).decode("utf-8"), object_pairs_hook=_unique_members, parse_constant=_invalid_constant)
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
        or lane_document.get("schema_version") not in {1, 2}
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
        if type(receipt) is not dict or set(receipt) != (_LANE_FIELDS if lane_document["schema_version"] == 1 else _LANE_V2_FIELDS):
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
        try:
            parsed = urlsplit(target)
        except ValueError:
            raise ReviewCloseoutValidationError(
                "review_report_link_unsupported",
            ) from None
        if (
            parsed.scheme == "mailto"
            or parsed.scheme in {"http", "https"} and parsed.netloc
            or not parsed.scheme and parsed.netloc and target.startswith("//")
        ):
            continue
        if parsed.scheme or parsed.netloc:
            raise ReviewCloseoutValidationError(
                "review_report_link_unsupported",
            )
        path = unquote(parsed.path) or "report.md"
        try:
            linked = (scope / path).resolve(strict=True)
        except OSError:
            raise ReviewCloseoutValidationError(
                "review_report_link_missing", path,
            ) from None
        except ValueError:
            raise ReviewCloseoutValidationError(
                "review_report_link_target_unsafe", path,
            ) from None
        if not linked.is_relative_to(root):
            raise ReviewCloseoutValidationError(
                "review_report_link_escapes_scope",
            )
        try:
            _regular_file(linked)
        except (OSError, ValueError):
            raise ReviewCloseoutValidationError(
                "review_report_link_target_unsafe", path,
            ) from None


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
    evidence_root: Path | None = None,
    repository_root: Path | None = None,
) -> ReviewRequest:
    """Validate required source coverage independently of optional observers."""
    request = ReviewRequest.from_mapping(request_document)  # type: ignore[arg-type]
    if request.source_repository != repository or request.source_head != head:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch", "review/request.json")
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
        raise EvidenceAssemblyError("aggregate_validation", "missing_evidence", "review/coverage.json")
    translate_review_receipts(source_receipts)
    request_rows = [
        value for value in source_receipts if value.get("stage") == "review_request"
    ]
    if not request_rows or (
        request_rows[-1].get("source_repository") != request.source_repository
        or request_rows[-1].get("source_head") != request.source_head
    ):
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch", "review/request.json")
    final_coverage = source_receipts[coverage_positions[-1]]
    expected = final_coverage.get("expected_lanes")
    completed = final_coverage.get("completed_lanes")
    degraded = final_coverage.get("degraded_lanes", [])
    unavailable = final_coverage.get("unavailable_lanes", [])
    if type(expected) is not list or any(type(lane) is not str for lane in expected):
        raise ValueError("required review coverage expected_lanes must be a string list")
    if set(expected) != set(request.required_lanes):
        missing_lanes = sorted(set(request.required_lanes) - set(expected))
        extra_lanes = sorted(set(expected) - set(request.required_lanes))
        raise ValueError(
            "required review lane coverage mismatch"
            f" (missing={missing_lanes}, unexpected={extra_lanes})"
        )
    if any(
        type(values) is not list or any(type(lane) is not str for lane in values)
        for values in (completed, degraded, unavailable)
    ):
        raise ValueError("required review coverage completed/degraded/unavailable lanes must be string lists")
    if set(completed) | set(degraded) != set(expected) or unavailable:
        missing_lanes = sorted(set(expected) - set(completed) - set(degraded))
        raise ValueError(
            "required review lanes are incomplete"
            f" (missing={missing_lanes}, degraded={sorted(degraded)}, unavailable={sorted(unavailable)})"
        )
    if final_coverage.get("source_repository") != request.source_repository:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch", "review/coverage.json")
    if final_coverage.get("source_head") != request.source_head:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch", "review/coverage.json")
    browser_cases = final_coverage.get("required_browser_cases")
    if type(browser_cases) is not list or browser_cases != list(request.required_browser_cases):
        raise ValueError(
            "review coverage required_browser_cases does not match the bound request"
            f" (expected={list(request.required_browser_cases)}, actual={browser_cases!r})"
        )
    _validate_lane_source_coverage(request, lane_document, outputs_document)
    _validate_finding_result_sources(
        request, lane_document, outputs_document,
        findings_document, decisions_document,
    )
    _validate_browser_coverage(request, source_receipts)
    if lane_document["schema_version"] != 2 or evidence_root is None:
        raise EvidenceAssemblyError("aggregate_validation", "missing_source_provenance", "review/review-lane-receipts.json")
    _validate_committed_coverage(request, receipts_document, lane_document, outputs_document,
                                 findings_document, decisions_document, evidence_root, repository_root)
    return request


def _source_path(path: str | Path, root: Path, *, allow_repository: bool = False, repository: Path | None = None) -> Path:
    candidate = Path(path)
    lexical = candidate.absolute()
    if ".." in candidate.parts:
        raise ValueError("review evidence source path is unsafe")
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
    else:
        raise ValueError("review evidence source is outside its owned boundary")
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
            raise EvidenceAssemblyError("retained_validation", "append_conflict")
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
            raise EvidenceAssemblyError("retained_validation", "append_conflict")
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
                raise BoundedDiagnosticLimitError("private router receipts exceed bounded retention limits")
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


def _preserve_review_evidence_locked(
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
    diagnostics: list[dict] = []
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
        try:
            sources[name] = _source_path(
                path, run.root, allow_repository=name == "report.md",
                repository=repository,
            )
        except FileNotFoundError:
            diagnostics.append({"stage": "preservation_input", "reason": "missing_evidence", "path": name})
        except (OSError, ValueError):
            diagnostics.append({"stage": "preservation_input", "reason": "unsafe_path", "path": name})

    evidence_source_root = sources.get("review/request.json", run.root / "review/request.json").parent.parent
    parsed: dict[str, object] = {}
    for name in (
        "review/request.json", "review/authoritative-receipts.json",
        "review/review-lane-receipts.json", "review/raw-lane-outputs.json",
        "review/raw-finding-inventory.json", "review/synthesis-decisions.json",
        "report.md",
    ):
        path = sources.get(name)
        if path is not None:
            if name == "report.md":
                _regular_file(path)
                continue
            try:
                parsed[name] = _load_json(path)
            except BoundedDiagnosticLimitError:
                raise
            except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
                parsed[name] = None
                diagnostics.append({"stage": "preservation_input", "reason": "invalid_evidence", "path": name})

    missing: list[str] = [item["path"] for item in diagnostics]
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
            raise EvidenceAssemblyError("preservation_input", "unsafe_path") from None
        cursor = run.root
        for segment in relative.parts:
            cursor = cursor / segment
            if cursor.is_symlink():
                raise EvidenceAssemblyError("preservation_input", "unsafe_path")
        try:
            router_source = router_candidate.resolve(strict=True)
        except FileNotFoundError:
            missing.append("private model-router receipts")
            diagnostics.append(EvidenceAssemblyError("preservation_input", "missing_evidence", relative.as_posix()).detail())
        if router_source is not None and not router_source.is_relative_to(run.root):
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
                evidence_root=evidence_source_root, repository_root=repository,
            )
            if request.run_id != run.run_id:
                raise ValueError("review request does not match its exact-owned run")
        except EvidenceAssemblyError as exc:
            missing.append(exc.reason)
            diagnostics.append(exc.detail())
        except (TypeError, ValueError):
            missing.append("required review coverage is invalid")
            diagnostics.append({"stage": "aggregate_validation", "reason": "invalid_evidence", "path": "review/coverage.json"})

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
                evidence_source_root / reference, run.root / reference, repository / reference,
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

    if type(parsed.get("review/authoritative-receipts.json")) is list:
        try:
            for reference in _committed_references(parsed["review/authoritative-receipts.json"], evidence_source_root):
                try:
                    sources.setdefault(reference, _source_path(evidence_source_root / reference, run.root))
                except FileNotFoundError:
                    missing.append("missing_evidence")
                    diagnostics.append(EvidenceAssemblyError("retained_validation", "missing_evidence", reference).detail())
                except (OSError, ValueError):
                    missing.append("unsafe_path")
                    diagnostics.append({"stage": "retained_validation", "reason": "unsafe_path", "path": "review/evidence.json"})
        except EvidenceAssemblyError as exc:
            missing.append(exc.reason)
            diagnostics.append(exc.detail())

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
                    # Keep the first copied receipt immutable and return the
                    # recoverable scope instead of surfacing the CLI's generic
                    # unsafe-payload error for this expected retry conflict.
                    missing.append(
                        "authoritative review receipts changed outside append-only closeout"
                    )
                    diagnostics.append({"stage": "retained_validation", "reason": "append_conflict", "path": "review/authoritative-receipts.json"})
                    continue
                target.unlink()
                before = False
            copied_bytes += _copy_file(source, target)
            if not before:
                copied_files += 1
        if router_source is not None:
            try:
                _copy_router_tree(router_source, staging / router_source.relative_to(run.root))
            except BoundedDiagnosticLimitError:
                raise
            except FileNotFoundError as exc:
                raise EvidenceAssemblyError("preservation_input", "missing_evidence", _relative_role(exc.filename, run.root)) from None
            except (OSError, ValueError):
                raise EvidenceAssemblyError("preservation_input", "invalid_evidence") from None
        copied_files, copied_bytes = _check_evidence_bound(staging, "preservation_input")
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
                evidence_root=destination, repository_root=repository,
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
        "diagnostics": diagnostics,
        "failure_exit": 6 if any(row["reason"] == "append_conflict" for row in diagnostics) else 2 if any(row["reason"] == "invalid_evidence" for row in diagnostics) else 3,
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
            evidence_root=scope,
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


class EvidenceAssemblyError(ValueError):
    """Closed evidence-operation diagnostics; never retain rejected input text."""
    REASONS = {
        "missing_evidence": (3, "missing_evidence"),
        "incomplete_inspection": (3, "missing_evidence"),
        "missing_source_provenance": (3, "missing_evidence"),
        "invalid_evidence": (2, "invalid_schema"),
        "digest_mismatch": (3, "unsafe_payload"),
        "source_scope_mismatch": (3, "unsafe_payload"),
        "unsafe_path": (3, "unsafe_payload"),
        "append_conflict": (6, "state_conflict"),
        "retention_limit": (3, "evidence_limit_exceeded"),
    }

    def __init__(self, stage, reason, role="review/evidence.json"):
        if stage not in {"lane_input", "lane_validation", "aggregate_validation", "preservation_input", "retained_validation"} or reason not in self.REASONS:
            raise ValueError("invalid evidence diagnostic")
        self.stage, self.reason = stage, reason
        if role not in {"review/evidence.json", "review/request.json", "review/authoritative-receipts.json", "review/review-lane-receipts.json", "review/raw-lane-outputs.json", "review/coverage.json"}:
            # Keep a validated relative reference; unsafe text gets the placeholder.
            try:
                normalized = safe_reference(role)
            except (TypeError, ValueError):
                normalized = None
            if normalized != role or role.startswith(("sha256:", "url-sha256:")) or contains_secret_shape(role):
                role = "review/evidence.json"
        self.role = role
        self.exit_code, self.code = self.REASONS[reason]
        super().__init__("required review evidence failed validation")

    def detail(self):
        return {"stage": self.stage, "reason": self.reason, "path": self.role}

    def to_dict(self):
        return {"error": {"code": self.code, "message": "required review evidence failed validation", "details": self.detail()}}


def preserve_review_evidence(**arguments):
    from .cli import _open_receipt_stream_lock
    import fcntl
    run = ExactOwnedRun.open(Path(arguments["run_root"]))
    path = Path(arguments["receipts_path"])
    # Containment and symlinks must precede opening the shared lock.
    try:
        _source_path(path, run.root)
    except FileNotFoundError:
        pass
    descriptor = _open_receipt_stream_lock(path)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return _preserve_review_evidence_locked(**arguments)
    except BoundedDiagnosticLimitError:
        raise EvidenceAssemblyError("preservation_input", "retention_limit") from None
    finally:
        os.close(descriptor)


def _relative_role(path, root):
    """Root-relative diagnostic role; EvidenceAssemblyError sanitizes the text."""
    try:
        return Path(path).absolute().relative_to(root).as_posix()
    except (TypeError, ValueError):
        return "review/evidence.json"


def _evidence_bytes(root, reference, stage):
    try:
        safe_reference(reference)
        if reference.startswith(("sha256:", "url-sha256:")):
            raise ValueError
        return _regular_file(_source_path(root / reference, root))
    except FileNotFoundError:
        raise EvidenceAssemblyError(stage, "missing_evidence", reference) from None
    except BoundedDiagnosticLimitError:
        raise EvidenceAssemblyError(stage, "retention_limit") from None
    except (OSError, TypeError, ValueError):
        raise EvidenceAssemblyError(stage, "unsafe_path") from None


def _evidence_json(root, reference, stage):
    data = _evidence_bytes(root, reference, stage)
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_members, parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceAssemblyError(stage, "invalid_evidence") from None


def _byte_digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _seal_evidence(root, role, value, *, literal=False):
    from .cli import _write_json
    data = value if literal else (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = _byte_digest(data) if literal else _document_digest(value)
    reference = "review/evidence/" + role + "-" + digest.replace(":", "-") + (".bin" if literal else ".json")
    target = root / reference
    # Check every parent before mkdir/write, including dangling symlinks.
    cursor = root
    for part in Path(reference).parts:
        cursor /= part
        if cursor.is_symlink():
            raise EvidenceAssemblyError("retained_validation", "unsafe_path")
    if target.exists():
        if _evidence_bytes(root, reference, "retained_validation") != data:
            raise EvidenceAssemblyError("retained_validation", "append_conflict")
    else:
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if literal:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            except Exception:
                target.unlink(missing_ok=True)
                raise
        else:
            _write_json(target, value)
        _fsync_directory(target.parent)
    if _evidence_bytes(root, reference, "retained_validation") != data:
        raise EvidenceAssemblyError("retained_validation", "digest_mismatch")
    return reference


def _check_evidence_bound(directory, stage="retained_validation"):
    try:
        return _bounded_diagnostic(directory)
    except BoundedDiagnosticLimitError:
        raise EvidenceAssemblyError(stage, "retention_limit") from None
    except (OSError, ValueError):
        raise EvidenceAssemblyError(stage, "unsafe_path") from None


def _seal_record(root, role, value):
    directory = root / "review/evidence"
    if directory.exists():
        _check_evidence_bound(directory)
        for path in sorted(directory.glob(role + "-sha256-*.json")):
            reference = path.relative_to(root).as_posix()
            try:
                candidate = _read_seal(root, reference, role)
            except EvidenceAssemblyError:
                continue  # Uncommitted partial files never confer coverage.
            if {k: v for k, v in candidate.items() if k != "assembled_at"} == {k: v for k, v in value.items() if k != "assembled_at"}:
                return reference
    return _seal_evidence(root, role, value)


def _read_seal(root, reference, role, stage="retained_validation"):
    value = _evidence_json(root, reference, stage)
    expected = "review/evidence/" + role + "-" + _document_digest(value).replace(":", "-") + ".json"
    if reference != expected:
        raise EvidenceAssemblyError(stage, "digest_mismatch")
    return value


def _resolve_snapshot(root, value, *, head=None, shared=False):
    """Resolve an explicit seal without changing any historical document bytes."""
    if shared:
        if type(value) is not dict or set(value) != {"snapshot_ref"}:
            raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
        value = _read_seal(root, value["snapshot_ref"], "source")
    if type(value) is not dict or set(value) != {"head", "files"}:
        raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    if type(value["head"]) is not str or _HEAD_RE.fullmatch(value["head"]) is None or type(value["files"]) is not dict:
        raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    from .verification_repository import _relative_path
    for path, identity in value["files"].items():
        try:
            _relative_path(path, "reviewed path")
        except (TypeError, ValueError):
            raise EvidenceAssemblyError("retained_validation", "invalid_evidence") from None
        if type(identity) is not dict or set(identity) != {"mode", "oid"} or type(identity["mode"]) is not str or identity["mode"] not in {"100644", "100755", "120000"} or type(identity["oid"]) is not str or re.fullmatch(r"[0-9a-f]{" + str(len(value["head"])) + r"}", identity["oid"]) is None:
            raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    if head is not None and value["head"] != head:
        raise EvidenceAssemblyError("retained_validation", "source_scope_mismatch")
    return value


def _read_source_record(root, reference, role):
    value = _read_seal(root, reference, role)
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] not in {1, 2}:
        raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    if type(value.get("request")) is not dict or type(value["request"].get("source_head")) is not str or _HEAD_RE.fullmatch(value["request"]["source_head"]) is None:
        raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    field = "source_snapshot" if role == "lane" else "target_source"
    return dict(value, **{field: _resolve_snapshot(root, value.get(field), head=value["request"]["source_head"], shared=value["schema_version"] == 2)})


def _read_transition(root, reference):
    value = _evidence_json(root, reference, "aggregate_validation")
    if type(value) is not dict or type(value.get("schema_version")) is not int or value["schema_version"] not in {1, 2}:
        raise EvidenceAssemblyError("aggregate_validation", "invalid_evidence")
    return dict(value, **{field: _resolve_snapshot(root, value.get(field), shared=value["schema_version"] == 2) for field in ("from_source", "to_source")})


def _source_snapshot(repository, head, *, live=False):
    """Compare source bytes/modes, including dirty and untracked source paths."""
    if type(head) is not str or _HEAD_RE.fullmatch(head) is None:
        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
    from .verification_repository import _relative_path
    tree = _git(repository, "ls-tree", "-rz", head)
    files = {}
    for entry in tree.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, kind, oid = meta.split()
        _relative_path(path, "reviewed path")
        if kind != "blob":
            raise EvidenceAssemblyError("lane_validation", "unsafe_path")
        files[path] = {"mode": mode, "oid": oid}
    if live:
        names = _git(repository, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
        for name in names:
            if not name or name.startswith((".workflow-kernel/", ".claude/ux-review/", "todos/")):
                continue
            _relative_path(name, "reviewed path")
            path = repository / name
            if not path.exists() and not path.is_symlink():
                files.pop(name, None)
                continue
            data = _regular_file(_source_path(path, repository))
            header = b"blob " + str(len(data)).encode() + b"\0"
            oid = (hashlib.sha1 if len(head) == 40 else hashlib.sha256)(header + data).hexdigest()
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
            files[name] = {"mode": mode, "oid": oid}
    return {"head": head, "files": files}


def _changed_paths(before, after):
    return sorted(path for path in set(before["files"]) | set(after["files"]) if before["files"].get(path) != after["files"].get(path))


def _git_patch(repository, before, after, paths=()):
    result = subprocess.run(("git", "-C", str(repository), "diff", "--binary", before, after, "--", *paths), capture_output=True, timeout=10)
    if result.returncode:
        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
    return result.stdout


def _working_patch(repository, head):
    result = subprocess.run(("git", "-C", str(repository), "diff", "--binary", head), capture_output=True, timeout=10)
    if result.returncode:
        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
    return result.stdout


def _lane_bindings(root, value, previous=None):
    source = value["source"]
    references = {source["request_ref"], *value["literal"].values(),
                  *value["requested"]["evidence_refs"], *value["provenance"]["source_refs"],
                  *value["recheck"]["repair_refs"]}
    references.update(f["evidence_ref"] for f in value["result"]["findings"])
    if source["worktree_ref"]:
        references.add(source["worktree_ref"])
    if value["recheck"]["selection_ref"]:
        references.add(value["recheck"]["selection_ref"])
    references.update(_transition_references(root, value["recheck"].get("pending_transition_refs", [])))
    bindings, missing = {}, []
    for reference in sorted(references):
        try:
            data = _evidence_bytes(root, reference, "lane_input")
        except EvidenceAssemblyError as exc:
            if exc.reason != "missing_evidence":
                raise
            if previous is not None and reference in previous["bindings"]:
                _bound_bytes(root, previous, reference)
                bindings[reference] = previous["bindings"][reference]
            else:
                missing.append(reference)
            continue
        retained = _seal_evidence(root, "literal", data, literal=True)
        bindings[reference] = {"retained_ref": retained, "digest": _byte_digest(data)}
    return bindings, missing


def _bound_bytes(root, record, reference):
    binding = record["bindings"].get(reference)
    if type(binding) is not dict or set(binding) != {"retained_ref", "digest"}:
        raise EvidenceAssemblyError("retained_validation", "missing_evidence")
    data = _evidence_bytes(root, binding["retained_ref"], "retained_validation")
    if _byte_digest(data) != binding["digest"]:
        raise EvidenceAssemblyError("retained_validation", "digest_mismatch")
    return data


def _record(root, reference, receipts):
    rows = [row for row in receipts if row.get("stage") == "review_lane_evidence" and row.get("authoritative_receipt") == reference]
    if len(rows) != 1:
        raise EvidenceAssemblyError("retained_validation", "missing_evidence")
    record = _read_source_record(root, reference, "lane")
    if type(record) is not dict or set(record) != {"schema_version", "input", "input_digest", "request", "source_snapshot", "source_content", "bindings", "eligible", "missing", "assembled_at"}:
        raise EvidenceAssemblyError("retained_validation", "invalid_evidence")
    request = ReviewRequest.from_mapping(record["request"])
    value = validate_evidence_input(record["input"], request)
    if _document_digest(value) != record["input_digest"] or value["run_id"] != rows[0].get("run_id") or value["lane"] != rows[0].get("lane") or value["attempt"] != rows[0].get("attempt"):
        raise EvidenceAssemblyError("retained_validation", "digest_mismatch")
    for original in record["bindings"]:
        _bound_bytes(root, record, original)
    for binding in record["source_content"].values():
        if _byte_digest(_evidence_bytes(root, binding["retained_ref"], "retained_validation")) != binding["digest"]:
            raise EvidenceAssemblyError("retained_validation", "digest_mismatch")
    if ReviewRequest.from_mapping(_evidence_json_from_bytes(_bound_bytes(root, record, value["source"]["request_ref"]))).to_dict() != record["request"]:
        raise EvidenceAssemblyError("retained_validation", "source_scope_mismatch")
    if record["eligible"] is not True or value["result"]["status"] == "incomplete" or rows[0].get("status") != "complete":
        raise EvidenceAssemblyError("retained_validation", "incomplete_inspection")
    return record


def _evidence_json_from_bytes(data):
    try:
        return json.loads(data.decode(), object_pairs_hook=_unique_members, parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise EvidenceAssemblyError("lane_validation", "invalid_evidence") from None


def _validate_selection(root, reference, lanes, *, before=None, after=None, repository=None, worktree=None):
    document = _read_transition(root, reference)
    # The caller owns rule (a)/(b) semantics. Require its retained receipt and
    # explicit receiver-confirmed application, plus actual transition bytes.
    if set(document) - {"pending_scope_paths"} != {"schema_version", "selected_full_set", "applied", "iteration", "finding_owner_lanes", "file_trigger_lanes", "from_source", "to_source", "changed_paths", "patch_ref", "worktree_ref"} or document["selected_full_set"] != list(lanes) or document["applied"] is not True:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    if before is not None and (document["from_source"] != before or document["to_source"] != after):
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    if document["changed_paths"] != _changed_paths(document["from_source"], document["to_source"]):
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    if repository is not None:
        old_head, new_head = document["from_source"]["head"], document["to_source"]["head"]
        if old_head != new_head:
            _git(repository, "merge-base", "--is-ancestor", old_head, new_head)
        if _evidence_bytes(root, document["patch_ref"], "aggregate_validation") != _git_patch(repository, old_head, new_head):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        committed = _source_snapshot(repository, new_head)
        if after != committed:
            expected = worktree(after) if worktree is not None else _working_patch(repository, new_head)
            if document["worktree_ref"] is None or _evidence_bytes(root, document["worktree_ref"], "aggregate_validation") != expected:
                raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    iteration = document["iteration"]
    translate_review_receipts([dict(iteration, sequence=0)])
    pending = set(iteration.get("lanes_pending", []))
    scopes = document.get("pending_scope_paths", {})
    if type(scopes) is not dict or set(scopes) != pending:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    from .dm_review_adapter import _evidence_list
    for paths in scopes.values():
        _evidence_list(paths, references=True)
        if not paths or not set(paths) <= set(document["changed_paths"]):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    if iteration.get("stage") != "review_iteration" or set(iteration["lanes_rerun"]) | set(iteration["lanes_skipped"]) | pending != set(lanes):
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    owners, triggers = document["finding_owner_lanes"], document["file_trigger_lanes"]
    if type(owners) is not list or type(triggers) is not list or not set(owners + triggers) <= set(iteration["lanes_rerun"]) | pending:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    return iteration


def _transition_references(root, references):
    """Retain the same source/selection/patch closure for carry and pending."""
    result = set()
    for reference in references:
        proof = _evidence_json(root, reference, "retained_validation")
        _read_transition(root, reference)
        documents = [(reference, proof)]
        if "selection_ref" in proof:
            selection_ref = proof["selection_ref"]
            documents.append((selection_ref, _evidence_json(root, selection_ref, "retained_validation")))
            _read_transition(root, selection_ref)
        for ref, document in documents:
            result.add(ref)
            result.update(document[field] for field in ("patch_ref", "worktree_ref") if document.get(field) is not None)
            if document["schema_version"] == 2:
                result.update(document[field]["snapshot_ref"] for field in ("from_source", "to_source"))
    return result


def _transition_chain(root, references, original, target, lane, lanes, repository, worktree, *, pending=False):
    current = original
    affected = set()
    for reference in references:
        proof = _read_transition(root, reference)
        if set(proof) != {"schema_version", "from_source", "to_source", "changed_paths", "patch_ref", "worktree_ref", "selection_ref"} or proof["from_source"] != current:
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        after = proof["to_source"]
        if type(after) is not dict or set(after) != {"head", "files"} or proof["changed_paths"] != _changed_paths(current, after):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        iteration = _validate_selection(root, proof["selection_ref"], lanes, before=current, after=after, repository=repository, worktree=worktree)
        if lane not in iteration.get("lanes_pending" if pending else "lanes_skipped", []):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        if pending:
            affected.update(_read_transition(root, proof["selection_ref"])["pending_scope_paths"][lane])
        _evidence_bytes(root, proof["patch_ref"], "aggregate_validation")
        if repository is not None:
            before_head, after_head = current["head"], after["head"]
            if before_head != after_head:
                _git(repository, "merge-base", "--is-ancestor", before_head, after_head)
            if _evidence_bytes(root, proof["patch_ref"], "aggregate_validation") != _git_patch(repository, before_head, after_head):
                raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
            committed = _source_snapshot(repository, after_head)
            if after != committed:
                if proof["worktree_ref"] is None or _evidence_bytes(root, proof["worktree_ref"], "aggregate_validation") != worktree(after):
                    raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        current = after
    if current != target:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    return affected


def _validate_recheck(root, value, predecessor, target, lanes, repository, worktree):
    recheck = value["recheck"]
    pending_refs = recheck.get("pending_transition_refs", [])
    before = predecessor["source_snapshot"]
    if pending_refs:
        selection_source = _read_transition(root, recheck["selection_ref"])["from_source"]
        affected = _transition_chain(root, pending_refs, before, selection_source, value["lane"], lanes, repository, worktree, pending=True)
        before = selection_source
        # Historical baseline scope remains sealed; fresh scope covers the
        # explicitly mapped affected union at the actual cumulative boundary.
        if (
            value["source"]["base"] != predecessor["source_snapshot"]["head"]
            or not affected <= set(predecessor["input"]["inspected"]["paths"])
            or not affected <= set(value["requested"]["paths"])
            or not affected <= set(value["inspected"]["paths"])
        ):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    selection = _validate_selection(root, recheck["selection_ref"], lanes, before=before, after=target, repository=repository, worktree=worktree)
    if value["lane"] not in selection["lanes_rerun"] or not recheck["repair_refs"]:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")


def _lane_companion(companion, dispatch, value):
    """Consume the router's anonymous companion; exact identities stay private."""
    if type(companion) is dict and set(companion) == _LANE_FIELDS:
        if companion["lane"] != value["lane"] or companion["reviewer"] != value["reviewer"]:
            raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
        return companion  # Historical structured companion, now source-bound.
    public_fields = {
        "role", "capabilities", "requestedEffort", "normalizedEffort",
        "effectiveEffort", "transmittedEffort", "effortStatus", "participantId",
        "disposition", "fallback", "evidenceSource", "transportStub",
        "familyIndependence", "output",
    }
    if type(companion) is not dict or set(companion) != public_fields or type(dispatch) is not dict:
        raise EvidenceAssemblyError("lane_validation", "invalid_evidence")
    served, requested = dispatch.get("served"), dispatch.get("requested")
    if type(served) is not dict or type(requested) is not dict:
        raise EvidenceAssemblyError("lane_validation", "invalid_evidence")
    if companion["participantId"] != value["reviewer"] or companion["participantId"] != dispatch.get("participantId") or companion["role"] != requested.get("role") or companion["disposition"] != "completed" or companion["transportStub"] != dispatch.get("transportStub"):
        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
    candidate = requested.get("candidate")
    row = {
        "reviewer": value["reviewer"], "lane": value["lane"],
        "requested_provider": candidate.get("provider", "unknown") if type(candidate) is dict else "unknown",
        "attempted_provider": served.get("provider"), "implemented_by": served.get("transport"),
        "provider": served.get("provider"), "model": served.get("model"),
        "implementer_family": "unknown", "reviewer_family": served.get("family"),
        "resolution_reason": "implementation-origin-not-reported",
        "evidence_refs": [value["literal"]["output_ref"]],
        "raw_output_ref": "review/pending-output.json", "raw_output_digest": "sha256:" + "0" * 64,
        "finding_count": len(value["result"]["findings"]),
    }
    for field in _LANE_FIELDS - {"evidence_refs", "finding_count"}:
        required_text(row[field], field)
    return row


def _aggregate_documents(root, request, value, receipts, target, repository):
    def worktree(snapshot):
        # Only the final target is compared with the live checkout. An earlier
        # dirty snapshot must match the patch sealed by a lane that inspected it.
        if snapshot == target:
            return _working_patch(repository, snapshot["head"])
        for selected in value["selection"]:
            for ref in (*selected["history_refs"], selected["record_ref"]):
                item = _record(root, ref, receipts)
                sealed = item["input"]["source"]["worktree_ref"]
                if item["source_snapshot"] == snapshot and sealed is not None:
                    return _bound_bytes(root, item, sealed)
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")

    lanes, outputs, all_findings = [], [], []
    seen = set()
    for selected in value["selection"]:
        reference = selected["record_ref"]
        record = _record(root, reference, receipts)
        extraction = record["input"]
        if extraction["lane"] != selected["lane"] or extraction["source"]["repository"] != request.source_repository:
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        history = [_record(root, ref, receipts) for ref in selected["history_refs"]]
        predecessor = extraction["recheck"]["prior_record_ref"]
        if predecessor is not None and (not selected["history_refs"] or selected["history_refs"][-1] != predecessor):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        if predecessor is None and history:
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        chain = history + [record]
        for index, item in enumerate(history):
            expected = selected["history_refs"][index - 1] if index else None
            if item["input"]["lane"] != selected["lane"] or item["input"]["recheck"]["prior_record_ref"] != expected:
                raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        for item in chain:
            recheck = item["input"]["recheck"]
            refs = _transition_references(root, recheck.get("pending_transition_refs", []))
            if recheck["selection_ref"]:
                refs.add(recheck["selection_ref"])
            for ref in refs:
                if _evidence_bytes(root, ref, "aggregate_validation") != _bound_bytes(root, item, ref):
                    raise EvidenceAssemblyError("aggregate_validation", "digest_mismatch")
        for index, item in enumerate(chain):
            if index:
                _validate_recheck(root, item["input"], chain[index - 1], item["source_snapshot"], request.required_lanes, repository, worktree)
        _transition_chain(root, selected["transition_refs"], record["source_snapshot"], target, selected["lane"], request.required_lanes, repository, worktree)
        companion = _lane_companion(
            _evidence_json_from_bytes(_bound_bytes(root, record, extraction["literal"]["companion_ref"])),
            _evidence_json_from_bytes(_bound_bytes(root, record, extraction["literal"]["dispatch_receipt_ref"])), extraction,
        )
        findings, refs = [], set()
        for item in chain:
            refs.update(binding["retained_ref"] for binding in item["bindings"].values())
            if item is not record:
                continue
            for finding in item["input"]["result"]["findings"]:
                finding = dict(finding, evidence_ref=item["bindings"][finding["evidence_ref"]]["retained_ref"])
                if finding["source_finding_id"] in seen:
                    raise EvidenceAssemblyError("aggregate_validation", "invalid_evidence")
                seen.add(finding["source_finding_id"])
                findings.append(finding)
        output = {"reviewer": extraction["reviewer"], "lane": selected["lane"], "findings": findings}
        digest = _document_digest(output)
        lanes.append(dict(companion, evidence_refs=sorted(refs), finding_count=len(findings), raw_output_digest=digest,
                          raw_output_ref="contribution-inputs/raw-lane-output-sha256-" + digest.removeprefix("sha256:") + ".json",
                          evidence_record_ref=reference, evidence_history=selected["history_refs"], transition_refs=selected["transition_refs"]))
        outputs.append(output)
        all_findings.extend(findings)
    documents = {
        "review/review-lane-receipts.json": {"schema_version": 2, "artifact_role": "review_lane_receipts", "run_id": request.run_id, "lanes": lanes},
        "review/raw-lane-outputs.json": {"schema_version": 1, "artifact_role": "review_lane_raw_outputs", "run_id": request.run_id, "outputs": outputs},
        "review/raw-finding-inventory.json": {"schema_version": 1, "artifact_role": "raw_finding_inventory", "run_id": request.run_id, "findings": all_findings},
        "review/synthesis-decisions.json": {"schema_version": 1, "artifact_role": "synthesis_decisions", "run_id": request.run_id, "source_finding_count": len(all_findings), "occurred_at": value["occurred_at"], "decisions": value["decisions"]},
    }
    _validate_lane_source_coverage(request, documents["review/review-lane-receipts.json"], documents["review/raw-lane-outputs.json"])
    _validate_finding_result_sources(request, documents["review/review-lane-receipts.json"], documents["review/raw-lane-outputs.json"], documents["review/raw-finding-inventory.json"], documents["review/synthesis-decisions.json"])
    prior_sources = {f["source_finding_id"] for selected in value["selection"] for ref in selected["history_refs"] for f in _record(root, ref, receipts)["input"]["result"]["findings"]}
    resolutions = {row["source_finding_id"]: row for row in value["resolutions"]}
    if len(resolutions) != len(value["resolutions"]) or set(resolutions) != prior_sources:
        raise EvidenceAssemblyError("aggregate_validation", "incomplete_inspection")
    for resolution in resolutions.values():
        verification = _record(root, resolution["verification_record_ref"], receipts)
        if verification["input"]["recheck"]["prior_record_ref"] is None or resolution["repair_ref"] not in verification["input"]["recheck"]["repair_refs"]:
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        owner = next((selected for selected in value["selection"] if any(
            finding["source_finding_id"] == resolution["source_finding_id"]
            for ref in selected["history_refs"]
            for finding in _record(root, ref, receipts)["input"]["result"]["findings"]
        )), None)
        if owner is None or verification["input"]["lane"] != owner["lane"] or resolution["verification_record_ref"] not in [*owner["history_refs"], owner["record_ref"]]:
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        if _evidence_bytes(root, resolution["repair_ref"], "aggregate_validation") != _bound_bytes(root, verification, resolution["repair_ref"]):
            raise EvidenceAssemblyError("aggregate_validation", "digest_mismatch")
    for reference in value["required_case_refs"]:
        _evidence_bytes(root, reference, "aggregate_validation")
    return documents


def _validate_committed_coverage(request, receipts, lane_document, outputs, findings, decisions, root, repository):
    coverage = [row for row in receipts if row.get("stage") == "coverage_matrix"][-1]
    snapshot = _read_source_record(root, coverage["authoritative_receipt"], "coverage")
    if type(snapshot) is not dict or set(snapshot) != {"schema_version", "input", "request", "target_source", "documents", "bindings", "assembled_at"} or snapshot["request"] != request.to_dict():
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    value = validate_evidence_input(snapshot["input"], request)
    for reference in snapshot["bindings"]:
        if _evidence_bytes(root, reference, "retained_validation") != _bound_bytes(root, snapshot, reference):
            raise EvidenceAssemblyError("retained_validation", "digest_mismatch")
    request_row = [row for row in receipts if row.get("stage") == "review_request"][-1]
    if _read_seal(root, request_row["authoritative_receipt"], "request") != snapshot["request"]:
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    if repository is not None and snapshot["target_source"] != _source_snapshot(repository, request.source_head, live=True):
        raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
    generated = _aggregate_documents(root, request, value, receipts, snapshot["target_source"], repository)
    expected = dict(zip(("review/review-lane-receipts.json", "review/raw-lane-outputs.json", "review/raw-finding-inventory.json", "review/synthesis-decisions.json"), (lane_document, outputs, findings, decisions)))
    if generated != snapshot["documents"] or generated != expected:
        raise EvidenceAssemblyError("aggregate_validation", "digest_mismatch")


def _committed_references(receipts, root):
    references = set()

    def sources(document, fields):
        for field in fields:
            value = document[field]
            _resolve_snapshot(root, value, shared=document["schema_version"] == 2)
            if document["schema_version"] == 2:
                references.add(value["snapshot_ref"])

    def include_transition(reference):
        document = _evidence_json(root, reference, "retained_validation")
        _read_transition(root, reference)
        sources(document, ("from_source", "to_source"))
        references.update(document[field] for field in ("patch_ref", "worktree_ref") if document[field] is not None)

    for row in receipts:
        if type(row) is not dict:
            continue
        if row.get("stage") == "review_lane_evidence":
            reference = row["authoritative_receipt"]
            record = _read_seal(root, reference, "lane")
            _read_source_record(root, reference, "lane")
            sources(record, ("source_snapshot",))
            references.add(reference)
            references.update(binding["retained_ref"] for binding in record["bindings"].values())
            references.update(binding["retained_ref"] for binding in record["source_content"].values())
            references.update(record["input"]["recheck"]["repair_refs"])
            references.update(_transition_references(root, record["input"]["recheck"].get("pending_transition_refs", [])))
            if record["input"]["recheck"]["selection_ref"]:
                selection_ref = record["input"]["recheck"]["selection_ref"]
                references.add(selection_ref)
                include_transition(selection_ref)
        elif row.get("stage") == "review_request" and row.get("authoritative_receipt", "").startswith("review/evidence/request-"):
            references.add(row["authoritative_receipt"])
        elif row.get("stage") == "coverage_matrix" and row.get("authoritative_receipt", "").startswith("review/evidence/coverage-"):
            reference = row["authoritative_receipt"]
            snapshot = _read_seal(root, reference, "coverage")
            _read_source_record(root, reference, "coverage")
            sources(snapshot, ("target_source",))
            references.add(reference)
            references.update(snapshot["bindings"])
            references.update(binding["retained_ref"] for binding in snapshot["bindings"].values())
            for selected in snapshot["input"]["selection"]:
                references.update(_transition_references(root, selected["transition_refs"]))
            references.update(snapshot["input"]["required_case_refs"])
            references.update(row["repair_ref"] for row in snapshot["input"]["resolutions"])
    return sorted(references)


def _review_receipt_context(request):
    context = {
        "workflow_class": request.workflow_class.value,
        "workflow_class_defaulted": request.workflow_class_defaulted,
        "execution_mode": request.execution_mode,
        "decision_profile_defaulted": request.decision_profile_defaulted,
    }
    if request.decision_profile is not None:
        context["decision_profile"] = dict(request.decision_profile)
    return context


def assemble_review_evidence(*, run_root, repository_root, request_path, receipts_path, input_path, test_harness=False):
    """One locked read/validate/seal/append transaction; append is the commit."""
    import fcntl
    from datetime import datetime, timezone
    from .cli import _open_receipt_stream_lock, _append_receipts_locked, _write_json
    run = ExactOwnedRun.open(Path(run_root))
    if run.workflow not in _REVIEW_WORKFLOWS:
        raise EvidenceAssemblyError("lane_input", "unsafe_path")
    root, repository = run.root, Path(repository_root).resolve(strict=True)
    def owned(path):
        try:
            return _source_path(path, root)
        except FileNotFoundError:
            raise EvidenceAssemblyError("lane_input", "missing_evidence", _relative_role(path, root)) from None
        except (OSError, ValueError):
            raise EvidenceAssemblyError("lane_input", "unsafe_path") from None
    request_file, input_file, receipt_file = owned(request_path), owned(input_path), owned(receipts_path)
    # Retained retries use the committed scope beneath the registered
    # diagnostic child; references retain their original scope-relative names.
    if receipt_file.parent.name == "review" and request_file.parent == receipt_file.parent:
        root = receipt_file.parent.parent
        if root != run.root:
            registered = next((item for item in run._metadata["resources"] if item["kind"] == "diagnostic"), None)
            if registered is None or root.parent != run.root / registered["relative_path"] / "review" or _REVIEW_SCOPE_RE.fullmatch(root.name) is None:
                raise EvidenceAssemblyError("retained_validation", "unsafe_path")
    descriptor = _open_receipt_stream_lock(receipt_file)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        raw_request = _evidence_json(root, request_file.relative_to(root).as_posix(), "lane_input")
        request = ReviewRequest.from_mapping(raw_request)
        raw_value = _evidence_json(root, input_file.relative_to(root).as_posix(), "lane_input")
        # Retain safe structured extraction; literal provider files keep bytes.
        from .dm_review_adapter import require_secret_safe_contribution_inputs
        try:
            require_secret_safe_contribution_inputs(raw_value)
        except (TypeError, ValueError, RecursionError):
            raise EvidenceAssemblyError("lane_input", "invalid_evidence") from None
        _seal_evidence(root, "extraction", raw_value)
        if type(raw_value) is dict and raw_value.get("operation") == "lane" and type(raw_value.get("source")) is dict:
            source = raw_value["source"]
            if source.get("repository") != request.source_repository or source.get("head") != request.source_head:
                raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
        try:
            value = validate_evidence_input(raw_value, request)
        except (TypeError, ValueError):
            # Preserve safe literal inputs even when extraction validation fails.
            if type(raw_value) is dict and type(raw_value.get("literal")) is dict:
                for reference in raw_value["literal"].values():
                    try:
                        _seal_evidence(root, "literal", _evidence_bytes(root, reference, "lane_input"), literal=True)
                    except EvidenceAssemblyError:
                        pass
            raise EvidenceAssemblyError("lane_validation", "invalid_evidence") from None
        if not request.required_lanes:
            raise EvidenceAssemblyError("lane_input", "invalid_evidence")
        if request.run_id != run.run_id or not request.source_repository or not request.source_head:
            raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
        receipts = _evidence_json(root, receipt_file.relative_to(root).as_posix(), "lane_input")
        translate_review_receipts(receipts)
        identity = (value["operation"], value["run_id"], value["pass_id"], value.get("lane"), value.get("attempt"))
        stage = "review_lane_evidence" if value["operation"] == "lane" else "coverage_matrix"
        previous = None
        for row in receipts:
            if row.get("stage") != stage or not row.get("authoritative_receipt", "").startswith("review/evidence/"):
                continue
            candidate = _read_source_record(root, row["authoritative_receipt"], "lane" if stage == "review_lane_evidence" else "coverage")
            old = candidate["input"]
            if (old["operation"], old["run_id"], old["pass_id"], old.get("lane"), old.get("attempt")) == identity:
                if old != value or candidate["request"] != request.to_dict():
                    raise EvidenceAssemblyError("lane_validation", "append_conflict")
                previous = (row["authoritative_receipt"], candidate)
        now = datetime.now(timezone.utc).isoformat()
        if value["operation"] == "lane":
            bindings, missing = _lane_bindings(root, value, previous[1] if previous is not None else None)
            if previous is not None:
                if bindings != previous[1]["bindings"] or missing != previous[1]["missing"]:
                    raise EvidenceAssemblyError("lane_validation", "append_conflict")
                for original in previous[1]["bindings"]:
                    _bound_bytes(root, previous[1], original)
                return {"status": "complete" if previous[1]["eligible"] else "incomplete", "record_ref": previous[0], "reused": True, "missing": missing}
            live = value["provenance"]["kind"] != "recovery"
            if value["provenance"]["kind"] == "synthetic_test" and not test_harness:
                raise EvidenceAssemblyError("lane_validation", "incomplete_inspection")
            repository_identity, head = source_identity(repository)
            if repository_identity != request.source_repository or live and head != request.source_head:
                raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            snapshot = _source_snapshot(repository, request.source_head, live=live)
            if value["recheck"].get("pending_transition_refs"):
                predecessor = _record(root, value["recheck"]["prior_record_ref"], receipts)
                if predecessor["input"]["lane"] != value["lane"] or predecessor["input"]["source"]["repository"] != request.source_repository:
                    raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
                _validate_recheck(root, value, predecessor, snapshot, request.required_lanes, repository, lambda source: _working_patch(repository, source["head"]))
            if value["provenance"]["kind"] == "live" and value["literal"]["dispatch_receipt_ref"] in bindings:
                dispatch_digest = bindings[value["literal"]["dispatch_receipt_ref"]]["digest"]
                for row in receipts:
                    if row.get("stage") != "review_lane_evidence":
                        continue
                    old_record = _read_source_record(root, row["authoritative_receipt"], "lane")
                    old_ref = old_record["input"]["literal"]["dispatch_receipt_ref"]
                    old_binding = old_record["bindings"].get(old_ref)
                    if old_binding and old_binding["digest"] == dispatch_digest and old_record["source_snapshot"] != snapshot:
                        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            source_content = {}
            if live:
                for changed_path in _changed_paths(_source_snapshot(repository, request.source_head), snapshot):
                    if changed_path not in snapshot["files"]:
                        continue
                    data = _regular_file(_source_path(repository / changed_path, repository))
                    source_content[changed_path] = {"retained_ref": _seal_evidence(root, "literal", data, literal=True), "digest": _byte_digest(data)}
            if live and _changed_paths(_source_snapshot(repository, request.source_head), snapshot):
                worktree = value["source"]["worktree_ref"]
                if worktree is None or worktree not in bindings or _bound_bytes(root, {"bindings": bindings}, worktree) != _working_patch(repository, request.source_head):
                    raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            required = {value["source"]["request_ref"], *value["literal"].values(), *value["requested"]["required_evidence_refs"]}
            patch_ref = value["requested"]["patch_ref"]
            if patch_ref is not None and patch_ref in bindings and _bound_bytes(root, {"bindings": bindings}, patch_ref) != _git_patch(repository, value["source"]["base"], request.source_head, value["requested"]["paths"]):
                raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            if value["requested"]["designation"] == "full":
                changed = _changed_paths(_source_snapshot(repository, value["source"]["base"]), snapshot)
                if not set(changed) <= set(value["requested"]["paths"]):
                    raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            eligible = not (set(missing) & required) and value["result"]["status"] != "incomplete"
            if value["source"]["worktree_ref"] is not None and not live:
                raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
            if value["literal"]["companion_ref"] in bindings:
                companion = _evidence_json_from_bytes(_bound_bytes(root, {"bindings": bindings}, value["literal"]["companion_ref"]))
                if value["literal"]["dispatch_receipt_ref"] in bindings:
                    companion = _lane_companion(companion,
                        _evidence_json_from_bytes(_bound_bytes(root, {"bindings": bindings}, value["literal"]["dispatch_receipt_ref"])), value)
                elif type(companion) is not dict:
                    raise EvidenceAssemblyError("lane_validation", "invalid_evidence")
            if eligible:
                bound_request = _evidence_json_from_bytes(_bound_bytes(root, {"bindings": bindings}, value["source"]["request_ref"]))
                if ReviewRequest.from_mapping(bound_request) != request:
                    raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
                dispatch = _evidence_json_from_bytes(_bound_bytes(root, {"bindings": bindings}, value["literal"]["dispatch_receipt_ref"]))
                if not test_harness and (type(dispatch) is not dict or dispatch.get("schemaVersion") != 1 or not dispatch.get("served") or not dispatch.get("attempts") or dispatch.get("publication") != {"output": "published"} or dispatch.get("transportStub") is not False):
                    raise EvidenceAssemblyError("lane_validation", "incomplete_inspection")
                if not test_harness:
                    if companion["model"] != dispatch["served"].get("model") or companion["provider"] != dispatch["served"].get("provider") or companion["reviewer_family"] != dispatch["served"].get("family"):
                        raise EvidenceAssemblyError("lane_validation", "source_scope_mismatch")
                if not _bound_bytes(root, {"bindings": bindings}, value["literal"]["output_ref"]).strip():
                    eligible = False
            record = {"schema_version": 2, "input": value, "input_digest": _document_digest(value), "request": request.to_dict(), "source_snapshot": {"snapshot_ref": _seal_evidence(root, "source", snapshot)}, "source_content": source_content, "bindings": bindings, "eligible": eligible, "missing": missing, "assembled_at": now}
            reference = _seal_record(root, "lane", record)
            body = {"stage": stage, "status": "complete" if eligible else "incomplete", "authoritative_receipt": reference, "lane": value["lane"], "reviewer": value["reviewer"], "attempt": value["attempt"], "finding_count": len(value["result"]["findings"])}
            body.update(_review_receipt_context(request))
            _check_evidence_bound(root / "review/evidence")
            _append_receipts_locked(receipt_file, "assemble-review-evidence", [body], run.run_id, now)
            return {"status": body["status"], "record_ref": reference, "reused": False, "missing": missing,
                    "diagnostics": [] if eligible else (
                        [EvidenceAssemblyError("lane_input", "missing_evidence", ref).detail() for ref in sorted(set(missing) & required)]
                        or [{"stage": "lane_validation", "reason": "incomplete_inspection", "path": "review/evidence.json"}]), "proof_level": "synthetic" if test_harness else value["provenance"]["kind"]}
        if not test_harness and any(_record(root, row["record_ref"], receipts)["input"]["provenance"]["kind"] == "synthetic_test" for row in value["selection"]):
            raise EvidenceAssemblyError("aggregate_validation", "incomplete_inspection")
        repository_identity, head = source_identity(repository)
        if (repository_identity, head) != (request.source_repository, request.source_head):
            raise EvidenceAssemblyError("aggregate_validation", "source_scope_mismatch")
        target = _source_snapshot(repository, head, live=True)
        documents = _aggregate_documents(root, request, value, receipts, target, repository)
        aggregate_refs = set(value["required_case_refs"]) | {item["repair_ref"] for item in value["resolutions"]}
        for selected in value["selection"]:
            aggregate_refs.update(_transition_references(root, selected["transition_refs"]))
        aggregate_bindings = {}
        for ref in sorted(aggregate_refs):
            data = _evidence_bytes(root, ref, "aggregate_validation")
            aggregate_bindings[ref] = {"retained_ref": _seal_evidence(root, "literal", data, literal=True), "digest": _byte_digest(data)}
        for name, document in documents.items():
            target_file = root / name
            try:
                _source_path(target_file, root)
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                raise EvidenceAssemblyError("aggregate_validation", "unsafe_path") from None
            if _evidence_json(root, name, "aggregate_validation") != document:
                raise EvidenceAssemblyError("aggregate_validation", "append_conflict")
        if previous is not None:
            reference, snapshot = previous
            if snapshot["documents"] != documents or snapshot["target_source"] != target or snapshot["bindings"] != aggregate_bindings:
                raise EvidenceAssemblyError("aggregate_validation", "append_conflict")
        else:
            snapshot = {"schema_version": 2, "input": value, "request": request.to_dict(), "target_source": {"snapshot_ref": _seal_evidence(root, "source", target)}, "documents": documents, "bindings": aggregate_bindings, "assembled_at": now}
            reference = _seal_record(root, "coverage", snapshot)
            bound_ref = _seal_evidence(root, "request", request.to_dict())
            bodies = [
                {"stage": "review_request", "status": "accepted", "authoritative_receipt": bound_ref, "requested_lanes": list(request.required_lanes), "source_repository": repository_identity, "source_head": head},
                {"stage": "coverage_matrix", "status": "complete", "authoritative_receipt": reference, "expected_lanes": list(request.required_lanes), "completed_lanes": list(request.required_lanes), "degraded_lanes": [], "unavailable_lanes": [], "source_repository": repository_identity, "source_head": head, "required_browser_cases": list(request.required_browser_cases)},
            ]
            for body in bodies:
                body.update(_review_receipt_context(request))
            _validate_browser_coverage(request, receipts)
            _check_evidence_bound(root / "review/evidence")
            _append_receipts_locked(receipt_file, "assemble-review-evidence", bodies, run.run_id, now)
        for name, document in documents.items():
            target_file = root / name
            if target_file.exists():
                if _evidence_json(root, name, "retained_validation") != document:
                    raise EvidenceAssemblyError("retained_validation", "append_conflict")
            else:
                _write_json(target_file, document)
        return {"status": "complete", "snapshot_ref": reference, "reused": previous is not None, "companions": list(documents), "proof_level": "synthetic" if test_harness else "candidate"}
    except EvidenceAssemblyError:
        raise
    except (OSError, TypeError, ValueError):
        raise EvidenceAssemblyError("lane_validation", "invalid_evidence") from None
    finally:
        os.close(descriptor)
