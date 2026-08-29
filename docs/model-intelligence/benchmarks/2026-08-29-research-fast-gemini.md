# Gemini 3.7 Flash research-fast benchmark

Run date: 2026-08-29 (Asia/Makassar)

Baseplate evidence revision: `f527fdf4b69725d73ed4ba01a3b4903a6b694211`

Requested model: `google/gemini-3.7-flash`

Fresh catalog canonical identity: `google/gemini-3.7-flash-20260813`

Sealed prompt SHA-256: `5e4eb127192e324cccbefd13272511d3203acd3d26f9d7e0141c28090a2f7864`

Final scorer SHA-256: `61a293015cd9278867318d0303e15dff6e5ef76a6d49932ae0a660f9ee4ef799`

## Scenario

The candidate received Baseplate's exact Go, Templ, Datastar Go, and NATS
pins; Docker/CI and architecture constraints; current official documentation
extracts captured through Context7; and two deliberately false internal claims.
It had to produce a source-ID-attributed JSON recommendation without outside
knowledge.

This measures evidence synthesis and contradiction handling. It does not
measure autonomous browsing or source discovery because the single-turn
OpenRouter wrapper supplied the evidence and exposed no research tools.

## Results

| Attempt | Response model | Provider | Fallback | Score | Words | Duration | Prompt | Completion | Reasoning | Billed cost |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `google/gemini-3.7-flash` | Google AI Studio | false | 100/100 | 641 | 8.10s | 1,875 | 2,709 | 1,329 | $0.01156500 |
| 2 | `google/gemini-3.7-flash` | Google AI Studio | false | 100/100 | 584 | 10.12s | 1,875 | 2,372 | 1,005 | $0.01030125 |
| 3 | `google/gemini-3.7-flash` | Google AI Studio | false | 100/100 | 589 | 8.10s | 1,875 | 2,327 | 1,000 | $0.01013250 |

Medians: 589 words, 8.10 seconds, 1,875 prompt tokens, 2,372 completion
tokens, 1,005 reasoning tokens, and `$0.01030125` billed cost. Total
provider-billed spend was **$0.03199875**.

All attempts held the current pins, covered all four components, rejected both
unsupported claims, retained supplied-source citations and unknowns, and
proposed bounded local validation rather than dependency churn.

## Scorer correction

The original scorer produced 90, 80, and 80 because it required correct
evidence in specific `reason` fields even though the task allowed it in other
structured fields. The scorer was corrected to inspect the complete semantic
objects. The task, evidence, prompt, outputs, receipts, and paid attempts were
unchanged; the original scores remain part of the private receipt history.

## Routing interpretation

This is positive prototype evidence for Gemini as `research-fast`, but it is
one evidence-bound scenario. It does not compare other research candidates,
measure source discovery, or provide production-canary attribution.

**No routing change justified.**

Next benchmark: a tool-enabled source-discovery case where candidates locate
exact official release notes, bind claims to retrieved versions and dates, and
are checked against a hidden source allowlist.
