# Red Flags Reference

*Early warning indicators for Co-op OS governance monitoring*

---

## The Red Flag Philosophy

Red flags aren't just compliance issues—they're early warning signs that governance is drifting. Every issue starts small. A missed filing becomes a pattern. A quorum problem becomes meeting dysfunction. An unclear bylaw becomes a contested decision.

Co-op OS should surface these signals before they become crises.

---

## Critical Red Flags (Immediate Action Required)

### 🔴 Membership Below Minimum

**The Rule (s.10):** Association must have at least 3 members.

**Grace Period (s.10(3)):** If membership drops below 3 for more than 6 months, every director and officer is personally liable for debts incurred during the deficiency period.

**Detection:**
```yaml
red_flag:
  type: membership_count_critical
  trigger: member_count < 3
  severity: critical
  
  action_required:
    immediate: 
      - Alert all directors
      - Block new financial obligations
      - Initiate emergency recruitment
    deadline: 6 months from first below-minimum date
    consequence: Personal director/officer liability
```

**Co-op OS Response:**
- Dashboard alert (red, persistent)
- Email to all directors immediately
- Weekly countdown until resolved
- Log all financial transactions (potential liability)

---

### 🔴 No BC Resident Director

**The Rule (s.72(1)(b)):** At least one director must be ordinarily resident in BC.

**Consequence:** Registrar may refuse filings. Association may be considered non-compliant.

**Detection:**
```yaml
red_flag:
  type: director_residency_bc
  trigger: count(directors.ordinarily_resident_bc == true) < 1
  severity: critical
  
  action_required:
    immediate:
      - Cannot file documents with registrar
      - Must elect/appoint BC resident director
    deadline: Before next filing
```

---

### 🔴 Majority of Directors Not Canadian Residents

**The Rule (s.72(1)(a)):** A majority of directors must be ordinarily resident in Canada.

**Detection:**
```yaml
red_flag:
  type: director_residency_canada
  trigger: count(directors.ordinarily_resident_canada == true) < (total_directors / 2) + 1
  severity: critical
  
  action_required:
    immediate:
      - Board decisions may be challenged
      - Must rectify director composition
```

---

### 🔴 AGM Not Held Within 15 Months

**The Rule (s.143):** 
- First AGM: within 15 months of incorporation
- Subsequent: within 15 months of previous AGM

**Detection:**
```yaml
red_flag:
  type: agm_overdue
  trigger: today > (last_agm + 15 months)
  severity: critical
  
  action_required:
    immediate:
      - Court can order meeting be held
      - Members can requisition meeting
      - All business decisions at risk
    remedy: Hold AGM immediately
```

**Escalation Timeline:**
- 3 months before deadline → Yellow warning
- 1 month before → Orange warning  
- 7 days before → Red warning
- Past deadline → Critical, all directors notified

---

### 🔴 Distributions During Insolvency

**The Rule (s.66(2)):** Cannot redeem shares or pay dividends/patronage if it would render the association unable to pay debts as they become due.

**Detection:**
```yaml
red_flag:
  type: insolvency_distribution
  trigger: distribution_approved AND solvency_test_failed
  severity: critical
  
  action_required:
    immediate:
      - Block distribution
      - Rescind authorization
      - Document solvency status
    consequence: Director personal liability possible
```

---

## High-Priority Red Flags (Action Required Within 30 Days)

### 🟠 Annual Report Not Filed

**The Rule (s.126):** File within 2 months after AGM.

**Consequence (s.194.4):** Registrar may dissolve association for non-filing.

**Detection:**
```yaml
red_flag:
  type: annual_report_overdue
  trigger: today > (last_agm + 2 months) AND annual_report_not_filed
  severity: high
  
  action_required:
    deadline: Immediate
    consequence: Fines ($50/day possible), eventual dissolution
    remedy: File immediately with late fees
```

---

### 🟠 Director Changes Not Filed

**The Rule (s.127):** Must file notice of director changes within 14 days.

**Consequence:** Fine up to $5,000.

**Detection:**
```yaml
red_flag:
  type: director_filing_overdue
  trigger: director_change_occurred AND filing_not_completed AND days_elapsed > 14
  severity: high
  
  action_required:
    deadline: Immediate
    remedy: File immediately
```

---

### 🟠 Financial Statements Not Sent Before AGM

**The Rule (s.153(1)(b)(iv)):** Must send to members at least 10 days before AGM.

**Consequence:** AGM decisions may be challenged as procedurally invalid.

**Detection:**
```yaml
red_flag:
  type: financial_statements_late
  trigger: agm_scheduled AND (agm_date - today) < 10 days AND statements_not_sent
  severity: high
  
  action_required:
    immediate: 
      - Postpone AGM, OR
      - Send statements immediately and document late sending
    risk: Member challenge to AGM decisions
```

---

### 🟠 Quorum Failures Becoming Pattern

**Detection:**
```yaml
red_flag:
  type: quorum_pattern
  trigger: quorum_failures_last_12_months >= 3
  severity: high
  
  action_required:
    analyze:
      - Meeting times/accessibility
      - Member engagement levels
      - Communication effectiveness
    remedies:
      - Adjust meeting logistics
      - Reduce quorum in rules (if appropriate)
      - Member engagement campaign
```

---

### 🟠 Audit Required But Not Completed

**The Rule (s.108, 114):** If audit required, auditor must audit statements annually.

**Detection:**
```yaml
red_flag:
  type: audit_not_completed
  trigger: audit_required AND agm_approaching AND audit_not_done
  severity: high
  
  action_required:
    immediate:
      - Engage auditor urgently
      - May need to postpone AGM
    consequence: Cannot present compliant financial statements
```

---

## Medium-Priority Red Flags (Monitor and Plan)

### 🟡 Director Terms Expiring With No Succession Plan

**Detection:**
```yaml
red_flag:
  type: succession_gap
  trigger: director_terms_expiring_within_90_days > 0 AND nominations_received == 0
  severity: medium
  
  action_required:
    recruit: Open nominations, active outreach
    timeline: Before AGM
    risk: Unfilled positions, insufficient board
```

---

### 🟡 Reserve Allocations Not Made Per Rules

**Detection:**
```yaml
red_flag:
  type: reserve_skipped
  trigger: year_end_surplus > 0 AND reserve_allocation == 0 AND model_rules_apply
  severity: medium
  
  action_required:
    review: Was allocation intentionally waived?
    document: If rules permit flexibility, document reasoning
    risk: Bylaw non-compliance
```

---

### 🟡 Conflict of Interest Disclosure Gaps

**The Rule (s.86-96):** Directors/officers must disclose material conflicts.

**Detection:**
```yaml
red_flag:
  type: conflict_disclosure_missing
  trigger: transaction_with_related_party AND no_disclosure_recorded
  severity: medium
  
  action_required:
    immediate: Obtain disclosure
    document: Record in minutes
    risk: Transaction voidable, director liability
```

---

### 🟡 Membership Shares Not Fully Paid

**The Rule (s.52):** Shares must be fully paid (except membership shares payable on call).

**Detection:**
```yaml
red_flag:
  type: shares_not_paid
  trigger: member_share_balance_owing > 0 AND call_not_issued
  severity: medium
  
  action_required:
    if_call_permitted: Issue call per rules
    if_not: Member may be in breach
```

---

### 🟡 Minutes Not Recorded or Filed

**Detection:**
```yaml
red_flag:
  type: minutes_missing
  trigger: meeting_held AND minutes_not_filed_within_14_days
  severity: medium
  
  action_required:
    prepare: Complete minutes from notes/recording
    risk: Decisions undocumented, disputes harder to resolve
```

---

## Low-Priority Red Flags (Track for Patterns)

### 🔵 Member Engagement Declining

**Detection:**
```yaml
red_flag:
  type: engagement_decline
  trigger: meeting_attendance_trend < -20% over 12 months
  severity: low
  
  watch_for:
    - Voting participation rates
    - Committee involvement
    - Response to communications
  risk: Future quorum problems, democratic deficit
```

---

### 🔵 Single Points of Failure

**Detection:**
```yaml
red_flag:
  type: concentration_risk
  trigger:
    - Only one person knows system password
    - Only one signing authority active
    - Only one person handles all compliance
  severity: low
  
  action_required:
    cross_train: Document processes, train backups
    risk: Disruption if key person unavailable
```

---

### 🔵 Bylaws Haven't Been Reviewed

**Detection:**
```yaml
red_flag:
  type: bylaws_stale
  trigger: last_bylaw_review > 3 years
  severity: low
  
  recommended:
    - Schedule governance review
    - Compare against current Act requirements
    - Update for operational changes
```

---

## Red Flag Dashboard Concept

```
┌─────────────────────────────────────────────────────────┐
│  GOVERNANCE HEALTH CHECK                   Feb 2026    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  CRITICAL (0)                                          │
│  ─────────────────────────────────────────────────────  │
│  ✅ No critical issues                                 │
│                                                         │
│  HIGH PRIORITY (1)                                      │
│  ─────────────────────────────────────────────────────  │
│  🟠 Director filing overdue (Jane Smith resignation)   │
│     └─ Filed: No | Days overdue: 5 | [File Now]        │
│                                                         │
│  MEDIUM PRIORITY (2)                                    │
│  ─────────────────────────────────────────────────────  │
│  🟡 2 director terms expiring at May AGM               │
│     └─ Nominations received: 0 | [Open Nominations]    │
│  🟡 Minutes outstanding for Jan 15 board meeting       │
│     └─ Days since meeting: 22 | [Add Minutes]          │
│                                                         │
│  WATCHING (3)                                          │
│  ─────────────────────────────────────────────────────  │
│  🔵 Meeting attendance down 15% (vs last year)         │
│  🔵 Bylaws last reviewed 2.5 years ago                 │
│  🔵 Only 2 active signing authorities                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Housing Cooperative Additional Red Flags

### 🔴 Arrears Exceeding Threshold

**Detection:**
```yaml
red_flag:
  type: housing_arrears
  trigger: member_arrears > rules_threshold OR arrears_age > 60_days
  severity: high (housing)
  
  action_required:
    notice: Issue payment demand per rules
    timeline: Termination procedures if not resolved
    special: Housing co-op termination procedures apply (s.35)
```

---

### 🟠 Occupancy Without Membership

**Detection:**
```yaml
red_flag:
  type: non_member_occupant
  trigger: unit_occupied AND occupant_not_member AND not_permitted_guest
  severity: high (housing)
  
  action_required:
    review: Is membership application pending?
    action: Regularize status or terminate occupancy
```

---

### 🟠 Termination Appeal Period Active

**Detection:**
```yaml
red_flag:
  type: termination_appeal_pending
  trigger: termination_decided AND appeal_period_active
  severity: medium (housing)
  
  watch:
    court_appeal_deadline: 30 days from GM decision
    actions: Cannot enforce until appeal resolved
```

---

## Red Flag Integration with Nimber

The red flag framework in Co-op OS mirrors the estimation red flags in Nimber—both are early warning systems:

| Nimber Red Flag | Co-op OS Equivalent |
|-----------------|---------------------|
| Budget too low | Reserve allocation skipped |
| Timeline too short | AGM deadline approaching |
| Scope unclear | Bylaws stale/unclear |
| Client communication issues | Member engagement declining |
| Team capacity concerns | Board capacity/succession gaps |

**The principle is the same:** Surface problems early, when they're easier to solve.

---

## Response Workflow

### When Red Flag Triggered

1. **Alert** appropriate parties (board, officers, affected members)
2. **Document** the issue and timestamp
3. **Assess** severity and deadline
4. **Assign** responsibility for resolution
5. **Track** progress toward resolution
6. **Resolve** and document completion
7. **Review** to prevent recurrence

### Escalation Path

```
Detection → Auto-alert → Director review → Board agenda → Resolution → Documentation
     ↓
 If unresolved
     ↓
Escalate to → Chair/President → External advisor → Legal counsel
```

---

## Quick Reference: Red Flag Severity Guide

| Severity | Response Time | Who's Notified | Example |
|----------|---------------|----------------|---------|
| Critical | Immediate | All directors + officers | Membership < 3 |
| High | 24-48 hours | Board chair + responsible officer | AGM overdue |
| Medium | 7 days | Responsible officer | Director filing late |
| Low | 30 days | Governance lead | Engagement declining |

---

*Reference v1.0 · February 2026*
*Source: BC Cooperative Association Act (SBC 1999, c.28)*
