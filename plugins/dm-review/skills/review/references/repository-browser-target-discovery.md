# Repository browser-target discovery

Load this host contract before choosing a browser target. The default for a
project with an established review domain is its canonical repo folder with
the feature branch checked out, reviewed through that existing domain. This
uses the existing author loop without requiring a new environment or checked-in
declaration. It does not extend `ui-review-readiness.sh` into a runbook parser.

## Entry and precedence

Keep the shared readiness order intact:

1. explicit invocation target override, bound to the intended app and source;
2. the established project domain and canonical checkout from current user
   context or the bounded repository discovery below;
3. valid tracked `.dm/ui-review.json` when no established target is declared;
4. accepted exact-head browser packet reuse; then
5. an attached automation-capable T3 preview whose application and source
   identity the host has verified. An attached tab alone is not target proof.

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

## Established project checkout and domain

For Design Machines projects, resolve the project code from current context or
root instructions. The [Project Codes catalog](https://app.notion.com/p/gertz/2f7d87938808802888b4c184d4d3cf62?v=305d8793880880129530000ce06e58cc&source=copy_link)
is a lookup fallback: `DM-006/WORKS` maps to `dm006.asmbly.app`, for example.
Do not require Notion when the code is already known. The code identifies the
domain; verify its actual repo/service binding locally before using it. Do not
infer that a production/customer deployment is a branch-switchable review app.

1. Resolve the canonical physical repo folder, remote identity, project domain,
   feature branch and exact intended commit. Read its current branch, status,
   worktree registrations, and the documented service/build commands. Capture
   the original branch/head for handoff. Source-analysis worktrees do not
   automatically become browser environments.
2. Check out the feature branch in that canonical folder when it is clean and
   available for this work. This ordinary checkout and the documented local
   rebuild are part of authorized implementation/review; do not ask again.
   If it already holds this run's edits, preserve them and bind evidence to that
   source snapshot. If another run owns it, unrelated changes would be
   displaced, name the concrete collision and coordinate a safe handoff before
   switching. If the feature branch is checked out in an implementation
   worktree, a normal `git checkout --detach <exact-committed-head>` in the clean,
   free serving checkout is acceptable; record detached HEAD honestly. Never stash/reset others' work, force
   duplicate branch checkout, or silently substitute a fresh harness.
3. Use the project's existing build/restart or Fixture composition command to
   serve that source through the same domain, service and data. Rebuild compiled
   Go/Templ/CSS/JS as documented; changing Git HEAD alone does not refresh a
   running binary. Verify relevant dependency/source bindings for a Fixture's
   existing Baseplate consumer. No domain, DNS, Caddy, tunnel, ports, environment
   files, or Compose topology changes are authorized by an ordinary review.
4. This is a maintained developer instance, not review-owned infrastructure.
   Its documented rebuild/restart may replace its application container; retain
   its existing service identity, networks, volumes, data and configuration.
   Record the rebuild and source evidence as `pre-existing`, with no review
   cleanup argv or ownership adoption. Do not run reset/seed/wipe or automatic
   migrations that would make switching back unsafe; name that concrete
   prerequisite if the documented restart would do so. New isolated resources
   still require `review-docker-create.md`; maintenance cannot be used to evade
   that creation contract.
5. Navigate the established domain with the available host browser, using T3
   first when supported. Verify the served artifact and assets against the
   intended source and exercise the selected cases. Bind helper evidence to the
   actual serving checkout, not merely the worktree used for source analysis.
   Record domain, source branch/head, build proof and actual observations.
6. Serialize use of a shared review instance. Leave the reviewed feature branch
   selected for the operator unless an earlier agreed handoff requires a
   restore; a restore also needs the documented rebuild. Never clean up or
   repoint the established instance as if it were a disposable review resource.

An isolated browser environment is an exception requiring a concrete testing
need or explicit user direction, such as simultaneous Federation peers. A
worktree, a convenient attached tab, or generic reviewer isolation is not that
need. Record why the established instance cannot cover the selected case and
use the existing isolated creation/cleanup contracts only for that exception.
Ordinary isolated unit-test containers are unaffected by this browser default.

## Closed inspection boundary

The host, not a generalized parser, interprets human-authored declarations.
Current user-provided targets and project mappings also apply. Repository
evidence still uses tracked source ranges for the local binding and author
loop; a catalog entry alone is not serving-source proof. Never relabel a
catalog-derived target as an explicit invocation URL.
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

The established-instance maintenance path above may execute its documented
rebuild/restart without adopting cleanup ownership. For new resources, the
host-interpreted pass may execute a directly named Make target when it is
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
route new isolated Compose start/rebuild argv through `review-docker-create.md` (including
its scoped repository-wrapper command instrumentation), and do not
execute raw-process starts in this pass. Never turn declaration prose into
`sh -c`. Redact credentials and private endpoint material using the existing
evidence rules.

Run a documented status/readiness command first when one exists. A zero exit
is not enough by itself: interpret its bounded output and declaration to bind
the affected application, selected checkout, source commit, checkout state,
and target identity. Reachability or `curl` alone proves none of those.

For a maintained instance, first apply the established-checkout procedure above.
The following creation path applies only to a justified isolated target.
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
`pre-existing`: do not register or clean it. Rebuild/restart only through the
established-checkout procedure when required to serve the reviewed source. This
host-interpreted pass never starts a raw process; a stopped process needs the
structured `.dm/ui-review.json` path, whose helper records cleanup before the
start and supervises interruption. For new isolated Docker/Compose resources, load
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
this review. Reused resources remain retained. Never run a cleanup command
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
