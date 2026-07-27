#!/usr/bin/env bash
# Fail-closed OpenRouter disclosure and diff boundary shared by delegation callers.
# Exit 0 = safe, 3 = actual disclosure decline, 2 = malformed/unverifiable input.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

POLICY=""
CHANGED_FILES=""
CONTENT_FILES=()
CONTENT_COUNT=0
DIFF_FILE=""
OUTPUT_PATHS=""
OUTPUT_DIFF=""
MODE="execution"

while [ $# -gt 0 ]; do
  case "$1" in
    --policy)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      POLICY="$2"; shift 2;;
    --changed-files)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      CHANGED_FILES="$2"; shift 2;;
    --content-file)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      CONTENT_FILES+=("$2"); CONTENT_COUNT=$((CONTENT_COUNT + 1)); shift 2;;
    --diff-file)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      DIFF_FILE="$2"; shift 2;;
    --output-paths)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      OUTPUT_PATHS="$2"; shift 2;;
    --output-diff)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      OUTPUT_DIFF="$2"; shift 2;;
    --mode)
      [ "$#" -ge 2 ] || { echo "delegation-boundary: input-invalid:missing-argument" >&2; exit 2; }
      MODE="$2"; shift 2;;
    *) echo "delegation-boundary: input-invalid:unknown-argument" >&2; exit 2;;
  esac
done

[ -f "$POLICY" ] || {
  echo "delegation-boundary: input-invalid:policy-required" >&2
  exit 2
}
case "$MODE" in
  execution|mechanical-review|artifact-review|artifact-delegation) ;;
  *) echo "delegation-boundary: input-invalid:mode" >&2; exit 2;;
esac
if [ "$CONTENT_COUNT" -gt 0 ]; then
  for content_file in "${CONTENT_FILES[@]}"; do
    [ -f "$content_file" ] || {
      echo "delegation-boundary: input-invalid:content-file" >&2
      exit 2
    }
  done
fi
[ -z "$DIFF_FILE" ] || [ -f "$DIFF_FILE" ] || {
  echo "delegation-boundary: input-invalid:diff-file" >&2
  exit 2
}

if [ "$MODE" = "artifact-delegation" ]; then
  [ "$CONTENT_COUNT" -gt 0 ] &&
    [ -z "$CHANGED_FILES" ] &&
    [ -z "$DIFF_FILE" ] &&
    [ -z "$OUTPUT_PATHS" ] &&
    [ -z "$OUTPUT_DIFF" ] || {
      echo "delegation-boundary: input-invalid:artifact-delegation-authority" >&2
      exit 2
    }
else
  [ -f "$CHANGED_FILES" ] || {
    echo "delegation-boundary: input-invalid:changed-files-required" >&2
    exit 2
  }
fi

python3 - "$POLICY" "$CHANGED_FILES" "$DIFF_FILE" "$OUTPUT_PATHS" \
  "$OUTPUT_DIFF" "$MODE" ${CONTENT_FILES[@]+"${CONTENT_FILES[@]}"} <<'PY'
import collections
import json
import math
import os
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

policy_path, changed_path, diff_path, output_path, output_diff_path, mode, *content_paths = sys.argv[1:]


def fail(code, reason):
    category = "disclosure-declined" if code == 3 else "input-invalid"
    print(f"delegation-boundary: {category}:{reason}", file=sys.stderr)
    raise SystemExit(code)


def read_text(path, reason):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        fail(2, reason)
    if b"\0" in raw:
        fail(2, f"{reason}-nul")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(2, f"{reason}-not-utf8")


def normalize(raw):
    if not isinstance(raw, str) or not raw or any(ord(char) < 32 for char in raw):
        fail(2, "path-not-normalized")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        fail(2, "path-not-normalized")
    normalized = path.as_posix()
    if normalized != raw:
        fail(2, "path-not-normalized")
    return normalized


def check_containment(path):
    root = Path.cwd().resolve()
    try:
        resolved = (root / path).resolve(strict=False)
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            fail(2, "symlink-escape")
    except (OSError, RuntimeError, ValueError):
        fail(2, "symlink-unverifiable")


try:
    policy = json.loads(read_text(policy_path, "policy-unreadable"))
    disclosure = policy["disclosureControls"]
    controls = policy["executionControls"]
    modes = policy["delegationModes"]
    review = policy["reviewControls"]
    if (
        policy.get("schemaVersion") != 2
        or disclosure.get("onMatch") != "decline-disclosure"
        or disclosure.get("exitCode") != 3
        or controls.get("modelCommandAuthority") != "none"
        or mode not in modes
        or review.get("pathNameEmbargo") is not False
    ):
        fail(2, "policy-contract")
except (KeyError, TypeError, json.JSONDecodeError):
    fail(2, "policy-contract")


def placeholder(value):
    value = value.strip().strip("'\"`").rstrip(".,;")
    lowered = value.lower()
    if not value:
        return True
    if lowered in {
        "redacted", "<redacted>", "<token>", "<secret>", "<password>",
        "<api-key>", "<value>", "example", "example-value", "changeme",
        "placeholder", "...", "xxx", "xxxxx",
    }:
        return True
    if re.fullmatch(r"\$\{?[A-Z][A-Z0-9_]*\}?", value):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|DSN)", value):
        return True
    if re.fullmatch(r"<[^>\r\n]*(?:token|secret|key|password|value|redacted|example)[^>\r\n]*>", lowered):
        return True
    return lowered.startswith(("example-", "test-", "dummy-", "placeholder-"))


def entropy(value):
    counts = collections.Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def high_confidence(value):
    value = value.strip().strip("'\"`").rstrip(".,;")
    if placeholder(value) or len(value) < 16 or any(char.isspace() for char in value):
        return False
    classes = sum((
        bool(re.search(r"[a-z]", value)),
        bool(re.search(r"[A-Z]", value)),
        bool(re.search(r"[0-9]", value)),
        bool(re.search(r"[^A-Za-z0-9]", value)),
    ))
    return classes >= 2 or entropy(value) >= 3.5


def scan_disclosure(text):
    if re.search(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----", text):
        fail(3, "private-key")

    for match in re.finditer(
        r"(?<![A-Za-z0-9])(?:sk-or-v1-|sk-ant-|ghp_|github_pat_|AKIA)([A-Za-z0-9_./+=:-]{16,})",
        text,
    ):
        if not placeholder(match.group(0)):
            fail(3, "high-confidence-credential")

    for match in re.finditer(r"\bAuthorization\s*:\s*Bearer\s+([^\s,;]+)", text, re.I):
        if high_confidence(match.group(1)):
            fail(3, "access-token")

    assignment = re.compile(
        r"""(?ix)
        ["']?
        (
          [A-Z0-9_]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|SESSION[_-]?(?:ID|TOKEN|SECRET)|
          TOKEN|SECRET|PASSWORD|PRIVATE[_-]?VALUE)
          |api[_-]?key|access[_-]?token|session[_-]?(?:token|secret)|
          session[_-]?id|client[_-]?secret|token|password
        )
        ["']?\s*[:=]\s*["']?([^\s"',;#}]+)
        """
    )
    for match in assignment.finditer(text):
        if high_confidence(match.group(2)):
            fail(3, "high-confidence-credential")

    for match in re.finditer(
        r"\b[a-z][a-z0-9+.-]*://([^/\s:@]+):([^/\s@]*)@([^/\s]+)",
        text,
        re.I,
    ):
        password = match.group(2)
        if password and not placeholder(password):
            fail(3, "authenticated-dsn")

    if re.search(
        r"(?im)^\s*(?:data[_ -]?classification|classification|privacy[_ -]?class)"
        r"\s*[:=]\s*(?:private|regulated)\b",
        text,
    ):
        fail(3, "classified-private-data")


def parse_header_path(line, prefix):
    if not line.startswith(prefix):
        fail(2, "diff-file-header")
    try:
        fields = shlex.split(line[len(prefix):].rstrip("\r\n"))
    except ValueError:
        fail(2, "diff-quoted-path")
    if len(fields) != 1:
        fail(2, "diff-file-header")
    raw = fields[0]
    if raw == "/dev/null":
        return None
    expected = "a/" if prefix == "--- " else "b/"
    if not raw.startswith(expected):
        fail(2, "diff-file-prefix")
    return normalize(raw[2:])


def parse_diff(text):
    if not text.strip():
        fail(2, "empty-diff")
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith("diff --git ")]
    if not starts or "".join(lines[:starts[0]]).strip():
        fail(2, "headerless-diff")

    parsed = set()
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        section = lines[start:end]
        try:
            fields = shlex.split(section[0].rstrip("\r\n"))
        except ValueError:
            fail(2, "diff-quoted-path")
        if len(fields) != 4 or fields[:2] != ["diff", "--git"]:
            fail(2, "diff-git-header")
        if not fields[2].startswith("a/") or not fields[3].startswith("b/"):
            fail(2, "diff-git-prefix")
        git_old = normalize(fields[2][2:])
        git_new = normalize(fields[3][2:])
        check_containment(git_old)
        check_containment(git_new)

        if any(
            line.startswith(("GIT binary patch", "Binary files "))
            or line.startswith(("new file mode 120000", "old mode 120000", "new mode 160000"))
            for line in section
        ):
            fail(2, "binary-or-symlink-diff")

        hunk_indexes = [i for i, line in enumerate(section) if line.startswith("@@ ")]
        preamble = section[:hunk_indexes[0]] if hunk_indexes else section
        old_indexes = [i for i, line in enumerate(preamble) if line.startswith("--- ")]
        new_indexes = [i for i, line in enumerate(preamble) if line.startswith("+++ ")]
        if len(old_indexes) != 1 or len(new_indexes) != 1 or not hunk_indexes:
            fail(2, "non-unified-diff")
        if new_indexes[0] != old_indexes[0] + 1 or hunk_indexes[0] <= new_indexes[0]:
            fail(2, "diff-header-order")

        file_old = parse_header_path(section[old_indexes[0]], "--- ")
        file_new = parse_header_path(section[new_indexes[0]], "+++ ")
        if (file_old is None and file_new is None) or (
            file_old is not None and file_old != git_old
        ) or (file_new is not None and file_new != git_new):
            fail(2, "diff-header-mismatch")

        changed_lines = 0
        for hunk_position, hunk_start in enumerate(hunk_indexes):
            hunk_end = hunk_indexes[hunk_position + 1] if hunk_position + 1 < len(hunk_indexes) else len(section)
            header = section[hunk_start].rstrip("\r\n")
            match = re.match(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@", header)
            if not match:
                fail(2, "malformed-hunk")
            old_expected = int(match.group(1) or "1")
            new_expected = int(match.group(2) or "1")
            old_seen = new_seen = 0
            for line in section[hunk_start + 1:hunk_end]:
                if line.startswith("\\ No newline at end of file"):
                    continue
                if not line or line[0] not in " +-":
                    fail(2, "malformed-hunk")
                if line[0] in " -":
                    old_seen += 1
                if line[0] in " +":
                    new_seen += 1
                if line[0] in "+-":
                    changed_lines += 1
            if old_seen != old_expected or new_seen != new_expected:
                fail(2, "hunk-count-mismatch")
        if not changed_lines:
            fail(2, "empty-diff")
        parsed.update((git_old, git_new))
    return parsed


if mode == "artifact-delegation":
    for content_path in content_paths:
        scan_disclosure(read_text(content_path, "content-unreadable"))
    raise SystemExit(0)

changed_text = read_text(changed_path, "changed-files-unreadable")
try:
    changed = {
        normalize(line)
        for line in changed_text.splitlines()
        if line
    }
except TypeError:
    fail(2, "changed-files")
if not changed:
    fail(2, "changed-files-empty")
for path in changed:
    check_containment(path)

parsed = set()
diff_text = ""
if diff_path:
    diff_text = read_text(diff_path, "diff-unreadable")
    parsed = parse_diff(diff_text)
    if not parsed.issubset(changed):
        fail(2, "undeclared-output-path")
elif mode == "mechanical-review":
    fail(2, "diff-required")

for content_path in content_paths:
    scan_disclosure(read_text(content_path, "content-unreadable"))
if diff_text:
    # Scan the complete unified diff, including removed lines and context.
    scan_disclosure(diff_text)

if output_path:
    try:
        with open(output_path, "wb") as output:
            for path in sorted(parsed):
                output.write(path.encode("utf-8") + b"\0")
    except OSError:
        fail(2, "output-paths")
if output_diff_path:
    if not diff_text:
        fail(2, "output-diff-without-diff")
    try:
        Path(output_diff_path).write_text(diff_text, encoding="utf-8")
    except OSError:
        fail(2, "output-diff")
PY
