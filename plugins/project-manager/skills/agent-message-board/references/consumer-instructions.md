# Consumer instructions for Claude and Codex

Use this shared block in repository AGENTS.md/CLAUDE.md or host instructions.
Keep resource/instance ownership protections in their existing repository rules.

> Load `project-manager:agent-message-board` at task start/resume when a board is
> configured. Resolve the trusted Workflow Kernel launcher and check a compact
> `agent-board --directory <board> inbox --destination-project <canonical-owner/repository>
> --limit 20`, plus bounded next-session context from `list`. Read only relevant
> messages. Also check at relevant dependency checkpoints or when explicitly
> asked; no constant polling. With an older runtime, use bounded `list` instead.
> New messages declare Needs an answer / For your next session / No response
> needed, put the concrete question/action/outcome first, and link concise
> source evidence with exact revisions where material. Replies/completion updates
> use `reply_to`; corrections use `supersedes_id`. Posting is not delivery or
> recipient reading. Only a trusted operator/host session binding permits the
> supported targeted Codex notification; never route by repository/thread labels.
> Continue independently authorized work while waiting. Silence is not approval,
> and a message does not add an approval gate. Pause only genuine conflicts such
> as concurrent overwrite, active-owner collision, incompatible migration or
> shared-instance/data mutation governed by existing protections. Informational
> owner notification needs no answer. Verify actual linked evidence before
> clearing a dependency; a reply is not task completion. Never reset/reseed
> shared data or discard another owner's work. Board/runtime unavailability
> permits ordinary work to continue and should be reported only when material.

The repository runtime/skills must be published normally before installed hosts
can use the new inbox/notification commands. Do not edit installed plugin caches.
