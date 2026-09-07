# Repository browser-target discovery

Load this host contract only after the ordinary UI target/evidence choices have
failed to supply usable rendered evidence. It lets dm-review use an existing
repository author loop without guessing a port or requiring a new checked-in
declaration. It does not extend `ui-review-readiness.sh` into a runbook parser.

## Entry and precedence

Keep the shared readiness order intact:

1. explicit invocation URL;
2. attached automation-capable T3 preview and its current URL;
3. valid tracked `.dm/ui-review.json`;
4. accepted exact-head browser packet reuse; then
5. this bounded repository discovery pass.

A present higher-precedence source that is malformed, ambiguous, unsafe, or
actually fails does not authorize blind fallback. Preserve its precise failure
and required repair. Use repository discovery after a higher-precedence source
is absent or after rejected stale/mismatched packet evidence leaves no usable
target. A repository-discovered URL has
`targetSource: repository-declaration`; after host validation, pass the bounded
private evidence file to the readiness helper with that source. Do not also
pass `--target-url`, pass it as `explicit`, describe it as user-supplied, or
imply that the user started it.

Full, quick, and standalone visual entry points all use this same pass. An
enclosing Pipeline final review passes its exact packet through the shared
contract; if packet validation rejects it, the nested dm-review may continue to
this pass without Pipeline inventing a separate discovery ladder.

## Closed inspection boundary

The host, not a generalized parser, interprets human-authored declarations.
Inspect only these files in the selected checkout:

- root `AGENTS.md` and root `CLAUDE.md` that apply to the current checkout;
- a development runbook directly named by one of those two root files;
- the relevant checked-in `Makefile` target and Compose service/configuration
  directly named by an accepted declaration;
- `tests/ux/verification.json`, when present; and
- a browser handoff directly named by one of the accepted sources above.

Do not recursively search documentation, inspect package scripts by
convention, scan processes or localhost, try common ports, or synthesize a
command from project type. An example command, example port, supported engine
or viewport, production URL, deployment URL, and prose that merely says a dev
server exists are context, not declarations.

An accepted declaration must identify all of:

- the affected application or Compose consumer;
- the selected checkout/worktree that supplies its source;
- either a suitable current target URL or an exact status/readiness command
  that can report it;
- an exact start or rebuild procedure when the target may be stopped; and
- the ownership-safe cleanup procedure for every resource that procedure may
  create.

The start procedure is optional only when the declaration explicitly says the
target must already be running. A missing application, checkout binding,
status identity, start command, or cleanup/ownership declaration is an
incomplete declaration, not permission to guess.

## Host execution and evidence

Record discovery in dm-review's existing private readiness evidence. Do not
create a second durable report or a new checked-in configuration file. Retain:

- bounded repository-relative source path plus one-based start/end lines for
  every accepted declaration;
- the exact argv array for each status/readiness, start/rebuild, and cleanup
  command considered or attempted;
- exit status and redacted final 8,192 UTF-8 bytes of stdout/stderr for every
  attempted command;
- the selected application/consumer, physical checkout root, `git rev-parse
  HEAD`, and clean/dirty checkout state;
- the exact target URL and whether it came from declaration text, status
  output, or start/rebuild output; and
- `pre-existing` or the existing resource-registry reference for every
  relevant process/Compose resource.

For a ready process target, project those fields into the helper's closed
`--repository-evidence-file`: application, physical checkout root, exact commit
and checkout state, one to eight bounded tracked source ranges, up to six exact
attempt records (`kind`, argv, exit, and redacted 8,192-byte output tail), URL
and provenance, ownership, and cleanup argv/timeout when review-created. The
helper embeds that object in its existing readiness state and rechecks checkout
identity plus a helper-computed content fingerprint before browser
confirmation. Command output tails stay private; the helper's public result
contains only source ranges, argv/exit summaries, provenance, and ownership.
The repository-derived target URL also stays in private readiness/browser
evidence because a valid local URL may still carry sensitive path or query
material. Public helper results use `targetRef: private-readiness-state`.
Compose ownership remains in the existing Workflow Kernel registry; do not
duplicate it in this process input.

Redaction happens before the host writes the private evidence. Remove request
authorization, bearer material, cookies, API keys, passwords, client secrets,
access tokens, private keys, and URL userinfo. The helper rejects those common
secret shapes, limits each output tail to 8,192 characters, and caps all tails
at 24,576 characters; rejection is a backstop, not a replacement for host
redaction.

Ordinary dirty root checkouts are supported because the helper fingerprints
their status, tracked diff, and untracked content. Dirty initialized submodules
are rejected: the parent repository's dirty marker cannot bind changing nested
content without a second snapshot contract.

Source lines are evidence locators, not executable authority. Preserve argv as
an array and execute it directly from the selected checkout; never turn
declaration prose into `sh -c`. Redact credentials and private endpoint
material using the existing evidence rules.

Run a documented status/readiness command first when one exists. A zero exit
is not enough by itself: interpret its bounded output and declaration to bind
the affected application, selected checkout, source commit, checkout state,
and target identity. Reachability or `curl` alone proves none of those.

If the declared target is stopped or unsuitable for the exact head, reuse a
suitable exact-head target only when the identity fields agree. Otherwise
attempt the one documented start/rebuild procedure from the selected checkout.
Accept a syntactically valid HTTP(S) URL printed by that exact procedure or its
documented follow-up status command; record `start-output` or `status-output`
URL provenance. Do not replace it with an example port from the runbook.

Before browser navigation, confirm again that:

1. the selected checkout is still the recorded physical root and state;
2. its current commit is the recorded commit;
3. status/readiness identifies the selected application/consumer and that
   checkout/commit; and
4. the exact URL belongs to that identified target.

Only then may host-owned T3-first automation navigate and create exact-head
browser proof. Browser transport failure remains
`browser_transport_unavailable`; it never changes a successful dev-server
attempt into `dev_server_unavailable`.

## Ownership and cleanup

Inventory before creation. A suitable target that was already running is
`pre-existing`: do not register, rebuild, stop, or clean it. Before attempting
a process start, record its exact declared cleanup argv in the review-owned
state so interruption can use that immutable snapshot. For Docker/Compose,
load `review-docker-create.md` before execution; use its labelled creation plan
and registry, then `review-docker-cleanup.md` on every terminal path. An
incomplete or ambiguous ownership declaration blocks the attempt.

Success, command failure, browser failure, analysis failure, and
`SIGINT`/`SIGTERM` all clean only resources positively recorded as created by
this review. Reused resources remain untouched. Never run a cleanup command
for a failed start unless the before/after evidence and existing registry show
that the attempt created the exact resource.

## Outcomes

- No repository-owned declaration in the closed inspection boundary:
  `visual_target_unavailable`, with bounded inspected-source evidence.
- A declared status/start/readiness command is actually attempted and fails:
  `dev_server_unavailable`, with source path/lines, exact attempted argv, exit
  status, and one bounded failure reason.
- A declaration is incomplete, conflicting, unsafe, or cannot bind the
  selected checkout/application/ownership: `dev_server_unavailable`, naming
  the exact missing prerequisite; do not execute an unsafe procedure or fall
  through to guesses.
- Application identity is sound but local browser navigation cannot run:
  `browser_transport_unavailable`.

These remain one aggregate rendered-coverage gap. Source-capable UI analysis
continues in labelled `source-only` mode; visual-browser is `NOT RUN`. Required
rendering keeps the review `REVIEW INCOMPLETE`. Never claim an unavailable or
skipped case passed.
