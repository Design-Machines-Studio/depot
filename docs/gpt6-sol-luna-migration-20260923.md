# GPT-6 Sol and Luna migration — 2026-09-23

Active native roles replace GPT-5.6 Sol with GPT-6 Sol and both GPT-5.6 Luna
and Terra with GPT-6 Luna. Deduplicate the merged Luna candidates; builder-fast
uses Sol as its next native fallback. Keep effort normalization, subscription
preference, family independence, browser ownership and verification unchanged.
No mandatory maximum-effort escalation follows from vendor benchmarks.

Sources: [release](https://openai.com/index/introducing-gpt-6-sol-and-luna/),
[Sol](https://developers.openai.com/api/docs/models/gpt-6-sol),
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), and the public
OpenRouter catalog fetched on this date. Sol input/cache-read/output costs are
$2/$0.20/$10 per million tokens; Luna costs $0.10/$0.01/$0.50. Above 272K input
tokens the model cards state 2x input/cache and 1.5x output rates for the whole
request. Existing native imputation cannot represent these tiers, so no new
native pricing aliases are added. Missing estimates stay unavailable. Historical
GPT-5.6 native aliases retain their old dated prices solely for old receipts.

The routing snapshot is assembled today; only the two new OpenAI catalog rows
have fresh evidence. Other providers retain their old evidence explicitly marked
by catalog_evidence_date/status. Do not transfer old Luna/Terra usage or benchmark
results to the replacements. Live availability probes remain required.

NED's cached Codex catalog still advertises GPT-5.6 identities at inspection.
The release announcement is not a successful native execution canary. No user
configuration, context limits or installed plugins were changed. Fresh native
execution, matched review quality/latency, and actual subscription savings remain
unproved. API context is not the Codex usable context. Improved vendor caching
is a reason to preserve stable prefixes, not to introduce a new caching service.
