# Independent-family lanes (Branches C and D)

Loaded only when the selected roster includes the `second-perspective` lane or
the `security-auditor-codex-signoff` lane -- both resolve their reviewer family
against the implementing family. A dispatch with neither role selected never
loads this file.

**C. If the selected role is `second-perspective`:**

1. Read `$DM_REVIEW_BUNDLE_ROOT/agents/review/codex-perspective.md`.
2. Build a read-only prompt per the common contract, with `implementer_family`, `reviewer_family`, and `resolution_reason`.
3. Dispatch on the resolved family:
   - OpenAI/Codex: run:
   ```bash
   printf '%s' "$REVIEW_PROMPT" | codex exec -s read-only -c service_tier=fast --skip-git-repo-check -
   ```
   - Anthropic/Claude: dispatch through the native read-only Claude harness with the same prompt and no coding authority.
   - An OpenRouter-served third party: use Branch A only through the authorized path, preserving that model vendor as `reviewer_family`.
4. If the resolved family fails, continue down the remaining policy-derived non-implementing families in subscription-first order. Never retry on an implementing family.
5. If no independent family completes, record `second-perspective: unavailable` and its attempted resolution in the Agent Summary and Coverage Gaps. Do not mark the review clean until the remaining selected agents have completed and Phase 5 consolidation has run.

**D. If the selected role is `security-auditor-codex-signoff`:**

1. The compatibility lane ID remains stable, but provider resolution is family-aware. Codex is preferred when Codex did not implement the diff.
2. When Codex is the implementer, use the strongest available non-implementing family under subscription-first resolution. After eligible subscription rails, use the matrix security head, currently Kimi K3, only through its authorized path. Never fall back to Codex for this sign-off.
3. Dispatch `$DM_REVIEW_BUNDLE_ROOT/agents/review/security-auditor.md` with the complete unfiltered diff. The sign-off remains mandatory and full-diff regardless of which family performs it.
4. Record `implementer_family`, `reviewer_family`, and `resolution_reason`, including every family swap and why it occurred. If no independent family can complete, the lane is incomplete and the review cannot be clean.
