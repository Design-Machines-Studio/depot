# Step 5.5: coverage gaps

Loaded by `review-consolidator` only when at least one selected lane failed,
declined, timed out, was unavailable, or returned incomplete required coverage.
A run in which every required lane completed never loads this file.

### Step 5.5: Coverage Gaps

Add a **Coverage Gaps** section (immediately below the agent summary table) that lists every lane that did NOT achieve full coverage:

- Each agent's `NOT-COVERED:` lines (budget-capped paths/checks), attributed to the agent.
- Every dead/absent agent (see Dead / Missing Agent Handling), with what it was responsible for.

If there are no gaps, state `Coverage Gaps: none -- all lanes completed within budget.` An empty or omitted section must never be used to imply full coverage; absence of the section is treated as an authoring error, not as "clean".

Return the provisional report body only after this Coverage Gaps section is
complete.
