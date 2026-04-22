# 011 — P3 — Depot docs convention updates

**Status:** pending
**Severity:** P3
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agents:** dm-review:review:pattern-recognition-specialist, dm-review:review:doc-sync-reviewer

## Findings

### P3-D1 — CLAUDE.md should document references/*.sh convention

`gemini-wrapper.sh` is the depot's first executable script in any `references/` folder. The current CLAUDE.md "Conventions" section says references are descriptively-named Markdown — implying always-Markdown.

**Fix:** Add to CLAUDE.md "Conventions" section:

> Reference files in `references/` are typically Markdown. Executable scripts (`.sh`) are permitted when a skill needs runtime tooling (see `plugins/gemini/skills/gemini-delegate/references/gemini-wrapper.sh` for the established pattern). Scripts must include a header comment block with WHY/WHAT/DEPENDENCIES/USAGE sections, set the executable bit (`chmod +x`), and stay POSIX-portable (bash 3.2+ for macOS compatibility).

### P3-D2 — voice/SKILL.md missing `plugins/` prefix in path reference

`plugins/ghostwriter/skills/voice/SKILL.md:324` references `design-machines/audience/references/language-card.md` — missing the `plugins/` prefix. Other depot files use the full `plugins/<plugin>/skills/<skill>/references/<file>` form.

**Fix:** Normalize to `plugins/design-machines/skills/audience/references/language-card.md`.

### P3-D3 — orchestration-patterns.md missing Soft Cross-Skill Companions pattern

The audience skill creates a many-to-many cross-skill reference pattern (audience ↔ strategy ↔ governance ↔ ghostwriter:voice ↔ ghostwriter:social-media), all soft links via SKILL.md text rather than hard `pluginDependencies`. This may constitute a sixth orchestration pattern.

**Fix:** Add a "Soft Cross-Skill Companions" section to `docs/orchestration-patterns.md` documenting the pattern: skills that reference each other via SKILL.md "Companion Skills" sections without declaring hard `pluginDependencies`. Note when this pattern is appropriate (cross-references that enrich behavior without being hard requirements).

## Acceptance

- [ ] CLAUDE.md Conventions section includes references/*.sh guidance
- [ ] voice/SKILL.md uses full `plugins/...` path
- [ ] docs/orchestration-patterns.md has Soft Cross-Skill Companions section
