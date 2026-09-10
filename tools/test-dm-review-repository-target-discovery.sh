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
assert grep -Fq 'does not start an unregistered' "$CONTRACT"
assert grep -Fq '`review-created-compose`' "$CONTRACT"
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

Application: storefront-web Compose consumer from the current physical checkout and HEAD.
Status/readiness argv: ["make","dev","ACTION=status"]
Start/rebuild argv: ["docker","compose","up","storefront-web"] through the Workflow Kernel creation plan.
Cleanup is owned only by the Workflow Kernel registry.
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
cat > "$REPO/Makefile" <<'EOF'
.PHONY: dev
dev:
	@case "$(ACTION)" in \
	  status) ./tools/dev-status ;; \
	  *) exit 2 ;; \
	esac
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

# A documented-but-stopped target performs status, then routes Compose creation
# through the same durable Workflow Kernel registry used by record-create. It
# never invokes the declared Compose argv or a raw process directly.
run_attempt stopped-status make dev ACTION=status
assert test "$(cat "$TMP/stopped-status.rc")" -eq 2
assert grep -Fq 'storefront-web is stopped' "$TMP/stopped-status.stderr"
mkdir -p "$TMP/review"
PYTHONPATH="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references" python3 - <<PY
from datetime import datetime, timezone
from pathlib import Path
from workflow_kernel.resources import ResourceKind, ResourceRecord, ResourceRegistry

created = datetime.now(timezone.utc)
ResourceRegistry(Path("$TMP/review/resources.jsonl")).register(ResourceRecord(
    resource_id="storefront-compose-container",
    kind=ResourceKind.CONTAINER,
    run_id="fixture-review",
    node_id="storefront-compose",
    lifecycle="run",
    cleanup_policy="stop-remove",
    created_at=created,
    labels={
        "com.designmachines.depot.managed":"true",
        "com.designmachines.depot.run-id":"fixture-review",
        "com.designmachines.depot.node-id":"storefront-compose",
        "com.designmachines.depot.created-at":created.isoformat(),
        "com.designmachines.depot.lifecycle":"run",
        "com.designmachines.depot.cleanup-policy":"stop-remove",
        "com.designmachines.depot.repository-scope-id":"0" * 64,
    },
))
PY
assert jq -se 'any(.[]; .event == "registered" and .resource.node_id == "storefront-compose")' \
  "$TMP/review/resources.jsonl"
touch "$TARGET_READY_MARKER"
discovered_url="$TARGET_DYNAMIC_URL"
run_attempt started-status make dev ACTION=status
assert test "$(cat "$TMP/started-status.rc")" -eq 0
assert grep -Fq "application=storefront-web" "$TMP/started-status.stdout"
assert grep -Fq "checkout=$(cd "$REPO" && pwd -P)" "$TMP/started-status.stdout"
assert grep -Fq "commit=$(git -C "$REPO" rev-parse HEAD)" "$TMP/started-status.stdout"
assert grep -Fq "url=$TARGET_DYNAMIC_URL" "$TMP/started-status.stdout"
assert test "$(grep -Ec '^(start|cleanup)$' "$TARGET_ATTEMPT_LOG" || true)" -eq 0
start_line="$(grep -nF 'Start/rebuild argv:' "$REPO/docs/development.md" | cut -d: -f1)"
target_line="$(grep -nF 'Target URL:' "$REPO/docs/development.md" | cut -d: -f1)"
assert test "$start_line" -gt 0
jq -cn --arg url "$discovered_url" --arg checkout "$(cd "$REPO" && pwd -P)" \
  --arg head "$(git -C "$REPO" rev-parse HEAD)" --argjson start_line "$start_line" \
  --argjson target_line "$target_line" \
  '{targetSource:"repository-declaration",source:{path:"docs/development.md",lineStart:$start_line,lineEnd:$target_line},
    application:"storefront-web",checkoutRoot:$checkout,repositoryCommit:$head,checkoutState:"clean",
    statusAttempt:{commandArgv:["make","dev","ACTION=status"],initialExitStatus:2,finalExitStatus:0},
    creationPlan:{declaredArgv:["docker","compose","up","storefront-web"],authority:"workflow-kernel",fixtureExecution:"simulated"},
    targetUrl:$url,targetUrlProvenance:"status-output",resourceOwnership:"review-created-compose",
    resourceRegistryRef:"review/resources.jsonl",resourceRegistryRunId:"fixture-review",
    resourceRegistryNodeId:"storefront-compose"}' \
  > "$TMP/stopped-evidence.json"
assert jq -e --arg url "$TARGET_DYNAMIC_URL" '
  .targetSource == "repository-declaration" and .source.path == "docs/development.md" and
  .source.lineStart > 0 and .source.lineEnd >= .source.lineStart and
  .statusAttempt.commandArgv == ["make","dev","ACTION=status"] and
  .statusAttempt.initialExitStatus == 2 and .statusAttempt.finalExitStatus == 0 and
  .creationPlan == {declaredArgv:["docker","compose","up","storefront-web"],authority:"workflow-kernel",fixtureExecution:"simulated"} and
  .targetUrl == $url and .targetUrlProvenance == "status-output" and
  .resourceOwnership == "review-created-compose" and
  .resourceRegistryRef == "review/resources.jsonl" and
  .resourceRegistryRunId == "fixture-review" and
  .resourceRegistryNodeId == "storefront-compose"' "$TMP/stopped-evidence.json"

# An actual failed status command is executed once and preserves its real
# exit/failure evidence without granting raw-process start authority.
rm -f "$TARGET_READY_MARKER"
: > "$TARGET_ATTEMPT_LOG"
run_attempt actual-failure make dev ACTION=status
assert test "$(cat "$TMP/actual-failure.rc")" -eq 2
assert grep -Fxq status "$TARGET_ATTEMPT_LOG"
assert grep -Fq 'storefront-web is stopped' "$TMP/actual-failure.stderr"
assert test ! -e "$TARGET_READY_MARKER"
failure_reason="$(tail -c 8192 "$TMP/actual-failure.stderr")"
jq -cn --arg reason "$failure_reason" \
  '{reason:"dev_server_unavailable",source:{path:"docs/development.md",lineStart:4,lineEnd:4},
    attemptedCommand:{argv:["make","dev","ACTION=status"],exitStatus:2,failureReason:$reason}}' \
  > "$TMP/actual-failure-evidence.json"
assert jq -e '.reason == "dev_server_unavailable" and
  .attemptedCommand.argv == ["make","dev","ACTION=status"] and
  .attemptedCommand.exitStatus == 2 and
  (.attemptedCommand.failureReason | contains("storefront-web is stopped"))' \
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
run_attempt stale-status make dev ACTION=status
assert test "$(cat "$TMP/stale-status.rc")" -eq 2
assert test "$(grep -Ec '^(start|cleanup)$' "$TARGET_ATTEMPT_LOG" || true)" -eq 0

# A suitable pre-existing exact-head target runs status only. It is neither
# started nor cleaned, and remains available after the scenario.
touch "$TARGET_READY_MARKER"
: > "$TARGET_ATTEMPT_LOG"
run_attempt preexisting-status make dev ACTION=status
assert test "$(cat "$TMP/preexisting-status.rc")" -eq 0
assert grep -Fq "commit=$current_head" "$TMP/preexisting-status.stdout"
assert test "$(grep -c '^status$' "$TARGET_ATTEMPT_LOG")" -eq 1
assert test "$(grep -Ec '^(start|cleanup)$' "$TARGET_ATTEMPT_LOG" || true)" -eq 0
assert test -e "$TARGET_READY_MARKER"
jq -cn --arg head "$current_head" --arg url "$TARGET_DYNAMIC_URL" \
  '{targetSource:"repository-declaration",repositoryCommit:$head,targetUrl:$url,
    targetUrlProvenance:"status-output",resourceOwnership:"pre-existing",resourceRegistryRef:"",
    resourceRegistryRunId:"",resourceRegistryNodeId:""}' \
  > "$TMP/preexisting-evidence.json"
assert jq -e '.resourceOwnership == "pre-existing" and
  .targetUrlProvenance == "status-output"' "$TMP/preexisting-evidence.json"

# Declared project beats an unrelated attached tab; maintenance retains ownership.
assert grep -Fq '2. the established project domain and canonical checkout' "$CONTRACT"
assert grep -Fq '5. an attached automation-capable T3 preview' "$CONTRACT"
assert grep -Fq 'git checkout --detach <exact-committed-head>' "$CONTRACT"
assert grep -Fq 'name the concrete collision' "$CONTRACT"
assert grep -Fq 'changing Git HEAD alone does not refresh' "$CONTRACT"
assert grep -Fq 'cleanup argv or ownership adoption' "$CONTRACT"
assert grep -Fq 'simultaneous Federation peers' "$CONTRACT"

# Exercise ordinary Git in disposable fixture repos. The implementation branch
# stays owned by its worktree. This simulated binary requires a separate rebuild.
SERVING="$TMP/serving"
BUILDER="$TMP/builder"
git init -q "$SERVING"
printf 'base\n' > "$SERVING/source.txt"
git -C "$SERVING" add source.txt
git -C "$SERVING" -c user.name=test -c user.email=test@example.invalid commit -qm base
git -C "$SERVING" rev-parse HEAD > "$TMP/served-build-head"
git -C "$SERVING" worktree add -qb fixture-feature "$BUILDER"
printf 'feature\n' > "$BUILDER/source.txt"
git -C "$BUILDER" add source.txt
git -C "$BUILDER" -c user.name=test -c user.email=test@example.invalid commit -qm feature
feature_head="$(git -C "$BUILDER" rev-parse HEAD)"
if git -C "$SERVING" checkout fixture-feature 2> "$TMP/branch-owned-error"; then
  printf 'FAIL: duplicate branch checkout unexpectedly succeeded\n' >&2
  exit 1
fi
assert grep -Eq 'already (checked out|used)' "$TMP/branch-owned-error"
git -C "$SERVING" checkout -q --detach "$feature_head"
assert test "$(git -C "$SERVING" rev-parse HEAD)" = "$feature_head"
assert test "$(git -C "$BUILDER" branch --show-current)" = fixture-feature
assert test -z "$(git -C "$SERVING" branch --show-current)"
assert test "$(cat "$TMP/served-build-head")" != "$feature_head"
# Simulated rebuild receipt, not application/browser evidence.
git -C "$SERVING" rev-parse HEAD > "$TMP/served-build-head"
assert test "$(cat "$TMP/served-build-head")" = "$feature_head"
printf 'unrelated owned edit\n' >> "$SERVING/source.txt"
before_dirty="$(git -C "$SERVING" diff | git hash-object --stdin)"
assert test -n "$(git -C "$SERVING" status --porcelain)"
# On a collision, retain the checkout without switching or cleaning it.
assert test "$(git -C "$SERVING" diff | git hash-object --stdin)" = "$before_dirty"
assert test -d "$SERVING"

printf 'dm-review-repository-target-discovery: %d assertions passed\n' "$pass"
