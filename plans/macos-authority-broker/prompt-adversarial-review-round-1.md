# Prompt adversarial review — round 1

Verdict: **REVISE**

Review scope: plan revision 8, generated M0/M1 manifest, six manifest-referenced prompts, and `original-prompt.md`. OpenRouter perspective: `host_authority_unavailable`; no external transmission attempted. Historical prompts were excluded.

## Consolidated blockers

1. **Same-UID run spending is not independently authenticated.** `SO_PEERCRED` plus an allowlisted UID cannot distinguish the intended adapter from repository-controlled code under that UID. A broad FIDO-approved run can therefore be raced or spent by another same-UID process. For the first safe request, bind the FIDO assertion to the exact final body digest and complete request scope. Do not claim unattended multi-request automation until a distinct principal/capability boundary is designed and proven.
2. **Production FIDO has no owner.** The authority prompt owns only an injectable fake. Add the pinned libfido2 1.17.0 cgo adapter, internal-UV-only policy, enrollment record, assertion verification, operator-terminal exact-request ceremony, and production-ineligible fake separation.
3. **Scanner/policy has no build or package owner.** Replace the unowned external scanner executable with an in-process scanner compiled into the root daemon and a fixed root-owned policy whose digest is bound to authority, or explicitly own/package the executable. The minimum slice selects the in-process scanner.
4. **Daemon composition is unwired.** The authority chunk owns `main.go` before provider transport exists, while the transport chunk cannot modify the composition root. Move daemon composition to a post-authority transport/join chunk.
5. **Packaging is scheduled before its Go dependencies.** Client/admin code needs protocol, authority, and credential interfaces. Make packaging depend on authority and transport; recalculate the critical path.
6. **Adapter fake and regression tests are unowned.** Add a production-ineligible executable fake client to M0 and give the adapter chunk ownership of the existing runner-policy test plus exact first-lane allowlist assertions.
7. **First consumer is ambiguous.** Name one M1 consumer/lane and keep every other Pipeline/dm-review/Airlift lane at `host_authority_unavailable`. Select Pipeline assessment as the first bounded consumer because it exercises artifact delegation without patch application authority.
8. **Plan metadata is stale.** Revision 8 still says prompt generation is pending. The revised plan/manifest must record round-1 review, the corrected scope, and continued non-dispatchable status.

## Sprint-contract additions

- Exact per-request FIDO challenge covers final body digest, origin/method/path, model order, repository/run/lane/candidate, policy digest, nonce, issuance, expiry, and single-use state.
- Same-UID race tests prove an unapproved body cannot spend or replace the approved request; exact duplicate replay sends at most once.
- Real libfido2 code exists and compiles behind the pinned ABI; real hardware remains a separately executed enablement gate, not a mocked pass.
- The in-process scanner and fixed policy are part of the daemon measurement; no caller selects code or path.
- The provider transport chunk owns daemon composition and black-box startup wiring.
- Packaging owns focused injected-root tests and runs only after its Go dependencies.
- Pipeline assessment is the only M1 automated consumer; all other consumers preserve the explicit Codex fallback.

Final audit: no active prompt contains Amendment/Addendum/Correction residue. Finding actions were consolidated as replacements rather than append-only execution instructions.
