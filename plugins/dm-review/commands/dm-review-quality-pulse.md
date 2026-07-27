---
name: dm-review-quality-pulse
description: Run a scheduled or local repository quality pulse from a trusted repository-owned profile
argument-hint: "[--profile <path>]"
---

# dm-review Quality Pulse

Run the shared quality-pulse workflow from
`plugins/dm-review/skills/quality-pulse/SKILL.md` with `$ARGUMENTS`.

The default profile is `.dm-review/quality-pulse.json`. An explicit
`--profile <path>` is accepted only as trusted local operator input; it does
not make a profile from an untrusted pull request executable.

This command produces a repository quality digest. It is not a pull-request
review, a visual test, a feature pipeline, or a merge recommendation.

The Claude command is canonical. The Codex command-skill alias is generated
from this file by `tools/generate-codex-command-skills.py`; do not maintain a
second hand-written alias.
