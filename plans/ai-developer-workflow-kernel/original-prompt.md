# Original Prompt

## User Input

Initial request:

> Can you read this transcript and synthesize the content? How does it line up with our own pipeline and dm-review systems? Are there any good insights we can extract and improve our systems with?

Transcript source:

`/Users/trav/.codex/attachments/aa418aff-892c-464a-aedf-8e3d3813d747/pasted-text.txt`

Implementation request:

> Let's implement all of this. Use pipeline or whatever you recommend is our best approach to capturing all of these things.

The accepted scope refers to the complete improvement set synthesized from the transcript:

1. Introduce a shared workflow run-state and event schema for pipeline and dm-review.
2. Extract deterministic workflow control for transitions, retries, dependency readiness, provider fallback, evidence persistence, cleanup, and gates.
3. Add executable transition tests and failure-injection scenarios.
4. Preserve builder sessions across deterministic validation failures where the host supports resumable agents.
5. Route top-level workflow classes such as chore, bug, feature, hotfix, security, investigation, and migration.
6. Add a declared isolation abstraction covering worktrees, sequential branches, containers, and remote sandboxes.
7. Make human gates risk- and workflow-aware without weakening sensitive-path guarantees.
8. Extend run economics into node- and provider-level reliability calibration.
9. Preserve compatibility with current Markdown contracts, generated Codex shims, Claude-first canonical sources, zero-deferral review, and repository-cleanup guarantees.
10. Keep policy and expertise in Markdown while moving repeatable control-flow mechanics into testable code.

## Date

2026-07-14

## Key Requirements Extracted

1. Deliver the full improvement set rather than a single isolated recommendation.
2. Use the literal Depot pipeline workflow, including its creative-design, assessment, research, planning, adversarial-review, execution, dm-review, verification, and cleanup gates.
3. Decompose the work into safe, testable stages with backward compatibility for existing pipeline and dm-review users.
4. Produce an executable control plane rather than adding more orchestration prose alone.
5. Preserve cross-host Claude and Codex behavior, provider-routing security boundaries, evidence receipts, and honest degradation.
6. Validate workflow behavior through transition and failure-injection tests, not only textual contract checks.
7. Provide a clean feature branch with complete requirements evidence before delivery.

## Iteration 1 Feedback

The user approved these architectural decisions during brainstorming:

1. Use an additive, adapter-first kernel rather than an immediate rewrite.
2. Implement the kernel with the Python standard library and no new build system.
3. Launch in shadow mode; preserve the current Markdown orchestrators as authoritative until parity tests pass.
4. Keep this epic repo-local; defer GitHub, Notion, Slack, and other external ticket-ingestion integrations.
5. Treat Docker containers, networks, and volumes as owned cleanup resources.
6. Label all Depot-managed Docker resources and automatically remove labeled stale resources older than 24 hours.
7. Discover and run project UX personas as a blocking UI/integration verification layer when a project declares them.
8. On browser tooling failure, capture evidence, quit and restart the primary testing browser, retry with a different browser engine, and stop for human assistance if verification remains unavailable.

## Iteration 2 Feedback

> docker clean can happen at the end of the chunk phase during repo cleanup

This makes the existing per-chunk repository cleanup boundary the primary
Docker cleanup point. Chunk-owned resources are removed after that chunk's
validation, review, evidence, and merge disposition complete. Explicitly
run-shared resources remain until their last dependent completes, and terminal
cleanup performs a reconciliation sweep.
