#!/usr/bin/env bash
# Fail-closed OpenRouter delegation boundary shared by review and execution runners.
# Exit 0 = safe, 3 = decline to Codex, 2 = malformed/unverifiable input.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

POLICY=""
CHANGED_FILES=""
CONTENT_FILE=""
DIFF_FILE=""
OUTPUT_PATHS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --policy) POLICY="$2"; shift 2;;
    --changed-files) CHANGED_FILES="$2"; shift 2;;
    --content-file) CONTENT_FILE="$2"; shift 2;;
    --diff-file) DIFF_FILE="$2"; shift 2;;
    --output-paths) OUTPUT_PATHS="$2"; shift 2;;
    *) echo "delegation-boundary: unknown argument" >&2; exit 2;;
  esac
done

[ -f "$POLICY" ] && [ -f "$CHANGED_FILES" ] || {
  echo "delegation-boundary: policy and changed-file list are required" >&2
  exit 2
}
[ -z "$CONTENT_FILE" ] || [ -f "$CONTENT_FILE" ] || exit 2
[ -z "$DIFF_FILE" ] || [ -f "$DIFF_FILE" ] || exit 2

python3 - "$POLICY" "$CHANGED_FILES" "$CONTENT_FILE" "$DIFF_FILE" "$OUTPUT_PATHS" <<'PY'
import fnmatch
import json
import re
import shlex
import sys
from pathlib import PurePosixPath

policy_path, changed_path, content_path, diff_path, output_path = sys.argv[1:]

def fail(code):
    raise SystemExit(code)

def normalize(raw):
    if not isinstance(raw, str) or not raw or any(ord(char) < 32 for char in raw):
        fail(2)
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        fail(2)
    return path.as_posix()

try:
    policy = json.load(open(policy_path, encoding="utf-8"))
    configured = policy["neverRouteToOpenRouter"]["pathGlobs"]
except Exception:
    fail(2)
if not isinstance(configured, list) or not all(isinstance(item, str) and item for item in configured):
    fail(2)

canon = [
    "internal/auth/**", "internal/federation/**", "**/secretbox*",
    "**/destructive_confirmation*", "internal/baseplate/email/settings*",
    "deploy/**", "*.env*",
]
globs = [item.replace("**/", "*").replace("**", "*") for item in sorted(set(canon) | set(configured))]

try:
    changed = {normalize(line) for line in open(changed_path, encoding="utf-8").read().splitlines() if line}
except (OSError, UnicodeError):
    fail(2)
if not changed:
    fail(2)
if any(any(fnmatch.fnmatch(path, pattern) for pattern in globs) for path in changed):
    fail(3)

parsed = set()
diff_text = ""
if diff_path:
    try:
        diff_text = open(diff_path, encoding="utf-8", errors="replace").read()
    except OSError:
        fail(2)
    for line in diff_text.splitlines():
        if not line.startswith("diff --git "):
            continue
        try:
            fields = shlex.split(line)
        except ValueError:
            fail(2)
        if len(fields) != 4 or not fields[2].startswith("a/") or not fields[3].startswith("b/"):
            fail(2)
        parsed.update((normalize(fields[2][2:]), normalize(fields[3][2:])))
    if diff_text.strip() and not parsed:
        fail(2)
    if not parsed.issubset(changed):
        fail(3)
    if any(any(fnmatch.fnmatch(path, pattern) for pattern in globs) for path in parsed):
        fail(3)

texts = [diff_text]
if content_path:
    try:
        texts.append(open(content_path, encoding="utf-8", errors="replace").read())
    except OSError:
        fail(2)
payload = "\n".join(texts)
path_tokens = set(re.findall(r"(?:^|[\s'\"`(])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.*-]+)+|\.env[A-Za-z0-9_.-]*)", payload))
if any(any(fnmatch.fnmatch(token, pattern) for pattern in globs) for token in path_tokens):
    fail(3)
patterns = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?:sk-or-v1-|sk-ant-|ghp_|github_pat_|AKIA)[A-Za-z0-9_-]{16,}"),
    re.compile(r"[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.I),
    re.compile(r"\b(?:api[_-]?key|token|secret|password|dsn|connection[_-]?string)\b\s*[:=]\s*['\"]?([^\s'\"]{16,})", re.I),
)
for pattern in patterns:
    for match in pattern.finditer(payload):
        value = match.group(1) if match.lastindex else match.group(0)
        lowered = value.lower()
        if any(marker in value for marker in ("${", "...", "<")) or "example" in lowered:
            continue
        fail(3)

if output_path:
    try:
        with open(output_path, "wb") as output:
            for path in sorted(parsed):
                output.write(path.encode("utf-8") + b"\0")
    except OSError:
        fail(2)
PY
