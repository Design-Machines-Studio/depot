# Canonical Reviewer Output Contract

This is the shared execution and output contract for every core dm-review
reviewer. The caller inlines these exact bytes once; agent definitions own only
their domain criteria.

## Exploration checkpoint

- Around 40 tool calls is an exploration checkpoint, not a reason to disappear
  or return nothing.
- At that point, stop new broad exploration and finish a bounded report from
  the available evidence.
- List incomplete files, paths, or checks under `NOT-COVERED:` and list the
  commands actually run, without their output, under `COMMANDS-RUN:`.

## Findings-only output

- Emit one block per supported finding, using exactly these fields:

  ```markdown
  ### [P1|P2|P3] <title>
  - location: <path>:<line-or-stable-anchor>
  - current defect: <observable present failure>
  - evidence: <concrete evidence>
  - impact: <realistic impact>
  - fix: <smallest adequate fix>
  ```

- Keep each field to one sentence where practical and each finding to at most
  100 words.
- A clean reviewer emits only `<agent-name>: clean.` plus `NOT-COVERED:` and
  `COMMANDS-RUN:`.
- Do not add recaps, praise, approvals, methodology narration, generic best
  practices, speculative hardening, optional redesigns, or repeated
  conclusions.
- Never suppress a supported finding for brevity. Every retained P1, P2, and
  P3 remains mandatory repair work.
