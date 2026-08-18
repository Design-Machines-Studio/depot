# Trigger-word scan (0b fallback)

Loaded by `/pipeline` Step 0b only when Step 0a found no explicit markers in the
original prompt. When 0a found markers, this file is never loaded.

Scan the original prompt for explicit creative trigger words: "brainstorm", "explore ideas", "superpowers", "concept", "rethink", "reimagine", "experiment", "try some things", "let's try". Key Requirements involving NEW visual layout decisions, NEW page designs, or significant UI redesigns also count as creative work; routine template changes (adding a column, fixing a label, wiring an existing pattern) do NOT.

If ANY trigger word is present OR the feature involves new design decisions:

1. Invoke `superpowers:brainstorming` BEFORE any pipeline phase, passing the original prompt
2. Wait for completion (design doc written, user approved)
3. Save output to `plans/<feature-slug>/brainstorm.html` (per **Artifact Format**; `visualDecisions` island)
4. Use both the original prompt AND the brainstorming spec as Phase 1 input

This is NOT optional: the brainstorming hard gate ("Do NOT invoke any implementation skill until you have presented a design and the user has approved it") applies because the pipeline IS an implementation skill. "Having a reference pattern to copy" is NOT a reason to skip -- the brainstorm explores whether that pattern is the right choice.

With NO triggers and a purely backend/logic feature, skip to Phase 1 and log: "Phase 0: Creative routing check -- no creative triggers detected, skipping brainstorming."

Mark ledger item 1b complete. Proceed to Phase 1.
