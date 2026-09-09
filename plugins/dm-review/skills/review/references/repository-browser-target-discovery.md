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

The host-interpreted pass may execute a directly named Make target when it is
the exact status/readiness command or when it delegates a Compose consumer to
Workflow Kernel's Docker creation contract. It does not start an unregistered
raw process. A stopped process target requires the structured
`.dm/ui-review.json` declaration so `ui-review-readiness.sh` can snapshot
cleanup authority before it supervises the start; otherwise report
`dev_server_unavailable` without attempting the process start.

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
- `pre-existing` ownership for a reused target, or `review-created-compose`
  plus the existing Workflow Kernel resource-registry reference and exact
  registry run/node IDs for a Compose resource created by this review.

For a ready repository target, project those fields into the helper's closed
`--repository-evidence-file`: application, physical checkout root, exact commit
and checkout state, one to eight bounded tracked source ranges, up to six exact
attempt records (`kind`, argv, exit, and redacted 8,192-byte output tail), URL
and provenance, ownership, and the registry reference only when it is a
review-created Compose target. The
helper embeds that object in its existing readiness state and rechecks checkout
identity plus a helper-computed content fingerprint before browser
confirmation. Command output tails stay private; the helper's public result
contains only source ranges, attempt kind/exit summaries, provenance, and
ownership. Attempt argv remains private because arguments may carry credentials
even when the command output is redacted.
The repository-derived target URL also stays in private readiness/browser
evidence because a valid local URL may still carry sensitive path or query
material. Public helper results use `targetRef: private-readiness-state`.
Compose ownership remains authoritative in the existing Workflow Kernel
registry. The evidence carries only its safe run-relative registry reference
and exact run/node IDs; it does not duplicate registry contents or process
cleanup argv.

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
an array. Execute status/readiness argv directly from the selected checkout;
route Compose start/rebuild argv through `review-docker-create.md` (including
its scoped repository-wrapper command instrumentation), and do not
execute raw-process starts in this pass. Never turn declaration prose into
`sh -c`. Redact credentials and private endpoint material using the existing
evidence rules.

Run a documented status/readiness command first when one exists. A zero exit
is not enough by itself: interpret its bounded output and declaration to bind
the affected application, selected checkout, source commit, checkout state,
and target identity. Reachability or `curl` alone proves none of those.

If the declared target is stopped or unsuitable for the exact head, reuse a
suitable exact-head target only when the identity fields agree. Otherwise, a
declared Compose consumer may start only through `review-docker-create.md`:
keep any directly linked repository lifecycle wrapper as the caller and
instrument its exact Docker creation boundary as described there; materialize
the exact Compose argv in the Workflow Kernel plan, execute only
the returned label-instrumented creation argv/override, record its observed
before/after inventory, and retain the resulting `resources.jsonl` registry
reference. A stopped raw-process target is not started by this pass; report
`dev_server_unavailable` and require the structured `.dm/ui-review.json`
declaration. Accept a syntactically valid HTTP(S) URL printed by the authorized
Compose creation procedure or its documented follow-up status command; record
`start-output` or `status-output` URL provenance. Do not replace it with an
example port from the runbook.

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
`pre-existing`: do not register, rebuild, stop, or clean it. This
host-interpreted pass never starts a raw process; a stopped process needs the
structured `.dm/ui-review.json` path, whose helper records cleanup before the
start and supervises interruption. For Docker/Compose, load
`review-docker-create.md` before execution; use its labelled creation plan and
registry, retain only `resources.jsonl` (relative to the review state
directory) or `review/resources.jsonl` (relative to the exact run root) in
readiness evidence, then run `review-docker-cleanup.md` on every terminal path.
The readiness helper loads the complete referenced file through Workflow
Kernel's trusted launcher and requires a registered Docker resource with the
complete, record-matching Workflow Kernel ownership label set and a labelled
creation time within Workflow Kernel's five-minute record skew before accepting
`review-created-compose`. Pass the launcher plus the host-retained expected
registry run/node IDs separately to every readiness-helper action; neither the
launcher nor the expected identity is discovered from the evidence. Workflow
Kernel strictly replays the exact existing registry, binds its repository scope,
requires that scope's physical Git root to be the selected checkout, and emits
only a bounded validation result. The helper repeats that validation
before browser confirmation and before emitting any cleanup handoff. An
incomplete or ambiguous ownership declaration blocks the attempt.

Success, command failure, browser failure, analysis failure, and
`SIGINT`/`SIGTERM` all clean only resources positively recorded as created by
this review. Reused resources remain untouched. Never run a cleanup command
for a failed start unless the before/after evidence and existing registry show
that the attempt created the exact resource.

## Authentication and populated cases

Target identity, application authentication, test data, and browser transport
are separate prerequisites. An authenticated empty state proves neither the
required populated cases nor the repaired source. Bind the running artifact to
the exact source snapshot used to build it, including relevant dirty-source
content; a metadata source path plus a reachable URL is insufficient after edits.
A build receipt and unchanged snapshot are usable proof; status output alone
must not be described as exact-commit proof when it does not report a commit.

Try the session's actual T3 tools first. If T3 cannot complete the required
interaction, discover and try an available appropriate host browser transport.
A missing routed browser participant says nothing about host tool availability.
Keep the T3 failure and the chosen fallback in the browser evidence.

An app sign-in failure is `application_authentication_unavailable`, with the
specific missing supported sign-in prerequisite; do not relabel it as a server
or transport failure. Missing mixed-response, abstention-only, open/resolved,
or matched rendered prototype cases are `required_browser_cases_unavailable`.
Use supported setup/UI only on disposable review-owned data. If a consumer has
not implemented position-taking or story setup, name that consumer prerequisite;
do not inject database rows, invent product features, or reset developer data.
These are host evidence diagnoses, not new readiness-helper CLI states.

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
