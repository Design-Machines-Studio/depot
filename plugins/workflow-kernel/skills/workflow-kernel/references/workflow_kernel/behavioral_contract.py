"""Strict schema-version-1 behavioral verification contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from ._files import _OwnedResourceScope, bind_durable_path
from .limits import bounded_json_int, parse_json_document
from .redaction import (
    MAX_STRING_LENGTH, contains_high_confidence_secret, normalize_durable_string,
)


SCHEMA_VERSION = 1
MAX_CONTRACT_BYTES = 1_048_576
MAX_APPROVAL_BYTES = 65_536
MAX_COLLECTION_ITEMS = 1_024
MAX_ARGV_ITEMS = 256
MAX_OBLIGATION_ITEMS = 4_096

_ROOT_FIELDS = frozenset({
    "schema_version", "contract_id", "revision", "previous_contract_digest",
    "requirements", "prohibited_regressions", "checks", "persona_case_ids",
    "browser_case_ids", "verification_profile_id", "verification_profile_digest",
    "manual_requirements", "revision_justification",
})
_STATEMENT_FIELDS = frozenset({"id", "source_ref", "statement"})
_CHECK_FIELDS = frozenset({
    "id", "argv", "proves_requirement_ids", "proves_regression_ids",
    "baseline_expectation",
})
_MANUAL_FIELDS = frozenset({"requirement_id", "reason_code", "evidence_ref"})
_JUSTIFICATION_FIELDS = frozenset({
    "reason_code", "summary", "added_obligation_ids",
    "retained_obligation_ids", "removed_obligation_ids",
    "human_approval_evidence_ref",
})
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}")
_STABLE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_CONTRACT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_REQUIREMENT_ID = re.compile(r"REQ-[A-Za-z0-9][A-Za-z0-9._-]{0,123}")
_REGRESSION_ID = re.compile(r"REG-[A-Za-z0-9][A-Za-z0-9._-]{0,123}")
_CHECK_ID = re.compile(r"CHK-[A-Za-z0-9][A-Za-z0-9._-]{0,123}")
_BASELINE_EXPECTATIONS = frozenset({"must_fail", "may_pass", "not_runnable"})
_BASELINE_STRENGTH = {"not_runnable": 0, "may_pass": 1, "must_fail": 2}
_APPROVAL_FIELDS = frozenset({
    "schema_version", "actor", "decision", "occurred_at", "run_id",
    "nonce", "previous_contract_digest", "candidate_contract_digest",
})
_SHELL_EXECUTABLES = frozenset({
    "ash", "bash", "csh", "dash", "fish", "ksh", "mksh", "powershell",
    "cmd", "cmd.exe", "powershell.exe", "pwsh", "pwsh.exe", "sh", "tcsh",
    "yash", "zsh",
})
_ENVIRONMENT_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def _uses_shell_command_string(argv):
    """Reject shell command-string modes, including combined short flags."""
    initial_name = Path(argv[0]).name.casefold()
    if initial_name.endswith(".exe"):
        initial_name = initial_name[:-4]
    shell_index = 0
    if initial_name == "env":
        shell_index = 1
        while shell_index < len(argv):
            option = argv[shell_index]
            if option.startswith("-") and not option.startswith("--") and len(option) > 2:
                cluster = option[1:]
                for position, marker in enumerate(cluster):
                    if marker == "S":
                        return True
                    if marker in {"u", "C"}:
                        shell_index += 2 if position == len(cluster) - 1 else 1
                        break
                else:
                    shell_index += 1
                continue
            if (
                option == "-S" or option.startswith("-S")
                or option == "--split-string" or option.startswith("--split-string=")
            ):
                return True
            if _ENVIRONMENT_ASSIGNMENT.fullmatch(option):
                shell_index += 1
                continue
            if option in {"-u", "--unset", "-C", "--chdir"}:
                shell_index += 2
                continue
            if option.startswith(("--unset=", "--chdir=")) or option in {"-", "-i", "--ignore-environment"}:
                shell_index += 1
                continue
            if (
                (option.startswith("-u") and len(option) > 2)
                or (option.startswith("-C") and len(option) > 2)
            ):
                shell_index += 1
                continue
            if option == "--":
                shell_index += 1
            break
    if shell_index >= len(argv):
        return False
    shell_name = Path(argv[shell_index]).name.casefold()
    if shell_name.endswith(".exe") and shell_name[:-4] in _SHELL_EXECUTABLES:
        shell_name = shell_name[:-4]
    if shell_name not in _SHELL_EXECUTABLES:
        return False
    options = argv[shell_index + 1:]
    option_index = 0
    powershell_value_parameters = {
        "configurationfile", "configurationname", "custompipename", "executionpolicy",
        "inputformat", "outputformat", "settingsfile", "version", "windowstyle",
        "workingdirectory",
    }
    powershell_command_aliases = {"c", "cwa", "ec"}
    powershell_value_aliases = {"config", "ep", "o", "of", "settings", "v", "w", "wd"}
    while option_index < len(options):
        option = options[option_index]
        if option == "--":
            break
        folded = option.casefold()
        if shell_name == "cmd":
            if folded.startswith(("/c", "/k")):
                return True
            if option.startswith(("/", "-")):
                option_index += 1
                continue
            break
        if shell_name in {"powershell", "pwsh"}:
            if not option.startswith("-"):
                break
            parameter = folded.lstrip("-")
            if (
                parameter in powershell_command_aliases
                or (len(parameter) >= 2 and "command".startswith(parameter))
                or "encodedcommand".startswith(parameter)
                or parameter == "commandwithargs"
            ):
                return True
            if parameter == "f" or (len(parameter) >= 2 and "file".startswith(parameter)):
                break
            matches = {
                name for name in powershell_value_parameters
                if len(parameter) >= 2 and name.startswith(parameter)
            }
            if parameter in powershell_value_aliases or len(matches) == 1:
                option_index += 2
            else:
                option_index += 1
            continue
        if not option.startswith(("-", "+")):
            break
        if folded == "--command" or folded.startswith("--command="):
            return True
        if shell_name == "fish" and (
            folded == "--init-command" or folded.startswith("--init-command=")
            or (len(option) > 1 and option[0] in "-+" and "C" in option[1:])
        ):
            return True
        if option in {"--rcfile", "--init-file"}:
            option_index += 2
            continue
        if option.startswith(("--rcfile=", "--init-file=")):
            option_index += 1
            continue
        if option.startswith("--"):
            option_index += 1
            continue
        if len(option) > 1 and option[0] in "-+" and "c" in option[1:]:
            return True
        if option in {"-O", "-o"}:
            option_index += 2
        else:
            option_index += 1
    return False


def _passes_secret_value(argv):
    for index, argument in enumerate(argv):
        flag, separator, _value = argument.partition("=")
        if not flag.startswith(("-", "/")):
            continue
        compact_flag = re.sub(r"[^a-z0-9]", "", flag.casefold())
        segments = {
            segment for segment in flag.casefold().replace("_", "-").split("-")
            if segment
        }
        secret_flag = compact_flag.endswith((
            "apikey", "accesskey", "secretkey", "privatekey",
            "clientsecret", "clientauth", "authorization", "password",
            "passwd", "passphrase", "credential", "credentials", "creds", "cookie", "dsn",
            "bearer", "token",
        )) or bool(segments & {
            "key", "secret", "password", "passwd", "authorization",
            "passphrase", "credential", "credentials", "creds", "cookie", "dsn", "bearer",
        }) or (
            "token" in segments and (
                len(segments) == 1
                or bool(segments & {
                    "access", "api", "auth", "bearer", "client", "github",
                    "oauth", "private", "refresh", "session",
                })
            )
        )
        if not secret_flag:
            continue
        if separator or index + 1 < len(argv):
            return True
    return False


def _fail(reason: str) -> None:
    raise ValueError(reason)


def _object(value, fields, name):
    if type(value) is not dict or set(value) != fields:
        _fail(f"{name} fields mismatch")
    return value


def _strict_int(value, name, *, minimum):
    if type(value) is not int or value < minimum:
        _fail(f"invalid {name}")
    return value


def _string(value, name, *, maximum=MAX_STRING_LENGTH, pattern=None, durable=True):
    if (
        type(value) is not str or not value or len(value) > maximum
        or "\x00" in value or any(ord(character) < 0x20 for character in value)
        or contains_high_confidence_secret(value)
        or (pattern is not None and pattern.fullmatch(value) is None)
    ):
        _fail(f"invalid {name}")
    if durable:
        try:
            if normalize_durable_string(value) != value:
                _fail(f"unsafe {name}")
        except ValueError:
            _fail(f"unsafe {name}")
    return value


def _nullable_reference(value, name):
    if value is None:
        return None
    return _string(value, name, maximum=2048)


def _list(value, name, *, maximum=MAX_COLLECTION_ITEMS, nonempty=False):
    if type(value) is not list or len(value) > maximum or (nonempty and not value):
        _fail(f"invalid {name}")
    return value


def _unique_strings(value, name, *, maximum=MAX_COLLECTION_ITEMS,
                    nonempty=False, pattern=None, durable=False):
    result = [
        _string(item, name, maximum=512, pattern=pattern, durable=durable)
        for item in _list(value, name, maximum=maximum, nonempty=nonempty)
    ]
    if len(result) != len(set(result)):
        _fail(f"duplicate {name}")
    return result


def _validate_statement_records(value, name, id_pattern):
    result = []
    identifiers = set()
    for raw in _list(value, name):
        item = _object(raw, _STATEMENT_FIELDS, name)
        identifier = _string(
            item["id"], f"{name} id", pattern=id_pattern, durable=False,
        )
        if identifier in identifiers:
            _fail(f"duplicate {name} id")
        identifiers.add(identifier)
        result.append({
            "id": identifier,
            "source_ref": _string(item["source_ref"], "source_ref", maximum=2048),
            "statement": _string(item["statement"], "statement", maximum=4096),
        })
    return result, identifiers


def _canonical_contract(value):
    result = dict(value)
    result["requirements"] = sorted(value["requirements"], key=lambda item: item["id"])
    result["prohibited_regressions"] = sorted(
        value["prohibited_regressions"], key=lambda item: item["id"],
    )
    checks = []
    for item in sorted(value["checks"], key=lambda item: item["id"]):
        candidate = dict(item)
        candidate["proves_requirement_ids"] = sorted(item["proves_requirement_ids"])
        candidate["proves_regression_ids"] = sorted(item["proves_regression_ids"])
        checks.append(candidate)
    result["checks"] = checks
    result["persona_case_ids"] = sorted(value["persona_case_ids"])
    result["browser_case_ids"] = sorted(value["browser_case_ids"])
    result["manual_requirements"] = sorted(
        value["manual_requirements"], key=lambda item: item["requirement_id"],
    )
    justification = dict(value["revision_justification"])
    for name in (
        "added_obligation_ids", "retained_obligation_ids", "removed_obligation_ids",
    ):
        justification[name] = sorted(justification[name])
    result["revision_justification"] = justification
    return result


def validate_contract(value):
    """Validate and return the deterministic canonical contract projection."""
    value = _object(value, _ROOT_FIELDS, "contract")
    if _strict_int(value["schema_version"], "schema_version", minimum=1) != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    contract_id = _string(
        value["contract_id"], "contract_id", pattern=_CONTRACT_ID, durable=False,
    )
    revision = _strict_int(value["revision"], "revision", minimum=1)
    previous = value["previous_contract_digest"]
    if previous is not None and (type(previous) is not str or _DIGEST.fullmatch(previous) is None):
        _fail("invalid previous_contract_digest")
    profile_id = value["verification_profile_id"]
    profile_digest = value["verification_profile_digest"]
    if (profile_id is None) != (profile_digest is None):
        _fail("verification profile identity is incomplete")
    if profile_id is not None and (
        type(profile_id) is not str or _PROFILE_ID.fullmatch(profile_id) is None
        or type(profile_digest) is not str or _DIGEST.fullmatch(profile_digest) is None
    ):
        _fail("invalid verification profile identity")

    requirements, requirement_ids = _validate_statement_records(
        value["requirements"], "requirement", _REQUIREMENT_ID,
    )
    regressions, regression_ids = _validate_statement_records(
        value["prohibited_regressions"], "prohibited regression", _REGRESSION_ID,
    )
    if requirement_ids & regression_ids:
        _fail("duplicate obligation id")

    checks = []
    check_ids = set()
    proved_requirement_ids = set()
    proved_regression_ids = set()
    for raw in _list(value["checks"], "checks"):
        item = _object(raw, _CHECK_FIELDS, "check")
        identifier = _string(
            item["id"], "check id", pattern=_CHECK_ID, durable=False,
        )
        if identifier in check_ids:
            _fail("duplicate check id")
        check_ids.add(identifier)
        argv = [
            _string(argument, "argv argument", maximum=4096)
            for argument in _list(
                item["argv"], "argv", maximum=MAX_ARGV_ITEMS, nonempty=True,
            )
        ]
        if _uses_shell_command_string(argv):
            _fail("shell command snippets are not executable checks")
        if any(_ENVIRONMENT_ASSIGNMENT.fullmatch(argument) for argument in argv):
            _fail("executable checks must not embed environment values")
        if _passes_secret_value(argv):
            _fail("executable checks must not embed secret values")
        proof_ids = _unique_strings(
            item["proves_requirement_ids"], "proof requirement id",
            pattern=_REQUIREMENT_ID,
        )
        if not set(proof_ids) <= requirement_ids:
            _fail("check proves unknown requirement id")
        regression_proof_ids = _unique_strings(
            item["proves_regression_ids"], "proof regression id",
            pattern=_REGRESSION_ID,
        )
        if not set(regression_proof_ids) <= regression_ids:
            _fail("check proves unknown regression id")
        if not proof_ids and not regression_proof_ids:
            _fail("check proves no obligation")
        proved_requirement_ids.update(proof_ids)
        proved_regression_ids.update(regression_proof_ids)
        baseline = item["baseline_expectation"]
        if type(baseline) is not str or baseline not in _BASELINE_EXPECTATIONS:
            _fail("invalid baseline_expectation")
        checks.append({
            "id": identifier, "argv": argv,
            "proves_requirement_ids": proof_ids,
            "proves_regression_ids": regression_proof_ids,
            "baseline_expectation": baseline,
        })

    persona_ids = _unique_strings(
        value["persona_case_ids"], "persona case id", pattern=_STABLE_ID,
    )
    browser_ids = _unique_strings(
        value["browser_case_ids"], "browser case id", pattern=_STABLE_ID,
    )
    if (persona_ids or browser_ids) and profile_id is None:
        _fail("selected cases require verification profile identity")
    manual = []
    manual_ids = set()
    for raw in _list(value["manual_requirements"], "manual_requirements"):
        item = _object(raw, _MANUAL_FIELDS, "manual requirement")
        requirement_id = _string(
            item["requirement_id"], "manual requirement id", pattern=_REQUIREMENT_ID,
            durable=False,
        )
        if requirement_id not in requirement_ids:
            _fail("manual entry references unknown requirement id")
        if requirement_id in manual_ids:
            _fail("duplicate manual requirement id")
        manual_ids.add(requirement_id)
        manual.append({
            "requirement_id": requirement_id,
            "reason_code": _string(
                item["reason_code"], "manual reason_code", pattern=_STABLE_ID,
                durable=False,
            ),
            "evidence_ref": _nullable_reference(item["evidence_ref"], "manual evidence_ref"),
        })
    if requirement_ids - proved_requirement_ids - manual_ids:
        _fail("requirement lacks executable or manual verification")
    if regression_ids - proved_regression_ids:
        _fail("prohibited regression lacks executable verification")

    raw_justification = _object(
        value["revision_justification"], _JUSTIFICATION_FIELDS,
        "revision_justification",
    )
    justification = {
        "reason_code": _string(
            raw_justification["reason_code"], "revision reason_code", pattern=_STABLE_ID,
            durable=False,
        ),
        "summary": _string(raw_justification["summary"], "revision summary", maximum=4096),
        "added_obligation_ids": _unique_strings(
            raw_justification["added_obligation_ids"], "added obligation id",
            maximum=MAX_OBLIGATION_ITEMS,
        ),
        "retained_obligation_ids": _unique_strings(
            raw_justification["retained_obligation_ids"], "retained obligation id",
            maximum=MAX_OBLIGATION_ITEMS,
        ),
        "removed_obligation_ids": _unique_strings(
            raw_justification["removed_obligation_ids"], "removed obligation id",
            maximum=MAX_OBLIGATION_ITEMS,
        ),
        "human_approval_evidence_ref": _nullable_reference(
            raw_justification["human_approval_evidence_ref"],
            "human approval evidence_ref",
        ),
    }
    delta_sets = [
        set(justification[name]) for name in (
            "added_obligation_ids", "retained_obligation_ids", "removed_obligation_ids",
        )
    ]
    if any(delta_sets[index] & delta_sets[other]
           for index in range(3) for other in range(index + 1, 3)):
        _fail("obligation delta sets overlap")

    canonical = {
        "schema_version": SCHEMA_VERSION, "contract_id": contract_id,
        "revision": revision, "previous_contract_digest": previous,
        "requirements": requirements, "prohibited_regressions": regressions,
        "checks": checks, "persona_case_ids": persona_ids,
        "browser_case_ids": browser_ids,
        "verification_profile_id": profile_id,
        "verification_profile_digest": profile_digest,
        "manual_requirements": manual,
        "revision_justification": justification,
    }
    obligation_count = (
        len(requirements) + len(regressions) + len(persona_ids) + len(browser_ids)
        + sum(len(item["proves_requirement_ids"]) for item in checks)
        + sum(len(item["proves_regression_ids"]) for item in checks)
    )
    if obligation_count > MAX_OBLIGATION_ITEMS:
        _fail("contract obligation limit exceeded")
    return _canonical_contract(canonical)


def canonical_bytes(contract):
    """Return compact sorted-key UTF-8 JSON for one validated contract."""
    canonical = validate_contract(contract)
    return json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def contract_digest(contract):
    return "sha256:" + hashlib.sha256(canonical_bytes(contract)).hexdigest()


def obligations(contract):
    """Return the complete requirement, case, regression, and proof identity set."""
    canonical = validate_contract(contract)
    result = {item["id"] for item in canonical["requirements"]}
    result.update(item["id"] for item in canonical["prohibited_regressions"])
    result.update(f"PERSONA:{item}" for item in canonical["persona_case_ids"])
    result.update(f"BROWSER:{item}" for item in canonical["browser_case_ids"])
    for check in canonical["checks"]:
        result.update(
            f"PROOF:{check['id']}:{requirement_id}"
            for requirement_id in check["proves_requirement_ids"]
        )
        result.update(
            f"PROOF:{check['id']}:{regression_id}"
            for regression_id in check["proves_regression_ids"]
        )
    return frozenset(result)


def verification_profile_digest(profile):
    from .verification import VerificationProfile

    canonical = VerificationProfile.from_dict(profile).to_dict()
    encoded = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def parse_profile_bytes(raw):
    from .verification import VerificationProfile

    if type(raw) is not bytes or len(raw) > MAX_CONTRACT_BYTES:
        _fail("verification profile document exceeds size limit")
    try:
        text = raw.decode("utf-8")
        parse_json_document(text)
        value = json.loads(
            text, parse_int=bounded_json_int,
            parse_constant=lambda _raw: _fail("non-finite JSON constant"),
            object_pairs_hook=_duplicate_rejecting_object,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("invalid verification profile JSON")
    return VerificationProfile.from_dict(value).to_dict()


def load_profile(path):
    binding = bind_durable_path(Path(path))
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        descriptor = owned.own(directory.open_regular(binding.path.name, os.O_RDONLY))
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, MAX_CONTRACT_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_CONTRACT_BYTES:
                _fail("verification profile document exceeds size limit")
        directory.require_identity(descriptor, binding.path.name)
        return parse_profile_bytes(b"".join(chunks))


def validate_profile_binding(contract, profile):
    """Bind selected persona/browser cases to one authoritative profile."""
    from .verification import VerificationProfile

    canonical = validate_contract(contract)
    authoritative = VerificationProfile.from_dict(profile)
    digest = verification_profile_digest(authoritative.to_dict())
    if (canonical["verification_profile_id"] != authoritative.profile_id
            or canonical["verification_profile_digest"] != digest):
        _fail("verification profile identity mismatch")
    required_ids = {
        case.case_id for case in authoritative.cases if case.required
    }
    if (set(canonical["persona_case_ids"]) != required_ids
            or set(canonical["browser_case_ids"]) != required_ids):
        _fail("contract selected cases do not match authoritative profile")
    return canonical


def _potential_weakening(previous, candidate):
    previous_requirements = {item["id"]: item for item in previous["requirements"]}
    candidate_requirements = {item["id"]: item for item in candidate["requirements"]}
    previous_regressions = {item["id"]: item for item in previous["prohibited_regressions"]}
    candidate_regressions = {item["id"]: item for item in candidate["prohibited_regressions"]}
    if any(candidate_requirements.get(identifier) != item
           for identifier, item in previous_requirements.items()
           if identifier in candidate_requirements):
        return True
    if any(candidate_regressions.get(identifier) != item
           for identifier, item in previous_regressions.items()
           if identifier in candidate_regressions):
        return True
    previous_checks = {item["id"]: item for item in previous["checks"]}
    candidate_checks = {item["id"]: item for item in candidate["checks"]}
    for identifier, old in previous_checks.items():
        new = candidate_checks.get(identifier)
        if new is None:
            continue
        if old["argv"] != new["argv"]:
            return True
        if (_BASELINE_STRENGTH[new["baseline_expectation"]]
                < _BASELINE_STRENGTH[old["baseline_expectation"]]):
            return True
    previous_manual = {
        item["requirement_id"]: item for item in previous["manual_requirements"]
    }
    candidate_manual = {
        item["requirement_id"]: item for item in candidate["manual_requirements"]
    }
    if any(candidate_manual.get(identifier) != item
           for identifier, item in previous_manual.items()):
        return True
    if (
        previous["verification_profile_id"] != candidate["verification_profile_id"]
        or previous["verification_profile_digest"]
        != candidate["verification_profile_digest"]
    ):
        return True
    return False


def validate_initial_binding(contract):
    canonical = validate_contract(contract)
    expected = sorted(obligations(canonical))
    justification = canonical["revision_justification"]
    if (
        canonical["revision"] != 1
        or canonical["previous_contract_digest"] is not None
        or justification["reason_code"] != "initial_binding"
        or justification["added_obligation_ids"] != expected
        or justification["retained_obligation_ids"]
        or justification["removed_obligation_ids"]
        or justification["human_approval_evidence_ref"] is not None
    ):
        _fail("invalid initial binding justification")
    return canonical


def validate_approval_evidence(value, *, previous_digest, candidate_digest, run_id):
    """Authenticate one closed approval receipt for an exact contract transition."""
    item = _object(value, _APPROVAL_FIELDS, "approval evidence")
    if _strict_int(item["schema_version"], "approval schema_version", minimum=1) != 1:
        _fail("unsupported approval schema_version")
    actor = _string(item["actor"], "approval actor", pattern=_STABLE_ID, durable=False)
    if item["decision"] != "approved":
        _fail("approval decision is not approved")
    occurred_at = _string(item["occurred_at"], "approval occurred_at", maximum=64)
    try:
        parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError:
        _fail("invalid approval occurred_at")
    if parsed.tzinfo is None or parsed.utcoffset() is None or not occurred_at.endswith("Z"):
        _fail("approval occurred_at must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    occurred_at = parsed.isoformat().replace("+00:00", "Z")
    if _string(item["run_id"], "approval run_id", pattern=_STABLE_ID, durable=False) != run_id:
        _fail("approval run mismatch")
    nonce = _string(item["nonce"], "approval nonce", pattern=_STABLE_ID, durable=False)
    if item["previous_contract_digest"] != previous_digest:
        _fail("approval prior contract digest mismatch")
    if item["candidate_contract_digest"] != candidate_digest:
        _fail("approval candidate contract digest mismatch")
    return {
        "schema_version": 1, "actor": actor, "decision": "approved",
        "occurred_at": occurred_at, "run_id": run_id, "nonce": nonce,
        "previous_contract_digest": previous_digest,
        "candidate_contract_digest": candidate_digest,
    }


def approval_bytes(value, *, previous_digest, candidate_digest, run_id):
    canonical = validate_approval_evidence(
        value, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )
    return json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def approval_digest(value, *, previous_digest, candidate_digest, run_id):
    return "sha256:" + hashlib.sha256(approval_bytes(
        value, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )).hexdigest()


def validate_revision(previous, candidate, previous_digest, *,
                      approval_evidence=None, run_id=None):
    previous = validate_contract(previous)
    candidate = validate_contract(candidate)
    if (
        candidate["contract_id"] != previous["contract_id"]
        or candidate["revision"] != previous["revision"] + 1
        or candidate["previous_contract_digest"] != previous_digest
        or candidate["revision_justification"]["reason_code"] == "initial_binding"
    ):
        _fail("revision does not extend immediately prior binding")
    old = obligations(previous)
    new = obligations(candidate)
    expected = {
        "added_obligation_ids": sorted(new - old),
        "retained_obligation_ids": sorted(new & old),
        "removed_obligation_ids": sorted(old - new),
    }
    justification = candidate["revision_justification"]
    if any(justification[name] != values for name, values in expected.items()):
        _fail("revision obligation deltas do not match contracts")
    weakening = bool(old - new) or _potential_weakening(previous, candidate)
    if weakening:
        if justification["human_approval_evidence_ref"] is None:
            _fail("weakening requires human approval evidence")
        if approval_evidence is None or run_id is None:
            _fail("weakening requires authenticated approval evidence")
        validate_approval_evidence(
            approval_evidence, previous_digest=previous_digest,
            candidate_digest=contract_digest(candidate), run_id=run_id,
        )
    elif (approval_evidence is not None
          or justification["human_approval_evidence_ref"] is not None):
        _fail("approval evidence supplied for non-weakening revision")
    return candidate


def _duplicate_rejecting_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate object key")
        result[key] = value
    return result


def parse_contract_bytes(raw):
    if type(raw) is not bytes or len(raw) > MAX_CONTRACT_BYTES:
        _fail("contract document exceeds size limit")
    try:
        text = raw.decode("utf-8")
        parse_json_document(text)
        value = json.loads(
            text, parse_int=bounded_json_int,
            parse_constant=lambda _raw: _fail("non-finite JSON constant"),
            object_pairs_hook=_duplicate_rejecting_object,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("invalid contract JSON")
    return validate_contract(value)


def parse_approval_bytes(raw, *, previous_digest, candidate_digest, run_id):
    if type(raw) is not bytes or len(raw) > MAX_APPROVAL_BYTES:
        _fail("approval document exceeds size limit")
    try:
        text = raw.decode("utf-8")
        parse_json_document(text)
        value = json.loads(
            text, parse_int=bounded_json_int,
            parse_constant=lambda _raw: _fail("non-finite JSON constant"),
            object_pairs_hook=_duplicate_rejecting_object,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail("invalid approval JSON")
    return validate_approval_evidence(
        value, previous_digest=previous_digest,
        candidate_digest=candidate_digest, run_id=run_id,
    )


def load_contract(path):
    """Read one symlink-safe bounded contract document."""
    binding = bind_durable_path(Path(path))
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        descriptor = owned.own(directory.open_regular(binding.path.name, os.O_RDONLY))
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, MAX_CONTRACT_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_CONTRACT_BYTES:
                _fail("contract document exceeds size limit")
        directory.require_identity(descriptor, binding.path.name)
        return parse_contract_bytes(b"".join(chunks))


def load_approval(path, *, previous_digest, candidate_digest, run_id):
    """Read one symlink-safe bounded approval receipt."""
    binding = bind_durable_path(Path(path))
    with _OwnedResourceScope() as owned:
        directory = owned.pin(binding)
        descriptor = owned.own(directory.open_regular(binding.path.name, os.O_RDONLY))
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(8192, MAX_APPROVAL_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_APPROVAL_BYTES:
                _fail("approval document exceeds size limit")
        directory.require_identity(descriptor, binding.path.name)
        return parse_approval_bytes(
            b"".join(chunks), previous_digest=previous_digest,
            candidate_digest=candidate_digest, run_id=run_id,
        )
