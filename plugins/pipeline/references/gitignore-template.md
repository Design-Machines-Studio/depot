# Gitignore Template for Downstream Repos

Canonical `.gitignore` entries that pipeline and dm-review plugins require in downstream repos. The execution-orchestrator's Step 0d enforces these automatically.

## Required Entries

```gitignore
# Pipeline ephemeral + run-scoped artifacts (Tier 1 + 2)
plans/*/baselines/
plans/*/baselines-pre-fix/
plans/*/baselines-post-fix/
plans/*/screenshots/
plans/*/prompts/
plans/*/manifest.json
plans/*/brainstorm.md
.worktrees/

# dm-review artifacts
.claude/ux-review/
todos/
```

## What Is NOT Ignored

Feature-scoped files (Tier 3) inside `plans/<feature>/` remain trackable:

- `original-prompt.md` — user's verbatim input
- `assessment.md` — current state report
- `research.md` — research findings
- `plan.md` — implementation plan
- `final-requirements-crosscheck.md` — delivery proof
- `receipt.md` — post-cleanup summary

These files are available for the user to commit if they choose. They are not committed automatically.

## Enforcement Logic

Step 0d of the execution-orchestrator runs this before any file writes:

```bash
ENTRIES=(
  'plans/*/baselines/'
  'plans/*/baselines-pre-fix/'
  'plans/*/baselines-post-fix/'
  'plans/*/screenshots/'
  'plans/*/prompts/'
  'plans/*/manifest.json'
  'plans/*/brainstorm.md'
  '.worktrees/'
  '.claude/ux-review/'
  'todos/'
)
ADDED=0
for ENTRY in "${ENTRIES[@]}"; do
  grep -qxF "$ENTRY" .gitignore 2>/dev/null || { echo "$ENTRY" >> .gitignore; ADDED=$((ADDED+1)); }
done
if [ "$ADDED" -gt 0 ]; then
  git add .gitignore && git commit -m "chore: add depot plugin artifact entries to .gitignore"
fi
```

This is idempotent — safe to run on repos that already have the entries.
