# 007 — P2 — Missing pluginDependencies declarations + doc-sync gaps

**Status:** pending
**Severity:** P2 (should fix before merge or in immediate follow-up)
**Source:** dm-review on feature/depot-audience-rollout, 2026-04-22
**Reporting agents:** dm-review:review:architecture-reviewer, dm-review:review:doc-sync-reviewer

## Problem

The rollout introduced cross-plugin file references without declaring the dependencies. Per CLAUDE.md "Plugin Dependencies" section, hard cross-plugin references should be declared in `plugin.json`.

Plus three doc-sync gaps that would cause confusion or skill-loading misses.

## Findings

### A-1 — design-machines should declare council dependency

`strategy/SKILL.md:188` references `plugins/council/skills/governance/references/plain-language-glossary.md` as "Source of truth." Hard dependency.

`audience/SKILL.md:56` lists `council:governance` and `council:decolonial-language` as Companion Skills.

Add to `plugins/design-machines/.claude-plugin/plugin.json`:

```json
"pluginDependencies": {
  "council": ">=1.9.0"
}
```

### A-2 — ghostwriter should declare optional design-machines dependency

`voice/SKILL.md:319` (Audience Awareness section) directs reader to `design-machines:audience` and references `design-machines/audience/references/language-card.md`.

Voice still functions without audience-awareness, just less well. So this is optional:

```json
"optionalPluginDependencies": {
  "design-machines": ">=1.5.0"
}
```

### D-1 — social-media/SKILL.md doesn't reference 3 new block files

`enforcement-angle-blocks.md`, `plain-language-blocks.md`, `survival-reframe-blocks.md` were added under social-media/references/, but the SKILL.md was NOT updated to mention them. They sit dark — Claude has no signal to load them.

Add a "Cornerstone Blocks" section to `plugins/ghostwriter/skills/social-media/SKILL.md` listing the three files with load-trigger notes.

### D-2 — strategy/SKILL.md Companion Skills table doesn't include audience

audience/SKILL.md correctly lists strategy as companion. Strategy/SKILL.md does not list audience. Bidirectional inconsistency.

Add an `audience` row to strategy SKILL.md Companion Skills table.

### D-3 — docs/dependency-graph.md stale

Pre-existing drift (missing pipeline and gemini plugin nodes), not caused by this rollout but a natural moment to fix. Run:

```bash
./tools/check-dependencies.sh --graph > docs/dependency-graph.md
```

After A-1 and A-2 are applied, regenerate so the new dependencies appear.

## Fix order

D-1 and D-2 (docs sync) are quick wins. A-1 and A-2 (declare dependencies) require a careful version-floor decision. D-3 (regenerate graph) runs after A-1 + A-2.

## Acceptance

- [ ] design-machines plugin.json declares council ≥1.9.0 in pluginDependencies
- [ ] ghostwriter plugin.json declares design-machines ≥1.5.0 in optionalPluginDependencies
- [ ] social-media/SKILL.md mentions the 3 cornerstone block files
- [ ] strategy/SKILL.md Companion Skills table includes audience
- [ ] dependency-graph.md regenerated; includes new edges
- [ ] `./tools/check-dependencies.sh` returns 0
