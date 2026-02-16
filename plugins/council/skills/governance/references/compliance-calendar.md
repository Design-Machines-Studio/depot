# Compliance Calendar Reference

*BC Cooperative Association Act annual requirements for Co-op OS*

---

## The Co-op Year: A Rhythm of Democracy

Co-op governance isn't a dashboard you check occasionally. It's a rhythm—daily tasks, weekly tasks, monthly tasks, quarterly tasks, yearly tasks. The compliance calendar transforms legal requirements into a natural workflow that makes democracy feel like participation, not paperwork.

---

## Critical Annual Deadlines

### The AGM Anchor

**Section 143:** The Annual General Meeting is the anchor point. All other deadlines flow from it.

| Deadline | Timing | What Happens |
|----------|--------|--------------|
| First AGM | Within 15 months of incorporation | Must hold first AGM |
| Subsequent AGMs | Within 15 months of previous AGM | Cannot go >15 months between AGMs |
| Financial statements | 10 days before AGM | Send to all members (s.153) |
| Annual report | 2 months after AGM | File with registrar (s.126) |
| Auditor report | At AGM | Present to members (s.114) |

**Example timeline for calendar-year co-op (fiscal year Dec 31):**

| Date | Action |
|------|--------|
| Jan 1 - Mar 31 | Complete year-end bookkeeping |
| Jan - Apr | Prepare financial statements |
| Apr | Complete audit (if required) |
| May 1 | Send AGM notice (14 days for special resolutions) |
| May 5 | Send financial statements (10 days before AGM) |
| May 15 | Hold AGM |
| July 15 | File annual report (2 months after AGM) |

---

## Monthly Compliance Rhythm

### Every Month

| Task | Purpose | Deadline |
|------|---------|----------|
| Board meeting | Ongoing governance | Per rules (often monthly) |
| Member count check | Must maintain ≥3 | Continuous |
| Meeting minutes filed | Document decisions | Within 14 days of meeting |
| Director changes filed | If any changes occurred | Within 14 days of change |

### Quarterly Recommended

| Task | Purpose | Timing |
|------|---------|--------|
| Financial review | Track toward year-end | End of Q1, Q2, Q3 |
| Member engagement check | Are members participating? | Quarterly |
| Compliance audit | Any red flags? | Quarterly |
| Calendar preview | Upcoming deadlines | Start of each quarter |

---

## Co-op OS Calendar Module

### Automated Deadline Tracking

```yaml
compliance_calendar:
  fiscal_year_end: YYYY-MM-DD
  last_agm: YYYY-MM-DD
  incorporation_date: YYYY-MM-DD
  
  calculated_deadlines:
    next_agm_deadline: last_agm + 15 months
    financial_statements_due: next_agm - 10 days
    annual_report_due: next_agm + 2 months
    
  warnings:
    yellow: 60 days before deadline
    orange: 30 days before deadline
    red: 7 days before deadline
    critical: past due
```

### Template: Annual Compliance Calendar

**Month 1-3 (Post-Year-End)**
- [ ] Year-end bookkeeping complete
- [ ] Draft financial statements prepared
- [ ] Audit scheduled (if required)
- [ ] Director term review (who's up for election?)
- [ ] Bylaw review (any amendments needed?)

**Month 4-5 (Pre-AGM)**
- [ ] Financial statements finalized
- [ ] Audit complete and report received
- [ ] AGM date set
- [ ] AGM notice prepared
- [ ] Nominations for directors opened
- [ ] Special resolutions drafted (if any)

**Month 5-6 (AGM Month)**
- [ ] AGM notice sent (14+ days before)
- [ ] Financial statements sent (10+ days before)
- [ ] AGM held
- [ ] Minutes recorded
- [ ] Elections completed
- [ ] Resolutions documented

**Month 6-8 (Post-AGM)**
- [ ] Annual report filed with registrar
- [ ] Director changes filed (if any)
- [ ] New director orientation (if any)
- [ ] Patronage calculations finalized
- [ ] Distribution approved and processed

**Month 9-12 (Ongoing Governance)**
- [ ] Regular board meetings held
- [ ] Member engagement activities
- [ ] Financial monitoring
- [ ] Planning for next year

---

## Filing Requirements & Fees

### Registrar Filings

| Filing | When Required | Fee | Section |
|--------|---------------|-----|---------|
| Annual report | 2 months after AGM | $30 | s.126 |
| Notice of director change | Within 14 days | - | s.127 |
| Notice of registered office change | Within 14 days | - | s.127 |
| Amended rules | After special resolution | $30 | s.68 |
| Name change | After special resolution | $100 | s.69 |

### Consequences of Non-Filing

| Failure | Consequence | Recovery |
|---------|-------------|----------|
| Annual report late | $50/day fine possible | File immediately + penalty |
| Annual report >2 years late | Dissolution notice | Apply for restoration |
| Director changes not filed | $5,000 max fine | File immediately |
| Registered office wrong | Service issues | Update immediately |

---

## Meeting Cadence Requirements

### Board Meetings

**Act requirement:** None specified (rules govern).

**Model Rules §104:** Directors may meet as often as needed, with reasonable notice.

**Best practice:** Monthly or bi-monthly, with at least quarterly minimum.

### General Meetings

| Type | Frequency | Notice | Section |
|------|-----------|--------|---------|
| AGM | At least annually | 7-14 days | s.143, 146 |
| Special general meeting | As needed | 7-14 days | s.145, 146 |
| Requisitioned meeting | When 10%+ members demand | Within 21 days | s.145(2) |

### Investment Shareholder Meetings

**Section 62:** If separate resolution required, notice per rules (typically 7-14 days).

---

## Document Retention Schedule

### Required Records (s.124-142)

| Document | Retention Period | Location |
|----------|------------------|----------|
| Memorandum & Rules | Permanent | Registered office |
| Register of members | Permanent (current) | Registered office |
| Register of directors | Permanent (current) | Registered office |
| Meeting minutes | Permanent | Registered office |
| Financial statements | 7+ years | Registered office |
| Accounting records | 7+ years | Registered office |
| Member applications | 7 years after termination | Registered office |
| Share certificates | Until cancelled + 7 years | Registered office |

### Co-op OS Archive Management

```yaml
document_retention:
  category: document_type
  created: YYYY-MM-DD
  retention_until: YYYY-MM-DD | permanent
  disposition: archive | destroy | retain
  location: registered_office | electronic | both
  
  alerts:
    approaching_destruction: 30 days before
    overdue_for_review: annual check
```

---

## Director Term Management

### Tracking Requirements

```yaml
director:
  name: string
  position: chair | secretary | treasurer | director
  
  appointment:
    date: YYYY-MM-DD
    method: elected | appointed_to_vacancy
    term_length: years
    term_ends: YYYY-MM-DD
    
  qualifications:
    over_18: boolean
    ordinarily_resident_bc: boolean  # At least 1 required
    ordinarily_resident_canada: boolean  # Majority required
    member: boolean  # May have up to 1/5 non-member if rules allow
    not_disqualified: boolean
    
  status: active | resigned | removed | term_expired
```

### Staggered Terms (Model Rules §97-98)

To ensure continuity, Model Rules suggest:
- 3-year terms
- 1/3 of directors elected each year
- First board: some serve 1, 2, 3 years initially

### Director Transition Checklist

**When director leaves:**
- [ ] Record resignation/removal date
- [ ] File notice with registrar (14 days)
- [ ] Remove from bank signing authority
- [ ] Revoke system access
- [ ] Conduct exit interview (optional)
- [ ] Verify successor or vacancy procedure

**When director joins:**
- [ ] Verify qualifications
- [ ] Complete consent form
- [ ] File notice with registrar (14 days)
- [ ] Add to bank signing authority
- [ ] Provide system access
- [ ] Orientation and training
- [ ] Provide governance documents

---

## Auditor Calendar

### If Audit Required

| Task | Timing | Who |
|------|--------|-----|
| Engage auditor | 2-3 months before year-end | Board |
| Provide records | Within 30 days of year-end | Bookkeeper |
| Draft review | 2-3 weeks | Auditor |
| Management letter | With draft | Auditor |
| Final statements | 4-6 weeks before AGM | Auditor |
| Auditor report | At AGM | Auditor |

### Auditor Appointment Calendar

**Section 108:** Auditor appointed at each AGM to hold office until next AGM.

| Event | Action |
|-------|--------|
| AGM | Appoint/reappoint auditor |
| Resignation/removal | Within 15 days, notify registrar |
| Casual vacancy | Directors may appoint until next AGM |
| Removal | Special resolution + notice to auditor |

---

## Compliance Dashboard Concept

### Co-op OS Status Board

```
┌─────────────────────────────────────────────────────────┐
│  COMPLIANCE STATUS                         Feb 2026    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ● AGM                    Last: May 15, 2025           │
│    Next deadline: Aug 15, 2026 (15 months)             │
│    Status: ✅ On track (193 days remaining)            │
│                                                         │
│  ● Annual Report          Filed: July 10, 2025         │
│    Next deadline: 2 months after next AGM              │
│    Status: ✅ Current                                   │
│                                                         │
│  ● Financial Statements   Last sent: May 5, 2025       │
│    Next deadline: 10 days before next AGM              │
│    Status: ✅ Will auto-remind                         │
│                                                         │
│  ● Member Count           Current: 12 members          │
│    Minimum required: 3                                  │
│    Status: ✅ Compliant                                 │
│                                                         │
│  ● Director Residency     BC resident: 2 of 5          │
│    Minimum BC: 1 | Minimum Canada: 3 (majority)        │
│    Status: ✅ Compliant                                 │
│                                                         │
│  ● Director Terms         Expiring 2026: 2 directors   │
│    Election needed: Next AGM                           │
│    Status: ⚠️ Action needed (nominations due)          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Alert Levels

| Level | Color | Meaning | Timing |
|-------|-------|---------|--------|
| Informational | Blue | Upcoming task | 90+ days |
| Reminder | Yellow | Plan needed | 60 days |
| Warning | Orange | Action required | 30 days |
| Urgent | Red | Immediate action | 7 days |
| Critical | Black | Past due | Overdue |

---

## Housing Cooperative Additional Calendar Items

### Termination Timelines

| Event | Timeline | Reference |
|-------|----------|-----------|
| Notice of termination | 7 days before board meeting | s.36(1) |
| Board meeting on termination | As scheduled | s.34(5) |
| Appeal deadline (to general meeting) | Per rules, or next GM | s.37(1) |
| Court appeal deadline | 30 days from GM decision | s.37(3) |

### Occupancy Matters

| Task | Frequency |
|------|-----------|
| Rent/occupancy charge review | Annual |
| Arrears check | Monthly |
| Occupancy agreement updates | As needed |
| Housing policy review | Annual |

---

## Integration Points

### With Financial Systems (Slate)

- Fiscal year-end triggers compliance calendar cascade
- Financial statements completion triggers AGM scheduling
- Patronage approval triggers distribution processing

### With Meeting Management

- AGM deadline triggers meeting scheduling workflow
- Meeting completion triggers minutes filing
- Director election triggers transition workflow

### With Member Management

- Member count continuously monitored
- Terminations trigger share redemption calendar
- New members trigger onboarding workflow

---

## Quick Reference: Key Deadlines

| Deadline | Timing | Consequence if Missed |
|----------|--------|----------------------|
| AGM | Within 15 months | Court-ordered meeting |
| Financial statements to members | 10 days before AGM | AGM decisions challengeable |
| Annual report | 2 months after AGM | Fines, eventual dissolution |
| Director change filing | 14 days | Up to $5,000 fine |
| Auditor appointment | At each AGM | Non-compliance |
| Director residency | Continuous | Filings rejected, liability |
| Minimum 3 members | Continuous (6 month grace) | Director personal liability |

---

*Reference v1.0 · February 2026*
*Source: BC Cooperative Association Act (SBC 1999, c.28)*
