---
name: governance-check
description: Quick cooperative governance compliance check
argument-hint: "[optional: specific check like agm, members, directors]"
---

# Governance Compliance Check

Quick status check against BC Cooperative Association Act requirements.

## Process

### 1. Load Context

Read the governance skill's BC Act reference for thresholds:
- `plugins/council/skills/governance/references/bc-cooperative-act.md`
- `plugins/council/skills/governance/references/compliance-calendar.md`

### 2. Check Available Data

Look for governance data in the project:
- Database: `backend/data/coop.db` (if Assembly project)
- Config files: any YAML/JSON with member counts, meeting dates
- Memory: check ai-memory for the co-op entity

If no data source is available, run an interactive checklist instead.

### 3. Compliance Checklist

If an argument was given, check only that area. Otherwise check all:

**Members (s.10)**
- [ ] Minimum 3 members currently active?
- [ ] If below 3, has it been <6 months? (grace period)

**Directors (s.72)**
- [ ] At least 3 directors?
- [ ] Majority Canadian residents?
- [ ] At least 1 BC resident?
- [ ] Non-member directors ≤20%?

**AGM (s.143)**
- [ ] Last AGM date?
- [ ] Next AGM due by? (within 15 months)
- [ ] Days remaining?

**Filings (s.126-127)**
- [ ] Annual report filed after last AGM? (2-month deadline)
- [ ] Director changes filed within 14 days?
- [ ] Financial statements sent 10 days before AGM?

**Audit (s.108-109)**
- [ ] Auditor appointed at last AGM?
- [ ] Or s.109 exemption in place?

### 4. Report

Output a status table:

```
Governance Compliance Status — [date]

| Check              | Status | Detail                    |
|--------------------|--------|---------------------------|
| Member count       | PASS   | 12 active members         |
| Directors          | PASS   | 5 directors, 3 Canadian   |
| AGM timing         | WARN   | Due in 45 days            |
| Annual report      | PASS   | Filed July 2025           |
| Director filings   | PASS   | Current                   |
| Audit              | PASS   | Auditor appointed May 2025|

Overall: COMPLIANT (1 warning)
```

Flag items as:
- **PASS** — compliant
- **WARN** — approaching deadline or needs attention
- **FAIL** — non-compliant, action required
