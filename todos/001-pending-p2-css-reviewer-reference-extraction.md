# P2: Extract Reference Inventories from css-reviewer.md

**Priority:** P2 — Should Fix
**Source:** architecture-reviewer
**Plugin:** live-wires
**File:** plugins/live-wires/agents/review/css-reviewer.md

## Problem

The css-reviewer agent definition embeds ~120 lines of utility class inventory, layout primitives tables, and component tables. This reference data canonically lives in `skills/livewires/layouts.md`, `components.md`, and `utilities.md`. The duplication creates a synchronization risk — when the framework adds new utilities or layout variants, the agent's embedded copy drifts from the skill's reference docs.

## Evidence

- Layout Primitives table (css-reviewer.md ~line 130) duplicates content from `skills/livewires/layouts.md`
- Components table duplicates content from `skills/livewires/components.md`
- Utility class inventory duplicates content from `skills/livewires/utilities.md`
- Already found: `.box` variant list in css-reviewer.md is missing `box-loose` while code-style.md documents it

## Fix

1. Create `skills/livewires/references/class-inventory.md` with the canonical utility/layout/component tables
2. Replace the embedded tables in css-reviewer.md with a reference pointer
3. Or: have the agent instruct itself to read the skill reference files at review time

## Status

- [ ] Not started

---
*From dm-review (Full mode, 2026-03-11)*
