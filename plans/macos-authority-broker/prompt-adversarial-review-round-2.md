# Prompt adversarial review — round 2

Verdict: **REVISE**

OpenRouter perspective: `host_authority_unavailable`; no transmission attempted.

Both available local perspectives identified the same remaining seam: M0 froze JSON artifacts but not the byte-level single-connection exchange joining the adapter, fixed client, daemon body construction, terminal display, FIDO assertion, response delivery, and terminal receipt. The plan also required the in-process scanner build identity without placing that identity in the frozen authority bytes.

Revision disposition:

- Added a closed provider-dispatch exchange schema to chunk 01 ownership.
- Froze big-endian header/part/control/content framing, one-connection challenge and consent acknowledgement, original-connection binding, fd-3 anonymous-pipe delivery, trust verification, and exit-code mapping.
- Explicitly made transaction identity non-authoritative and unusable from any other connection.
- Added daemon/scanner build digest to request/challenge/FIDO authority and substitution vectors.
- Removed the separate `authorize-provider-request` command; the same fixed client connection displays scope, acknowledges it, waits for daemon-owned FIDO, verifies terminal evidence, and releases content.
- Added hostile pending substitution, reservation flooding, wrong-connection consent, disconnect, stale challenge, build/policy substitution, early-content, and later-retrieval cases.

Final audit: no active prompt contains Amendment/Addendum/Update/Clarification/Correction headings or coexisting superseded exchange language.
