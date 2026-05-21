#!/usr/bin/env bash
#
# detect-host-css.sh: Resolve the target project's compiled stylesheet so a
# pipeline HTML artifact can <link> to it and render in the project's own skin.
#
# WHY THIS EXISTS:
#   Pipeline planning artifacts (assessment/research/brainstorm/plan) are now
#   self-contained HTML. To look native they link the host project's CSS rather
#   than shipping bespoke styles. Each host stack exposes its compiled CSS at a
#   different path; this encodes the detection ladder in one place.
#
# WHAT THIS FIXES:
#   Without detection every artifact would hardcode a path or ship a generic
#   stylesheet. The script resolves the host's COMPILED CSS as it actually sits
#   on disk (across the DM stacks: Assembly, Live Wires, Tailwind, Craft) plus a
#   manual override, and falls back cleanly otherwise.
#
#   It emits a RELATIVE href from the artifact's own location, NOT a
#   site-absolute path. Pipeline artifacts are opened directly from disk
#   (file://) for review with no dev server, so /dist/main.css would never
#   resolve. The earlier version guessed per-stack site-absolute paths (e.g.
#   /dist/livewires.css) that both pointed at the wrong file and failed to load
#   locally -- artifacts rendered unstyled. A relative href works three ways:
#   double-clicked file://, served over a dev server, and headless screenshots.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default)
#   - POSIX grep, sed, head, cat
#
# USAGE:
#   bash detect-host-css.sh            # run from the target project root ($PWD)
#   HOST_CSS_LINK=$(bash detect-host-css.sh 2>/dev/null || echo FALLBACK)
#
#   Prints exactly one line to stdout: either a complete
#   <link rel="stylesheet" href="../../..."> tag, or the literal token FALLBACK
#   (caller then inlines baseline.css). Diagnostics go to stderr only.
#   Set ARTIFACT_DEPTH=3 for epic plans nested one level deeper.
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent caller-controlled hijack of grep,
#     sed, cat, head.
#   - A .dm-review-css override (and a livewires.config.json cssPath) is read from
#     a project file and emitted into an href="" attribute of the generated
#     artifact, which a human opens in a browser. emit_link refuses any value
#     containing attribute-breakout characters (" < > or a newline) so a crafted
#     project file cannot inject markup. Only the first line of the override is
#     used and surrounding whitespace is trimmed.

set -uo pipefail

# SECURITY: fixed PATH so a poisoned caller environment can't hijack our tools.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# Emit a <link> tag, but refuse paths that could break out of the href=""
# attribute and inject markup into the artifact. On rejection, returns non-zero
# so the caller falls through to the next detection rung (and ultimately
# FALLBACK) instead of emitting an empty/broken tag.
emit_link() {
  case "$1" in
    *'"'* | *'<'* | *'>'* | *$'\n'* | *$'\r'*)
      echo "[detect-host-css] SECURITY: refusing CSS path with unsafe characters: $1" >&2
      return 1
      ;;
  esac
  printf '<link rel="stylesheet" href="%s">\n' "$1"
}

# Resolve a repo-root-relative CSS path to a path that loads from the artifact's
# own location. Artifacts live at a fixed depth under the project root:
#   plans/<slug>/<kind>.html        -> depth 2 (default)
#   plans/<epic>/<sub>/<kind>.html  -> depth 3 (set ARTIFACT_DEPTH=3)
# A relative href ("../../public/dist/main.css") beats both a site-absolute path
# (/dist/main.css never resolves under file://) and an absolute file:// URL
# (breaks when the repo moves, and is blocked by automated browsers). Relative
# works three ways: double-clicked file://, served over a dev server (http), and
# headless screenshot tooling. Spaces are percent-encoded for safety.
ARTIFACT_DEPTH="${ARTIFACT_DEPTH:-2}"
rel_href() {
  prefix=""
  i=0
  while [ "$i" -lt "$ARTIFACT_DEPTH" ]; do
    prefix="../$prefix"
    i=$((i + 1))
  done
  printf '%s' "$prefix$1" | sed 's/ /%20/g'
}

# 1. Manual override wins over autodetection when present. A relative path that
#    exists on disk is resolved to file://; an absolute URL is emitted verbatim.
if [ -f ".dm-review-css" ]; then
  override=$(head -1 ".dm-review-css" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  if [ -n "$override" ]; then
    echo "[detect-host-css] using .dm-review-css override" >&2
    case "$override" in
      http://* | https://* | file://* | /*) emit_link "$override" && exit 0 ;;
      *) [ -f "$override" ] && emit_link "$(rel_href "$override")" && exit 0
         emit_link "$override" && exit 0 ;;
    esac
  fi
fi

# 2. Compiled-CSS disk scan. Detection by what is ACTUALLY built on disk, not by
#    guessing a stack's conventional URL. First real file wins; emit file://.
#    Covers Live Wires / DM (public/dist/main.css with ITCSS src/css/), the
#    assembly-baseplate bundle, Tailwind output, and Craft site CSS. The stack
#    label is for the log line only -- the file's existence is the real test.
for built in \
  public/dist/main.css \
  public/dist/livewires.css \
  dist/main.css \
  dist/livewires.css \
  public/css/main.css \
  internal/assets/css/dist/app.css \
  static/css/assembly.css \
  dist/output.css \
  public/build/app.css \
  web/dist/site.css \
  web/css/site.css ; do
  if [ -f "$built" ]; then
    echo "[detect-host-css] matched compiled CSS on disk: $built" >&2
    emit_link "$(rel_href "$built")" && exit 0
  fi
done

# 3. Live Wires source present but not yet built: tell the operator to compile,
#    then FALLBACK so the artifact still renders with baseline.css meanwhile.
if [ -d "src/css" ] && { [ -d "src/css/0_config" ] || [ -d "src/css/0_settings" ] || [ -d "src/css/1_tokens" ]; }; then
  echo "[detect-host-css] Live Wires source found (src/css/) but no compiled bundle on disk; run the CSS build (e.g. npm run build) so artifacts can link it. FALLBACK for now." >&2
fi

# 4. livewires.config.json may name a non-standard compiled path.
if [ -f "livewires.config.json" ]; then
  configured=$(grep -o '"cssPath"[[:space:]]*:[[:space:]]*"[^"]*"' livewires.config.json 2>/dev/null \
    | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
  if [ -n "$configured" ] && [ -f "$configured" ]; then
    echo "[detect-host-css] matched livewires.config.json cssPath: $configured" >&2
    emit_link "$(rel_href "$configured")" && exit 0
  fi
fi

# 5. Nothing built on disk -- caller inlines baseline.css.
echo "[detect-host-css] no compiled host CSS detected; FALLBACK" >&2
echo "FALLBACK"
exit 0
