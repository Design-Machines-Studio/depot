---
name: sprint-plan
description: Run the full sprint planning workflow -- review, triage, calendar, content, and loading
argument-hint: "[skip phases: 'skip content', 'skip mail', 'just review and load']"
---

# Sprint Planning

Run the full 9-phase sprint planning workflow. Integrates sprint review, Userback feedback triage, calendar prep, mail scan, content ideation, and sprint loading into a single orchestrated session.

**Philosophy:** Travis plans, Claude executes. Present findings and suggestions -- Travis decides.

## Process

### Step 1: Load Context

Read these files to understand the workflow:

- `plugins/project-manager/skills/planner/SKILL.md` -- permission rules, database IDs, session conventions
- `plugins/project-manager/skills/planner/references/databases.md` -- Notion database schemas
- `plugins/project-manager/skills/planner/references/conventions.md` -- API quirks and formatting rules

Look up database IDs from the `DM Notion Workspace` entity in ai-memory.

### Step 2: Parse Arguments

Check if Travis wants to skip any phases:

- "skip content" -- skip Phase 7 (Content Scan)
- "skip mail" -- skip Phase 6 (Mail Scan)
- "skip calendar" -- skip Phase 5 (Calendar & Meeting Prep)
- "skip userback" -- skip Phase 4 (Userback Triage)
- "just review and load" -- run only Phases 1, 2, 3, 8, 9
- No arguments -- run all 9 phases

### Step 3: Detect Environment

Check whether shell access is available (needed for Calendar.app and Mail.app phases):

- If shell is available: all phases can run
- If no shell: skip Phases 5 and 6 with a note to Travis

### Step 4: Execute Phases

Run phases in order, loading each reference file as needed. Pause between major phases for Travis's input.

| Phase | Reference File | Pause After? |
|-------|---------------|-------------|
| 1. Sprint Review | `references/sprint-stats.md` | Yes -- review stats |
| 2. Sprint Rollover | `references/sprint-planning.md` | Yes -- keep/defer/drop decisions |
| 3. Conversation Review | `references/sprint-planning.md` | Yes -- review findings |
| 4. Userback Triage | `references/userback-triage.md` | Yes -- approve themes |
| 5. Calendar & Meeting Prep | `references/meeting-prep.md` | Yes -- review briefs |
| 6. Mail Scan | `references/mail-scan.md` | Yes -- flag action items |
| 7. Content Scan | `references/content-scan.md` | Yes -- approve ideas |
| 8. Sprint Loading | `references/sprint-planning.md` | Yes -- Travis selects tasks |
| 9. Sprint Commitment | `references/sprint-planning.md` | No -- final confirmation |

### Step 5: Companion Skills

Load these companion skills when reaching their relevant phases:

- **Phases 1, 3 (Review, Conversation):** Load `ai-memory` skill from ned plugin for sprint stats and conversation mining
- **Phase 5 (Calendar):** Load `strategy` skill from design-machines plugin for participant research
- **Phase 7 (Content):** Load `social-media` and `voice` skills from ghostwriter plugin, `governance` from council plugin
- **Phase 8 (Loading):** Reference LT10 capacity rules from `lt10` skill

### Step 6: Wrap Up

After Phase 9, summarize the sprint plan:

```
## Sprint Plan Complete -- [Sprint Name]

**Period:** [start] to [end]
**Tasks loaded:** X (vs. rolling avg of Y)
**By project:** [project breakdown]
**New todos created:** X (from Userback, mail, content, conversation review)
**Meeting prep todos:** X
**Content ideas added:** X
```
