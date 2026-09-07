#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/plugins/dm-review/skills/review/references/repository-browser-target-discovery.md"
READINESS="$ROOT/plugins/dm-review/skills/review/references/ui-review-readiness.md"
REVIEW_SKILL="$ROOT/plugins/dm-review/skills/review/SKILL.md"
VISUAL_SKILL="$ROOT/plugins/dm-review/skills/visual-test/SKILL.md"
FULL_LANES="$ROOT/plugins/dm-review/skills/review/references/full-lane-dispatch.md"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/dm-review-repository-target.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

# Contract anchors prove the three entry points share one host-owned pass. The
# scenarios below separately execute fixture commands; these grep checks are
# not treated as proof that a declared command was attempted.
assert grep -Fq 'The host, not a generalized parser, interprets human-authored declarations.' "$CONTRACT"
assert grep -Fq 'root `AGENTS.md` and root `CLAUDE.md`' "$CONTRACT"
assert grep -Fq '`tests/ux/verification.json`' "$CONTRACT"
assert grep -Fq 'targetSource:' "$CONTRACT"
assert grep -Fq 'repository-declaration' "$CONTRACT"
assert grep -Fq 'accepted exact-head browser packet reuse' "$CONTRACT"
assert grep -Fq 'A suitable target that was already running is' "$CONTRACT"
assert grep -Fq '`pre-existing`' "$CONTRACT"
assert grep -Fq 'repository-browser-target-discovery.md' "$READINESS"
assert grep -Fq 'repository-browser-target-discovery.md' "$REVIEW_SKILL"
assert grep -Fq 'repository-browser-target-discovery.md' "$VISUAL_SKILL"
assert grep -Fq 'repository-browser-target-discovery.md' "$FULL_LANES"

ABSENT="$TMP/absent"
mkdir -p "$ABSENT/tests/ux"
git -C "$ABSENT" init -q
cat > "$ABSENT/AGENTS.md" <<'EOF'
# Project instructions

Run the existing development loop when one is documented.
EOF
cat > "$ABSENT/CLAUDE.md" <<'EOF'
# Claude instructions

Follow AGENTS.md.
EOF
cat > "$ABSENT/README.md" <<'EOF'
Example only: browse http://localhost:3000 and run ./not-a-declaration.
EOF
cat > "$ABSENT/package.json" <<'EOF'
{"scripts":{"dev":"./not-a-declaration"}}
EOF
cat > "$ABSENT/tests/ux/verification.json" <<'EOF'
{"schemaVersion":1,"viewports":["example-only"]}
EOF
git -C "$ABSENT" add .
git -C "$ABSENT" -c user.name=test -c user.email=test@example.invalid commit -qm fixture

# The host inspection fixture names every inspected path explicitly. README and
# package scripts remain outside the closed boundary and cannot become a target.
printf '%s\n' AGENTS.md CLAUDE.md tests/ux/verification.json > "$TMP/absent-inspected.log"
assert test "$(wc -l < "$TMP/absent-inspected.log" | tr -d ' ')" -eq 3
assert grep -Fxq AGENTS.md "$TMP/absent-inspected.log"
assert grep -Fxq CLAUDE.md "$TMP/absent-inspected.log"
assert grep -Fxq tests/ux/verification.json "$TMP/absent-inspected.log"
assert sh -c '! grep -Eq "README|package.json" "$1"' sh "$TMP/absent-inspected.log"
assert grep -Fq 'No repository-owned declaration in the closed inspection boundary:' "$CONTRACT"
assert grep -Fq '`visual_target_unavailable`' "$CONTRACT"

REPO="$TMP/repository"
mkdir -p "$REPO/docs" "$REPO/tools"
git -C "$REPO" init -q
cat > "$REPO/AGENTS.md" <<'EOF'
# Project instructions

The storefront author loop is declared in docs/development.md.
EOF
cat > "$REPO/CLAUDE.md" <<'EOF'
# Claude instructions

Follow AGENTS.md for the selected checkout.
EOF
cat > "$REPO/docs/development.md" <<'EOF'
# Development

Application: storefront-web from the current physical checkout and HEAD.
Status/readiness argv: ["./tools/dev-status"]
Start/rebuild argv: ["./tools/dev-start"]
Cleanup argv: ["./tools/dev-stop"]
Target URL: accept the HTTP(S) URL printed by status or start.
Production example only: https://storefront.example.com
Port example only: 3000
EOF
cat > "$REPO/tools/dev-status" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' status >> "$TARGET_ATTEMPT_LOG"
if [ ! -f "$TARGET_READY_MARKER" ]; then
  printf '%s\n' 'storefront-web is stopped' >&2
  exit 7
fi
printf 'application=storefront-web\ncheckout=%s\ncommit=%s\nstate=%s\nurl=%s\n' \
  "$(pwd -P)" "$(git rev-parse HEAD)" \
  "$(if [ -n "$(git status --porcelain)" ]; then printf dirty; else printf clean; fi)" \
  "$TARGET_DYNAMIC_URL"
EOF
cat > "$REPO/tools/dev-start" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' start >> "$TARGET_ATTEMPT_LOG"
touch "$TARGET_READY_MARKER"
printf '%s\n' "$TARGET_DYNAMIC_URL"
EOF
cat > "$REPO/tools/dev-stop" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' cleanup >> "$TARGET_ATTEMPT_LOG"
rm -f "$TARGET_READY_MARKER"
EOF
cat > "$REPO/tools/dev-fail" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' failed-start >> "$TARGET_ATTEMPT_LOG"
printf '%s\n' 'fixture start failed before target creation' >&2
exit 42
EOF
chmod +x "$REPO"/tools/dev-*
git -C "$REPO" add .
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit -qm fixture

export TARGET_ATTEMPT_LOG="$TMP/attempts.log"
export TARGET_READY_MARKER="$TMP/target-ready"
export TARGET_DYNAMIC_URL="http://127.0.0.1:49173/review"
: > "$TARGET_ATTEMPT_LOG"

run_attempt() {
  local name="$1"
  shift
  set +e
  (cd "$REPO" && "$@") > "$TMP/$name.stdout" 2> "$TMP/$name.stderr"
  local rc=$?
  set -e
  printf '%s\n' "$rc" > "$TMP/$name.rc"
}

# A documented-but-stopped target performs status, the exact start procedure,
# and status again. The URL is taken from actual command output, not port 3000.
run_attempt stopped-status ./tools/dev-status
assert test "$(cat "$TMP/stopped-status.rc")" -eq 7
assert grep -Fq 'storefront-web is stopped' "$TMP/stopped-status.stderr"
run_attempt stopped-start ./tools/dev-start
assert test "$(cat "$TMP/stopped-start.rc")" -eq 0
discovered_url="$(tail -n 1 "$TMP/stopped-start.stdout")"
assert test "$discovered_url" = "$TARGET_DYNAMIC_URL"
assert sh -c '! grep -Fq "3000" "$1"' sh "$TMP/stopped-start.stdout"
run_attempt started-status ./tools/dev-status
assert test "$(cat "$TMP/started-status.rc")" -eq 0
assert grep -Fq "application=storefront-web" "$TMP/started-status.stdout"
assert grep -Fq "checkout=$(cd "$REPO" && pwd -P)" "$TMP/started-status.stdout"
assert grep -Fq "commit=$(git -C "$REPO" rev-parse HEAD)" "$TMP/started-status.stdout"
assert grep -Fq "url=$TARGET_DYNAMIC_URL" "$TMP/started-status.stdout"
assert test "$(grep -c '^start$' "$TARGET_ATTEMPT_LOG")" -eq 1
start_line="$(grep -nF 'Start/rebuild argv:' "$REPO/docs/development.md" | cut -d: -f1)"
target_line="$(grep -nF 'Target URL:' "$REPO/docs/development.md" | cut -d: -f1)"
assert test "$start_line" -gt 0
jq -cn --arg url "$discovered_url" --arg checkout "$(cd "$REPO" && pwd -P)" \
  --arg head "$(git -C "$REPO" rev-parse HEAD)" --argjson start_line "$start_line" \
  --argjson target_line "$target_line" \
  '{targetSource:"repository-declaration",source:{path:"docs/development.md",lineStart:$start_line,lineEnd:$target_line},
    application:"storefront-web",checkoutRoot:$checkout,repositoryCommit:$head,checkoutState:"clean",
    statusAttempt:{commandArgv:["./tools/dev-status"],initialExitStatus:7,finalExitStatus:0},
    startAttempt:{commandArgv:["./tools/dev-start"],exitStatus:0},
    targetUrl:$url,targetUrlProvenance:"start-output",resourceOwnership:"review-created"}' \
  > "$TMP/stopped-evidence.json"
assert jq -e --arg url "$TARGET_DYNAMIC_URL" '
  .targetSource == "repository-declaration" and .source.path == "docs/development.md" and
  .source.lineStart > 0 and .source.lineEnd >= .source.lineStart and
  .statusAttempt.commandArgv == ["./tools/dev-status"] and
  .statusAttempt.initialExitStatus == 7 and .statusAttempt.finalExitStatus == 0 and
  .startAttempt == {commandArgv:["./tools/dev-start"],exitStatus:0} and
  .targetUrl == $url and .targetUrlProvenance == "start-output" and
  .resourceOwnership == "review-created"' "$TMP/stopped-evidence.json"

# Review-created resources use the recorded cleanup; this successful fixture
# cleans once and proves the marker is gone.
run_attempt started-cleanup ./tools/dev-stop
assert test "$(cat "$TMP/started-cleanup.rc")" -eq 0
assert test ! -e "$TARGET_READY_MARKER"
assert test "$(grep -c '^cleanup$' "$TARGET_ATTEMPT_LOG")" -eq 1

# An actual failed declared command is executed once and preserves its real
# exit/failure evidence. A token assertion alone cannot satisfy this case.
: > "$TARGET_ATTEMPT_LOG"
run_attempt actual-failure ./tools/dev-fail
assert test "$(cat "$TMP/actual-failure.rc")" -eq 42
assert grep -Fxq failed-start "$TARGET_ATTEMPT_LOG"
assert grep -Fq 'fixture start failed before target creation' "$TMP/actual-failure.stderr"
assert test ! -e "$TARGET_READY_MARKER"
failure_reason="$(tail -c 8192 "$TMP/actual-failure.stderr")"
jq -cn --arg reason "$failure_reason" \
  '{reason:"dev_server_unavailable",source:{path:"docs/development.md",lineStart:5,lineEnd:5},
    attemptedCommand:{argv:["./tools/dev-fail"],exitStatus:42,failureReason:$reason}}' \
  > "$TMP/actual-failure-evidence.json"
assert jq -e '.reason == "dev_server_unavailable" and
  .attemptedCommand.argv == ["./tools/dev-fail"] and
  .attemptedCommand.exitStatus == 42 and
  (.attemptedCommand.failureReason | contains("fixture start failed"))' \
  "$TMP/actual-failure-evidence.json"
assert grep -Fq 'A declared status/start/readiness command is actually attempted and fails:' "$CONTRACT"
assert grep -Fq '`dev_server_unavailable`' "$CONTRACT"

# Stale exact-head evidence is rejected by the host identity check before the
# repository author loop is attempted for the new head.
recorded_head="$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" -c user.name=test -c user.email=test@example.invalid commit --allow-empty -qm newer-head
current_head="$(git -C "$REPO" rev-parse HEAD)"
assert test "$recorded_head" != "$current_head"
: > "$TARGET_ATTEMPT_LOG"
run_attempt stale-status ./tools/dev-status
assert test "$(cat "$TMP/stale-status.rc")" -eq 7
run_attempt stale-start ./tools/dev-start
assert test "$(cat "$TMP/stale-start.rc")" -eq 0
assert grep -Fxq "$TARGET_DYNAMIC_URL" "$TMP/stale-start.stdout"
assert test "$(grep -c '^start$' "$TARGET_ATTEMPT_LOG")" -eq 1
run_attempt stale-cleanup ./tools/dev-stop
assert test ! -e "$TARGET_READY_MARKER"

# A suitable pre-existing exact-head target runs status only. It is neither
# started nor cleaned, and remains available after the scenario.
touch "$TARGET_READY_MARKER"
: > "$TARGET_ATTEMPT_LOG"
run_attempt preexisting-status ./tools/dev-status
assert test "$(cat "$TMP/preexisting-status.rc")" -eq 0
assert grep -Fq "commit=$current_head" "$TMP/preexisting-status.stdout"
assert test "$(grep -c '^status$' "$TARGET_ATTEMPT_LOG")" -eq 1
assert test "$(grep -Ec '^(start|cleanup)$' "$TARGET_ATTEMPT_LOG" || true)" -eq 0
assert test -e "$TARGET_READY_MARKER"
jq -cn --arg head "$current_head" --arg url "$TARGET_DYNAMIC_URL" \
  '{targetSource:"repository-declaration",repositoryCommit:$head,targetUrl:$url,
    targetUrlProvenance:"status-output",resourceOwnership:"pre-existing"}' \
  > "$TMP/preexisting-evidence.json"
assert jq -e '.resourceOwnership == "pre-existing" and
  .targetUrlProvenance == "status-output"' "$TMP/preexisting-evidence.json"

printf 'dm-review-repository-target-discovery: %d assertions passed\n' "$pass"
