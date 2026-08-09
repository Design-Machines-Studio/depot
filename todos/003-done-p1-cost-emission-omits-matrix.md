---
status: done
priority: p1
issue_id: "003"
tags: [review, workflow-kernel, cost-accounting]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Cost emission omits the matrix

## Problem

The shipped pipeline and dm-review `emit-cost-summary` invocations do not pass
`--matrix`, so the newly added imputation path is never enabled by the workflows
that are meant to produce the three-rail cost table. The synchronized paragraph
only tells an agent to pass the flag; the executable command immediately above
it remains unchanged in all eleven consumers.

## Location

- `plugins/pipeline/skills/pipeline-run/SKILL.md:228` -- terminal emission omits `--matrix`
- `plugins/dm-review/skills/review/SKILL.md:72` -- review emission omits `--matrix`
- `plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md:19` -- generated source covers prose, not the executable invocation

## Evidence

`rg` found eleven `emit-cost-summary` command lines under the pipeline and
dm-review plugins and zero command lines containing `--matrix`. Therefore an
ordinary pipeline or dm-review closeout preserves the old null-cost behavior
despite the new CLI option.

## Fix

1. Put the executable emission command under the same canonical generation
   contract as the explanatory text, or update every authoritative command
   source and add a drift check for the flag.
2. Resolve the matrix from the trusted OpenRouter plugin bundle and pass its
   resolved path to both pipeline and dm-review emission commands.
3. Add a contract test that rejects any generated consumer whose live
   `emit-cost-summary` invocation omits `--matrix`.

## Acceptance Criteria

- [x] All eleven live emission commands pass a trusted resolved matrix path
- [x] The sync check covers the executable command, not only nearby prose
- [x] A workflow-shaped fixture emits at least one imputed subscription cost
- [x] Workflow contracts pass; composition is covered by the chunk verification report

## Resolution

The canonical generator initially owned `--matrix trusted-openrouter-bundle`,
injected it into all eleven executable invocations, and rejected drift in check
mode. That selector was superseded by todo 013: callers now resolve a coherent
installed-plugin asset into `MODEL_MATRIX_ASSET` and pass
`--matrix "$MODEL_MATRIX_ASSET"`; the kernel remains provider-neutral.
