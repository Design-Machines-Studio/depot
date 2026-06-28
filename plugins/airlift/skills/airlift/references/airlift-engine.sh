#!/usr/bin/env bash
#
# airlift-engine.sh: Tier-1 deterministic session-handoff engine for airlift.
#
# WHY THIS EXISTS:
#   A usage cap, rate limit, or model switch should be a non-event. The airlift
#   skill promises a "spend zero model budget" safety net that snapshots the
#   working session into a portable .airlift/ bundle. Tier 2 (agent enrichment)
#   and Tier 3 (ccusage early warning) are best-effort bonuses; THIS engine is
#   the guarantee. It must run with no model, no network, and no AI API call --
#   pure local file + git operations -- so it can fire the instant a budget
#   warning appears, or even after the model has gone dark.
#
# WHAT THIS FIXES:
#   Without a deterministic capture, a handoff depends on the dying model
#   writing good notes -- exactly when it has no budget left to do so. This
#   engine captures objective state (git branch/HEAD/dirty, an uncommitted
#   patch, verify commands, existing pipeline/dm-review artifacts) and renders
#   a harness-neutral HANDOFF.md + RESUME_PROMPT.md from templates. It wires an
#   idempotent pointer marker into the harness instruction file so the next
#   session is told the bundle exists. Patch capture is lossless -- it records
#   the tracked changes (`git diff HEAD`) PLUS every untracked, non-ignored file
#   as an added-file diff, so resume loses nothing -- and NEVER forces a commit.
#   The marker upsert NEVER clobbers an existing file.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default; confirmed 3.2.57). NO bash-4 features:
#     no associative arrays, no mapfile/readarray, no ${var^^}, no sed -i.
#   - git (rev-parse, diff, status)
#   - python3 (state.json is built via a python3 heredoc + json.dump; JSON is
#     NEVER hand-concatenated)
#   - awk, mktemp, rm, date, grep (POSIX/BSD-portable usage only)
#   - NO network. NO curl/wget. NO AI API call. NO jq.
#
# USAGE:
#   # Capture a checkpoint into <repo-root>/.airlift/ and wire the marker into
#   # the repo-root CLAUDE.md:
#   bash airlift-engine.sh write
#   bash airlift-engine.sh write --phase execute --note "mid-refactor"
#   bash airlift-engine.sh write --instructions-file AGENTS.md
#
#   # Upsert just the marker block into an instruction file (idempotent):
#   bash airlift-engine.sh marker CLAUDE.md 3 2026-06-28T12:00:00Z
#
#   Environment overrides (all optional):
#     AIRLIFT_SOURCE_HARNESS  source.harness  (default: claude-code)
#     AIRLIFT_SOURCE_MODEL    source.model    (default: $AIRLIFT_MODEL or unknown)
#     AIRLIFT_MODEL           fallback for source.model
#     AIRLIFT_TARGETS         comma-separated targets (default: the 6 registry ids)
#     AIRLIFT_TEMPLATE_DIR    template dir override (default: <script-dir>/templates)
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value at the top to prevent a caller-controlled
#     PATH from hijacking git/python3/awk/mktemp/rm/date/grep.
#   - Temp files are created with mktemp and immediately chmod 600, then moved
#     atomically into place. A trap on EXIT/INT/TERM runs a glob sweep that
#     removes any leftover airlift.* temp in TMPDIR (command-substitution
#     subshells make a parent-process temp registry unreliable, so the sweep is
#     the authoritative cleanup).
#   - state.json is emitted by python3 via os.environ + json.dump -- values are
#     never interpolated into a hand-built JSON string, so notes/branch names
#     containing quotes or braces cannot corrupt the document.
#   - The marker upsert uses awk range replacement (robust on BSD awk) writing
#     to a 0600 temp then `mv`; it never uses `sed -i`, never reorders, and
#     keeps every byte outside the marker pair identical.
#   - No network calls of any kind. The only http(s) tokens in this file live
#     in this comment header.

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# ---------------------------------------------------------------------------
# Temp-file cleanup. Every temp is minted under TMPDIR with the prefix
# `airlift.$$.` (PID-scoped) so a single glob sweep removes only THIS process's
# temps -- a concurrent run (e.g. the statusLine-triggered early-warning engine
# write firing while a manual /airlift-out write is mid-flight in the same
# TMPDIR) cannot reap our in-flight temp. A per-process variable registry is
# unreliable here: every call site is `x="$(airlift_mktemp)"`, a
# command-substitution subshell, so a variable set inside it never reaches the
# parent. The EXIT/INT/TERM trap therefore relies on the PID-scoped glob sweep.
# ---------------------------------------------------------------------------
airlift_cleanup() {
  rm -f "${TMPDIR:-/tmp}"/airlift."$$".* 2>/dev/null || true
}

# Create a 0600 temp file and echo its path. Mirrors the secure-temp idiom.
airlift_mktemp() {
  local _t
  _t="$(mktemp "${TMPDIR:-/tmp}/airlift.$$.XXXXXX")" || return 1
  chmod 600 "$_t" 2>/dev/null || true
  printf '%s\n' "$_t"
}

# ---------------------------------------------------------------------------
# marker subcommand
#   airlift_marker <instructions-file> <seq> <timestamp>
# Idempotent upsert of the airlift pointer block.
# ---------------------------------------------------------------------------
airlift_marker() {
  local file="$1"
  local seq="$2"
  local ts="$3"

  if [ -z "$file" ] || [ -z "$seq" ] || [ -z "$ts" ]; then
    echo "ERROR: marker requires <instructions-file> <seq> <timestamp>" >&2
    return 2
  fi

  local start="<!-- airlift:start -->"
  local end="<!-- airlift:end -->"
  local content_line
  content_line="An airlift handoff is available at .airlift/HANDOFF.md (checkpoint ${seq}, ${ts})."

  # Build the canonical block in a temp so we can reuse it for create/append.
  local block_tmp
  block_tmp="$(airlift_mktemp)" || return 1
  {
    printf '%s\n' "$start"
    printf '%s\n' "$content_line"
    printf '%s\n' "Read it before continuing."
    printf '%s\n' "$end"
  } > "$block_tmp"

  # Case 1: file does not exist -> create it containing ONLY the block.
  if [ ! -e "$file" ]; then
    local mkdir_target
    mkdir_target="$(dirname "$file")"
    if [ -n "$mkdir_target" ] && [ ! -d "$mkdir_target" ]; then
      mkdir -p "$mkdir_target" 2>/dev/null || true
    fi
    cp "$block_tmp" "$file" || return 1
    return 0
  fi

  # Detect whether a WHOLE-LINE start marker is present. A line counts as a
  # marker only if, after trimming trailing whitespace, it equals the marker
  # string exactly. This avoids falsely matching prose or code fences that merely
  # MENTION the marker string (e.g. documentation of this very mechanism).
  local has_start has_end
  has_start="$(awk -v s="$start" '
    { line = $0; sub(/[ \t]+$/, "", line); if (line == s) { print "1"; exit } }
  ' "$file" 2>/dev/null)"

  if [ "$has_start" = "1" ]; then
    # A whole-line start marker exists. Require a matching whole-line end marker;
    # without one, replacing would consume everything to EOF. Safety bail: leave
    # the file byte-identical, report the error, return non-zero.
    has_end="$(awk -v e="$end" '
      { line = $0; sub(/[ \t]+$/, "", line); if (line == e) { print "1"; exit } }
    ' "$file" 2>/dev/null)"
    if [ "$has_end" != "1" ]; then
      echo "ERROR: airlift start marker found in $file with no matching end marker; refusing to rewrite (file left unchanged)" >&2
      return 1
    fi

    # Case 2: markers present -> REPLACE content between the whole-line markers
    # in place, leaving every byte outside the pair byte-identical. awk range
    # replace keyed on whole-line equality (trailing whitespace trimmed).
    local out_tmp
    out_tmp="$(airlift_mktemp)" || return 1
    awk -v s="$start" -v e="$end" -v cl="$content_line" '
      BEGIN { inblock = 0 }
      {
        line = $0
        trimmed = line
        sub(/[ \t]+$/, "", trimmed)
        if (inblock == 0 && trimmed == s) {
          # Emit a fresh, normalized block. Replaces the old one entirely.
          print s
          print cl
          print "Read it before continuing."
          print e
          inblock = 1
          next
        }
        if (inblock == 1) {
          if (trimmed == e) {
            inblock = 0
          }
          next
        }
        print line
      }
    ' "$file" > "$out_tmp" || return 1
    # Atomic publish: move the temp into place (the header promises temp-then-mv).
    # The temp is 0600; instruction files are not secret, so restore the typical
    # world-readable mode after the move.
    mv "$out_tmp" "$file" || return 1
    chmod 644 "$file" 2>/dev/null || true
    return 0
  fi

  # Case 3: file exists WITHOUT a whole-line start marker -> APPEND the block at
  # EOF, preceded by exactly one blank line. Prior content stays byte-identical.
  {
    printf '\n'
    cat "$block_tmp"
  } >> "$file" || return 1
  return 0
}

# ---------------------------------------------------------------------------
# Helpers for `write`: best-effort gathering. NEVER fail the run if a source
# is absent.
# ---------------------------------------------------------------------------

# Extract fenced shell blocks that sit near a heading mentioning
# verify/build/test/run from the repo-root CLAUDE.md. Best-effort; prints a
# friendly fallback when nothing is found. Output is plain markdown text.
airlift_extract_verify() {
  local md="$1"
  if [ -z "$md" ] || [ ! -f "$md" ]; then
    echo "_No instruction file found at checkpoint time. Inspect the repository for build/test commands._"
    return 0
  fi
  local out_tmp
  out_tmp="$(airlift_mktemp)" || return 1
  awk '
    BEGIN { armed = 0; infence = 0; emitted = 0 }
    {
      line = $0
      lc = tolower(line)
      # A heading that hints at verification arms capture of the next fence.
      if (line ~ /^#+[[:space:]]/) {
        if (lc ~ /verify|build|test|run/) { armed = 1 } else { armed = 0 }
        next
      }
      if (infence == 0 && line ~ /^[[:space:]]*```/) {
        if (armed == 1) {
          infence = 1
          print "```sh"
          emitted = 1
        }
        next
      }
      if (infence == 1) {
        if (line ~ /^[[:space:]]*```/) {
          infence = 0
          print "```"
          print ""
          next
        }
        print line
      }
    }
    END {
      if (emitted == 0) {
        print "NONE"
      }
    }
  ' "$md" > "$out_tmp" || return 1

  if grep -qx "NONE" "$out_tmp" 2>/dev/null; then
    echo "_No verify/build/test command blocks found in the instruction file. Inspect the repository._"
  else
    cat "$out_tmp"
  fi
  return 0
}

# Extract a few environment notes (Docker-only Go, -tags=dev, etc.) from the
# instruction file. Best-effort; prints a fallback when nothing matches.
airlift_extract_env() {
  local md="$1"
  if [ -z "$md" ] || [ ! -f "$md" ]; then
    echo "_None captured._"
    return 0
  fi
  local out_tmp
  out_tmp="$(airlift_mktemp)" || return 1
  # Pull lines mentioning common environment constraints. Case-insensitive.
  grep -iE 'docker|tags=dev|devcontainer|air |\bgo build\b|environment|requires? ' "$md" 2>/dev/null \
    | grep -ivE '^[[:space:]]*```' \
    | sed -n '1,12p' > "$out_tmp" 2>/dev/null || true
  if [ -s "$out_tmp" ]; then
    while IFS= read -r _ln; do
      printf -- '- %s\n' "$_ln"
    done < "$out_tmp"
  else
    echo "_None captured._"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# write subcommand
# ---------------------------------------------------------------------------
airlift_write() {
  local phase="handoff"
  local note=""
  local instructions_file=""

  while [ $# -gt 0 ]; do
    case "$1" in
      --phase)
        if [ -z "${2:-}" ]; then echo "ERROR: --phase requires a value" >&2; return 2; fi
        phase="$2"; shift 2 ;;
      --note)
        if [ -z "${2:-}" ]; then echo "ERROR: --note requires a value" >&2; return 2; fi
        note="$2"; shift 2 ;;
      --instructions-file)
        if [ -z "${2:-}" ]; then echo "ERROR: --instructions-file requires a value" >&2; return 2; fi
        instructions_file="$2"; shift 2 ;;
      *)
        echo "ERROR: unknown write option '$1'" >&2; return 2 ;;
    esac
  done

  # 1. Repo root.
  local repo_root
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -z "$repo_root" ]; then
    echo "ERROR: not inside a git repository (git rev-parse --show-toplevel failed)" >&2
    return 1
  fi

  local airlift_dir="${repo_root}/.airlift"
  mkdir -p "$airlift_dir" || { echo "ERROR: cannot create $airlift_dir" >&2; return 1; }

  # 2 + 3. Git state and lossless patch capture (NO commit).
  local branch head dirty
  branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  head="$(git -C "$repo_root" rev-parse HEAD 2>/dev/null)"
  [ -n "$branch" ] || branch="unknown"
  [ -n "$head" ] || head="unknown"

  local porcelain
  porcelain="$(git -C "$repo_root" status --porcelain 2>/dev/null)"
  if [ -z "$porcelain" ]; then
    dirty="false"
  else
    dirty="true"
  fi

  # Lossless patch capture. NEVER commit. Two parts:
  #   (a) tracked changes: byte-for-byte `git diff HEAD`.
  #   (b) untracked, non-ignored files: each appended as a standard added-file
  #       diff via `git diff --no-index /dev/null <file>`. `git status --porcelain`
  #       (which drives `dirty`) counts these, but `git diff HEAD` does not -- so
  #       without (b) an untracked file would make dirty=true with an empty patch
  #       and the work would be silently lost on resume.
  # The result is a single `git apply`-able patch with no index mutation.
  local patch_path="${airlift_dir}/uncommitted.patch"
  git -C "$repo_root" diff HEAD > "$patch_path" 2>/dev/null || true

  local untracked_count=0
  local untracked_captured="false"
  # Enumerate untracked, non-ignored files (NUL-delimited for path safety).
  # Process substitution keeps the NUL stream intact: piping into `while read`
  # would run the loop in a subshell and lose the counter; `$(...)` would strip
  # the NUL bytes. `read -d ''` splits on NUL so paths with spaces/newlines are
  # safe. bash 3.2 supports both `read -d ''` and process substitution.
  local _u
  while IFS= read -r -d '' _u; do
    [ -n "$_u" ] || continue
    # `git diff --no-index` exits 1 when files differ -- EXPECTED here, not an
    # error. Swallow the status so it never aborts the capture. Mutates no index.
    git -C "$repo_root" diff --no-index -- /dev/null "$_u" >> "$patch_path" 2>/dev/null || true
    untracked_count=$((untracked_count + 1))
  done < <(git -C "$repo_root" ls-files --others --exclude-standard -z 2>/dev/null)
  if [ "$untracked_count" -gt 0 ]; then
    untracked_captured="true"
  fi

  # 4. Verify commands + env notes from repo-root CLAUDE.md (best-effort).
  local root_md="${repo_root}/CLAUDE.md"
  local verify_block env_block
  if [ -f "$root_md" ]; then
    verify_block="$(airlift_extract_verify "$root_md")"
    env_block="$(airlift_extract_env "$root_md")"
  else
    verify_block="$(airlift_extract_verify "")"
    env_block="$(airlift_extract_env "")"
  fi

  # 5. Fold existing deterministic artifacts (best-effort, guarded globs).
  # Pipeline artifacts and dm-review artifacts collected into two lists.
  local pipeline_list=""
  local dmreview_list=""
  local _p
  # Guard each glob: with no match, the literal pattern is skipped via -e test.
  for _p in \
    "$repo_root"/plans/*/plan.html \
    "$repo_root"/plans/*/manifest.json \
    "$repo_root"/plans/*/receipt.md \
    "$repo_root"/tasks/todo.md; do
    if [ -e "$_p" ]; then
      pipeline_list="${pipeline_list}${_p#$repo_root/}
"
    fi
  done
  for _p in "$repo_root"/todos/*-pending-*.md; do
    if [ -e "$_p" ]; then
      dmreview_list="${dmreview_list}${_p#$repo_root/}
"
    fi
  done

  # 6. Sequence: read prior state.json.seq via python3 if present, else 1.
  local state_path="${airlift_dir}/state.json"
  local seq=1
  if [ -f "$state_path" ]; then
    local prior_seq
    prior_seq="$(AIRLIFT_STATE_PATH="$state_path" python3 - <<'PY' 2>/dev/null
import json, os, sys
p = os.environ.get("AIRLIFT_STATE_PATH", "")
try:
    with open(p) as fh:
        data = json.load(fh)
    s = int(data.get("seq", 0))
    print(s if s > 0 else 0)
except Exception:
    print(0)
PY
)"
    if [ -n "$prior_seq" ] && [ "$prior_seq" -gt 0 ] 2>/dev/null; then
      seq=$((prior_seq + 1))
    fi
  fi

  # Timestamp: ISO 8601 UTC.
  local timestamp
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # Source + targets defaults / overrides.
  local src_harness="${AIRLIFT_SOURCE_HARNESS:-claude-code}"
  local src_model="${AIRLIFT_SOURCE_MODEL:-${AIRLIFT_MODEL:-unknown}}"
  local targets_csv="${AIRLIFT_TARGETS:-claude-code,codex,deepseek,gemini,kiro,opencode}"

  # 6 (cont). Build state.json with python3 (NEVER hand-concatenate JSON).
  # Pass every dynamic value through the environment so embedded quotes/braces
  # in notes or branch names cannot corrupt the document.
  AIRLIFT_SEQ="$seq" \
  AIRLIFT_TIMESTAMP="$timestamp" \
  AIRLIFT_SRC_HARNESS="$src_harness" \
  AIRLIFT_SRC_MODEL="$src_model" \
  AIRLIFT_TARGETS_CSV="$targets_csv" \
  AIRLIFT_BRANCH="$branch" \
  AIRLIFT_HEAD="$head" \
  AIRLIFT_DIRTY="$dirty" \
  AIRLIFT_UNTRACKED_CAPTURED="$untracked_captured" \
  AIRLIFT_UNTRACKED_COUNT="$untracked_count" \
  AIRLIFT_PHASE="$phase" \
  AIRLIFT_NOTE="$note" \
  AIRLIFT_PIPELINE_LIST="$pipeline_list" \
  AIRLIFT_DMREVIEW_LIST="$dmreview_list" \
  AIRLIFT_STATE_OUT="$state_path" \
  python3 - <<'PY' || { echo "ERROR: failed to write state.json" >&2; return 1; }
import json, os

def lines(envname):
    raw = os.environ.get(envname, "")
    return [ln for ln in raw.splitlines() if ln.strip()]

targets = [t.strip() for t in os.environ.get("AIRLIFT_TARGETS_CSV", "").split(",") if t.strip()]

state = {
    "schemaVersion": 1,
    "seq": int(os.environ.get("AIRLIFT_SEQ", "1") or "1"),
    "timestamp": os.environ.get("AIRLIFT_TIMESTAMP", ""),
    "source": {
        "harness": os.environ.get("AIRLIFT_SRC_HARNESS", "claude-code"),
        "model": os.environ.get("AIRLIFT_SRC_MODEL", "unknown"),
    },
    "targets": targets,
    "git": {
        "branch": os.environ.get("AIRLIFT_BRANCH", "unknown"),
        "head": os.environ.get("AIRLIFT_HEAD", "unknown"),
        "dirty": os.environ.get("AIRLIFT_DIRTY", "false") == "true",
        "untrackedCaptured": os.environ.get("AIRLIFT_UNTRACKED_CAPTURED", "false") == "true",
        "untrackedCount": int(os.environ.get("AIRLIFT_UNTRACKED_COUNT", "0") or "0"),
    },
    "phase": os.environ.get("AIRLIFT_PHASE", "handoff"),
    "note": os.environ.get("AIRLIFT_NOTE", ""),
    "artifacts": {
        "handoff": ".airlift/HANDOFF.md",
        "resumePrompt": ".airlift/RESUME_PROMPT.md",
        "patch": ".airlift/uncommitted.patch",
        "pipeline": lines("AIRLIFT_PIPELINE_LIST"),
        "dmReview": lines("AIRLIFT_DMREVIEW_LIST"),
    },
}

with open(os.environ["AIRLIFT_STATE_OUT"], "w") as fh:
    json.dump(state, fh, indent=2)
    fh.write("\n")
PY

  # 7. Render HANDOFF.md + RESUME_PROMPT.md from templates.
  # Resolve the script dir from BASH_SOURCE (not $0): downstream callers invoke
  # this engine through wrappers/symlinks where $0 is the wrapper, not the engine.
  # AIRLIFT_TEMPLATE_DIR overrides the location entirely when set.
  local script_dir tmpl_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
  tmpl_dir="${AIRLIFT_TEMPLATE_DIR:-${script_dir}/templates}"

  local handoff_tmpl="${tmpl_dir}/HANDOFF.md.tmpl"
  local resume_tmpl="${tmpl_dir}/RESUME_PROMPT.md.tmpl"
  if [ ! -f "$handoff_tmpl" ] || [ ! -f "$resume_tmpl" ]; then
    echo "ERROR: templates not found under $tmpl_dir" >&2
    return 1
  fi

  # Dirty-driven note for the rendered HANDOFF. The patch captures tracked
  # changes (`git diff HEAD`) PLUS untracked, non-ignored files, so it is
  # lossless whether the dirt is staged, unstaged, or brand-new files.
  local dirty_note
  if [ "$dirty" = "true" ]; then
    if [ "$untracked_count" -gt 0 ]; then
      dirty_note="dirty (tracked changes plus ${untracked_count} untracked non-ignored file(s) captured in .airlift/uncommitted.patch)"
    else
      dirty_note="dirty (tracked changes captured in .airlift/uncommitted.patch)"
    fi
  else
    dirty_note="clean (no uncommitted changes at checkpoint time; uncommitted.patch is intentionally empty)"
  fi

  # Note text rendered for humans.
  local note_render="$note"
  [ -n "$note_render" ] || note_render="_none_"

  # Artifact list for the HANDOFF body.
  local artifact_render=""
  artifact_render="- .airlift/HANDOFF.md
- .airlift/RESUME_PROMPT.md
- .airlift/state.json
- .airlift/uncommitted.patch"
  if [ -n "$pipeline_list" ]; then
    artifact_render="${artifact_render}
- Pipeline artifacts folded into state.json (artifacts.pipeline)"
  fi
  if [ -n "$dmreview_list" ]; then
    artifact_render="${artifact_render}
- dm-review artifacts folded into state.json (artifacts.dmReview)"
  fi

  # Render via python3 token substitution (literal replace; no regex surprises
  # from values containing & or backslashes the way sed would mangle).
  AIRLIFT_TMPL="$handoff_tmpl" \
  AIRLIFT_OUT="${airlift_dir}/HANDOFF.md" \
  R_SEQ="$seq" \
  R_TIMESTAMP="$timestamp" \
  R_BRANCH="$branch" \
  R_HEAD="$head" \
  R_DIRTY="$dirty_note" \
  R_PHASE="$phase" \
  R_NOTE="$note_render" \
  R_VERIFY="$verify_block" \
  R_ENV="$env_block" \
  R_ARTIFACTS="$artifact_render" \
  python3 - <<'PY' || { echo "ERROR: failed to render HANDOFF.md" >&2; return 1; }
import os, re
with open(os.environ["AIRLIFT_TMPL"]) as fh:
    text = fh.read()
sub = {
    "{{SEQ}}": os.environ.get("R_SEQ", ""),
    "{{TIMESTAMP}}": os.environ.get("R_TIMESTAMP", ""),
    "{{BRANCH}}": os.environ.get("R_BRANCH", ""),
    "{{HEAD}}": os.environ.get("R_HEAD", ""),
    "{{DIRTY}}": os.environ.get("R_DIRTY", ""),
    "{{PHASE}}": os.environ.get("R_PHASE", ""),
    "{{NOTE}}": os.environ.get("R_NOTE", ""),
    "{{VERIFY_COMMANDS}}": os.environ.get("R_VERIFY", ""),
    "{{ENV_NOTES}}": os.environ.get("R_ENV", ""),
    "{{ARTIFACT_LIST}}": os.environ.get("R_ARTIFACTS", ""),
}
# Single-pass substitution. A sequential replace() loop would re-expand a value
# that happened to contain another token (e.g. a note of "{{VERIFY_COMMANDS}}").
# Build one alternation of all tokens and replace via a dict-lookup callback so
# each match is taken from the template's ORIGINAL text exactly once; injected
# values are inserted literally and never re-scanned.
pattern = re.compile("|".join(re.escape(k) for k in sub))
text = pattern.sub(lambda m: sub[m.group(0)], text)
with open(os.environ["AIRLIFT_OUT"], "w") as out:
    out.write(text)
PY

  # RESUME_PROMPT renders ONLY {{HEAD}} -- no harness/source value flows in, so
  # the output contains zero occurrences of any harness brand name.
  AIRLIFT_TMPL="$resume_tmpl" \
  AIRLIFT_OUT="${airlift_dir}/RESUME_PROMPT.md" \
  R_HEAD="$head" \
  python3 - <<'PY' || { echo "ERROR: failed to render RESUME_PROMPT.md" >&2; return 1; }
import os
with open(os.environ["AIRLIFT_TMPL"]) as fh:
    text = fh.read()
text = text.replace("{{HEAD}}", os.environ.get("R_HEAD", ""))
with open(os.environ["AIRLIFT_OUT"], "w") as out:
    out.write(text)
PY

  # 8. Marker upsert into the instruction file (default repo-root CLAUDE.md).
  local target_md
  if [ -n "$instructions_file" ]; then
    case "$instructions_file" in
      /*) target_md="$instructions_file" ;;
      *)  target_md="${repo_root}/${instructions_file}" ;;
    esac
  else
    target_md="${repo_root}/CLAUDE.md"
  fi

  # Scope guard: the marker target must live inside repo_root. An absolute path
  # or a `../` escape would let --instructions-file write outside the repo.
  # Canonicalize the parent dir (it must already exist; the marker create-case
  # mkdir is only meant for in-repo subdirs) and require a repo_root/ prefix.
  local target_parent target_parent_real repo_root_real
  target_parent="$(dirname "$target_md")"
  target_parent_real="$(cd "$target_parent" 2>/dev/null && pwd)"
  repo_root_real="$(cd "$repo_root" 2>/dev/null && pwd)"
  if [ -z "$target_parent_real" ] || [ -z "$repo_root_real" ]; then
    echo "ERROR: cannot resolve instructions-file target directory '$target_parent'" >&2
    return 1
  fi
  case "${target_parent_real}/" in
    "${repo_root_real}/"*) : ;;  # inside repo_root -- allowed
    *)
      echo "ERROR: --instructions-file resolves outside the repository ($target_md); refusing to write" >&2
      return 1 ;;
  esac

  airlift_marker "$target_md" "$seq" "$timestamp" || {
    echo "ERROR: marker upsert failed for $target_md" >&2
    return 1
  }

  echo "airlift: checkpoint ${seq} written to ${airlift_dir} (dirty=${dirty}); marker -> ${target_md}"
  return 0
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
main() {
  local sub="${1:-}"
  if [ -n "$sub" ]; then shift; fi
  case "$sub" in
    write)
      airlift_write "$@" ;;
    marker)
      airlift_marker "$@" ;;
    ""|-h|--help|help)
      cat >&2 <<'USAGE'
airlift-engine.sh -- tier-1 deterministic session-handoff engine

  write [--phase <name>] [--note <text>] [--instructions-file <path>]
        Capture a checkpoint into <repo-root>/.airlift/ and upsert the
        pointer marker into the instruction file (default repo-root CLAUDE.md).

  marker <instructions-file> <seq> <timestamp>
        Idempotent upsert of the pointer marker block only.
USAGE
      [ -z "$sub" ] && return 2 || return 0 ;;
    *)
      echo "ERROR: unknown subcommand '$sub' (expected: write | marker)" >&2
      return 2 ;;
  esac
}

# Source-vs-exec guard: run main only on direct invocation. Register the
# cleanup trap here so an interrupt during a direct run removes temp files,
# without firing on a sourcing caller's shell exit.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  trap airlift_cleanup EXIT INT TERM
  main "$@"
fi
