# Depot Tools

## generate-codex-manifests.py

Generates Codex compatibility manifests from the Claude marketplace manifests.
Claude remains canonical:

- `.claude-plugin/marketplace.json`
- `plugins/*/.claude-plugin/plugin.json`

Generated Codex files:

- `.agents/plugins/marketplace.json`
- `plugins/*/.codex-plugin/plugin.json`

### Regenerate Codex manifests

```bash
./tools/generate-codex-manifests.py
```

### Check generated files are current

```bash
./tools/generate-codex-manifests.py --check
```

## validate-dual-compat.sh

Verifies the generated Codex manifests match the Claude source manifests and
that execution-critical Claude plugin-cache lookups also include Codex cache
fallbacks.

```bash
./tools/validate-dual-compat.sh
```

This check is included in `./tools/validate-composition.sh`.

## eval-descriptions.sh

Evaluates whether SKILL.md descriptions would plausibly trigger for test queries using term-overlap heuristics. Catches regressions when descriptions are edited.

### Run all evals

```bash
./tools/eval-descriptions.sh
```

### Run one eval

```bash
./tools/eval-descriptions.sh ghostwriter-voice.json
```

### Verbose mode (show failures)

```bash
./tools/eval-descriptions.sh -v
./tools/eval-descriptions.sh -v chef-cooking.json
```

### How it works

For each JSON file in `description-evals/`:

1. Resolves the corresponding SKILL.md from the plugin directory
2. Extracts key terms from the description (stripping stopwords)
3. For each test query, counts how many terms overlap with the description
4. If overlap >= 3 (or >= 2 for short queries), predicts the skill should trigger
5. Compares prediction against the `should_trigger` value in the test case
6. Reports accuracy per skill; fails if any skill drops below 70%

This is a heuristic, not a classifier. It measures whether descriptions contain the right vocabulary to match real user queries. Expect 70-95% accuracy.

### Pre-commit hook

To check evals when a SKILL.md description changes, add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "command": "bash -c 'if git diff --name-only | grep -q SKILL.md; then ./tools/eval-descriptions.sh; fi'",
        "description": "Run description evals when SKILL.md changes"
      }
    ]
  }
}
```

Or run manually before committing:

```bash
git diff --name-only | grep SKILL.md && ./tools/eval-descriptions.sh
```

### Adding new eval cases

1. Create `description-evals/<plugin>-<skill>.json`
2. Format: JSON array of `{"query": "...", "should_trigger": true|false}` objects
3. Include 15-20 cases, roughly half true and half false
4. True cases: natural queries a user would type that should activate this skill
5. False cases: thematically adjacent queries that belong to a different skill
6. Run `./tools/eval-descriptions.sh <your-file>.json` to verify

The naming convention maps to SKILL.md paths:
- `ghostwriter-voice.json` -> `plugins/ghostwriter/skills/voice/SKILL.md`
- `craft-developer-craft-mcp.json` -> `plugins/craft-developer/skills/craft-mcp/SKILL.md`
- `live-wires.json` -> `plugins/live-wires/skills/livewires/SKILL.md`
