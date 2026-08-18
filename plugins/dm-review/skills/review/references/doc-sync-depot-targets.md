# Depot plugin documentation targets

Loaded by `doc-sync-reviewer` only when the diff under review is inside the
depot marketplace itself. Reviews of any other project never load this file.

### Depot Plugin Docs (when reviewing depot plugins)
- `SKILL.md` -- Skill definitions (must match actual behavior)
- `references/*.md` -- Reference material (must match actual patterns)
- `agents/**/*.md` -- Agent definitions (must match actual capabilities)
- `.claude-plugin/plugin.json` -- Version must be bumped on changes
