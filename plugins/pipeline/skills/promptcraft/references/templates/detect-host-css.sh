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
#   stylesheet. The ladder matches the four DM stacks (Assembly, Live Wires,
#   Tailwind, Craft) plus a manual override, and falls back cleanly otherwise.
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
#   <link rel="stylesheet" href="..."> tag, or the literal token FALLBACK
#   (caller then inlines baseline.css). Diagnostics go to stderr only.
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent caller-controlled hijack of grep,
#     sed, cat, head.
#   - A .dm-review-css override is read as a single trusted line and emitted
#     verbatim; only the first line is used and surrounding whitespace trimmed.

set -uo pipefail

# SECURITY: fixed PATH so a poisoned caller environment can't hijack our tools.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

emit_link() {
  printf '<link rel="stylesheet" href="%s">\n' "$1"
}

# 5. Manual override wins over autodetection when present.
if [ -f ".dm-review-css" ]; then
  override=$(head -1 ".dm-review-css" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  if [ -n "$override" ]; then
    echo "[detect-host-css] using .dm-review-css override" >&2
    emit_link "$override"
    exit 0
  fi
fi

# 1. Assembly (Go + Templ): compiled CSS served from internal/assets/css/.
if [ -f "go.mod" ] && [ -d "internal/assets/css" ]; then
  echo "[detect-host-css] matched Assembly (go.mod + internal/assets/css/)" >&2
  emit_link "/static/css/assembly.css"
  exit 0
fi

# 2. Live Wires: package.json livewires dep OR the settings layer directory.
if { [ -f "package.json" ] && grep -q '"livewires"' package.json 2>/dev/null; } \
   || [ -d "src/css/0_settings" ]; then
  href="/dist/livewires.css"
  if [ -f "livewires.config.json" ]; then
    configured=$(grep -o '"cssPath"[[:space:]]*:[[:space:]]*"[^"]*"' livewires.config.json 2>/dev/null \
      | head -1 | sed 's/.*:[[:space:]]*"//; s/"$//')
    [ -n "$configured" ] && href="$configured"
  fi
  echo "[detect-host-css] matched Live Wires" >&2
  emit_link "$href"
  exit 0
fi

# 3. Tailwind: a tailwind config plus a built output stylesheet.
for cfg in tailwind.config.js tailwind.config.ts tailwind.config.cjs tailwind.config.mjs; do
  if [ -f "$cfg" ] && [ -f "dist/output.css" ]; then
    echo "[detect-host-css] matched Tailwind ($cfg + dist/output.css)" >&2
    emit_link "/dist/output.css"
    exit 0
  fi
done

# 4. Craft CMS: general config present, conventional site stylesheet.
if [ -f "config/general.php" ]; then
  echo "[detect-host-css] matched Craft CMS (config/general.php)" >&2
  emit_link "/css/site.css"
  exit 0
fi

# 6. Nothing matched — caller inlines baseline.css.
echo "[detect-host-css] no host CSS detected; FALLBACK" >&2
echo "FALLBACK"
exit 0
