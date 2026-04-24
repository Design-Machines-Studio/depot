<!--
Behavioural principles below paraphrase Andrej Karpathy's observations on LLM coding
pitfalls (https://x.com/karpathy/status/2015883857489522876).
-->

# CLAUDE.md

This file tells Claude Code how to work in this repository. Read it at the start of every session.

## How to Work Here

### 1. Think before coding

Don't assume silently. When the task admits more than one reasonable interpretation, name them before touching code and choose one with a stated rationale. If you are confused, say what is confusing and ask — don't paper over it with plausible-looking output. A clarifying question up front is cheaper than a rewrite after.

### 2. Simplicity first

Write the minimum code that satisfies the request. No speculative features, no abstractions for single-use code, no configurability nobody asked for, no error handling for scenarios that cannot occur. If a senior engineer would call the result overcomplicated, it is overcomplicated — rewrite it shorter.

### 3. Surgical changes

Every line you change must trace directly to the request. Don't improve adjacent code, don't reformat, don't rewrite comments, don't tighten types on lines you weren't already touching. If you notice unrelated issues in a file you are editing, list them at the end of your response as "Noted, not fixed" — do not include them in the diff.

### 4. Goal-driven execution

Turn every task into a verifiable outcome before you start. "Make it work" is not a goal; "the login form accepts valid credentials and rejects invalid ones, with passing tests" is. State the success criterion, implement, verify. Loop only against a concrete criterion, never against vibes.

## Design Machines Conventions

### Live Wires CSS

This project uses the [Live Wires CSS framework](https://github.com/Design-Machines-Studio/live-wires) — cascade layers, baseline rhythm tokens, container queries, editorial-first primitives. Use the existing primitives and utilities. Do not invent new class names when a token or primitive already covers the need.

### Zero-deferral review

When a code review produces findings, fix every finding before merge — P1, P2, and P3. The `--allow-defer-p3` opt-in needs written justification and a tracking ID per item. "Good enough" is not a valid reason.

### Brainstorm trigger

Route creative UI and design work through the brainstorming skill before implementation. Triggers include phrases like "brainstorm," "explore ideas," "reimagine," "let's try," and any new visual layout or page design decision. Routine changes — adding a column, fixing a label, wiring an existing pattern — skip brainstorming.

### Install the depot

Most DM tooling lives in the depot marketplace. Install it in Claude Code:

```shell
/plugin marketplace add Design-Machines-Studio/depot
/plugin install <plugin-name>@depot
```

Relevant plugins for this project: `dm-review` (code review orchestrator), `live-wires` (CSS framework skill), `pipeline` (feature development pipeline), and the accessibility reviewers under `accessibility-compliance`.

## Project-Specific Rules

<!-- Replace this section with rules unique to this repository: build commands,
     deployment targets, naming conventions, architectural invariants, etc.
     Keep it short — one line per rule where possible. -->
