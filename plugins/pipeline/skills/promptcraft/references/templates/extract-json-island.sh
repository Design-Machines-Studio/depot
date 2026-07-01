#!/usr/bin/env bash
#
# extract-json-island.sh: Print the JSON data island from a pipeline HTML artifact.
#
# WHY THIS EXISTS:
#   Pipeline planning artifacts are dual-purpose HTML: human-readable prose plus a
#   <script type="application/json" id="pipeline-data"> island carrying structured
#   data (keyRequirements, chunks, visualDecisions, findings). Downstream agents
#   read the island instead of grepping rendered markup, which is brittle.
#
# WHAT THIS FIXES:
#   A single, dependency-light extractor agents can call regardless of whether the
#   artifact is .html (new) -- replaces ad-hoc markdown grepping in promptcraft,
#   plan-adversary, and the execution-orchestrator.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default)
#   - python3 preferred (robust HTML parsing); POSIX sed/grep fallback otherwise
#
# USAGE:
#   bash extract-json-island.sh <file.html> [island-id]
#     island-id defaults to "pipeline-data".
#   Prints the island's JSON to stdout. Exit 0 on success; non-zero (with a
#   stderr message) when the file or island is missing.
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent caller-controlled hijack of
#     python3, grep, sed, cat.
#   - The file is read read-only; nothing is executed from its contents.

set -uo pipefail

# SECURITY: fixed PATH so a poisoned caller environment can't hijack our tools.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

FILE="${1:-}"
ISLAND_ID="${2:-pipeline-data}"

# SECURITY: the sed fallback below interpolates ISLAND_ID into a sed address
# regex, so a value containing sed metacharacters or a newline could corrupt or
# inject sed commands. Restrict it to the character class real island ids use.
if ! printf '%s' "$ISLAND_ID" | grep -qE '^[A-Za-z0-9_-]+$'; then
  echo "ERROR: invalid island-id (must match [A-Za-z0-9_-]+): $ISLAND_ID" >&2
  exit 2
fi

if [ -z "$FILE" ]; then
  echo "ERROR: usage: extract-json-island.sh <file.html> [island-id]" >&2
  exit 2
fi
if [ ! -f "$FILE" ]; then
  echo "ERROR: file not found: $FILE" >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  ISLAND_ID="$ISLAND_ID" python3 - "$FILE" <<'PY'
import os, sys
from html.parser import HTMLParser

island_id = os.environ.get("ISLAND_ID", "pipeline-data")

class Island(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.found = False
        self.buf = []
    def handle_starttag(self, tag, attrs):
        if tag == "script":
            a = dict(attrs)
            if a.get("id") == island_id and a.get("type") == "application/json":
                self.capture = True
                self.found = True
    def handle_endtag(self, tag):
        if tag == "script" and self.capture:
            self.capture = False
    def handle_data(self, data):
        if self.capture:
            self.buf.append(data)

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    parser = Island()
    parser.feed(fh.read())

if not parser.found:
    sys.stderr.write("ERROR: no <script id='%s' type='application/json'> island in %s\n" % (island_id, sys.argv[1]))
    sys.exit(1)

text = "".join(parser.buf).strip()
# Validate it parses; emit canonical text so callers can pipe to jq/python.
try:
    import json
    json.loads(text)
except Exception as exc:
    sys.stderr.write("ERROR: island in %s is not valid JSON: %s\n" % (sys.argv[1], exc))
    sys.exit(1)
sys.stdout.write(text + "\n")
PY
  exit $?
fi

# Fallback: no python3. Extract the script block with sed, strip the tags.
# Matches the opening tag with the requested id on a single line (the convention
# emitted by data-island.html), through the next </script>.
island=$(sed -n "/<script[^>]*id=\"$ISLAND_ID\"[^>]*>/,/<\/script>/p" "$FILE" \
  | sed "s/.*<script[^>]*>//; s/<\/script>.*//")
if [ -z "$island" ]; then
  echo "ERROR: no '$ISLAND_ID' island found in $FILE (and python3 unavailable for robust parse)" >&2
  exit 1
fi
printf '%s\n' "$island"
exit 0
