# Voting & Decisions Reference

*BC Cooperative Association Act compliance for Co-op OS*

---

## Fundamental Principle: One Member, One Vote

**Section 40(1):** "Subject to this Act, the rules and sections 57(2) and 58(4), every member has only one vote, regardless of the number of membership shares or investment shares held by the member."

This is the cornerstone of cooperative democracy. Voting rights derive from **membership**, not capital contribution.

---

## Decision Types & Thresholds

### Ordinary Resolution
**Definition (s.1):** Simple majority of votes cast by members entitled to vote.

**Use for:**
- Routine business decisions
- Election of directors (unless rules specify otherwise)
- Approval of financial statements
- Appointment of auditor (unless exempt)
- Confirming termination appeals (for "material breach" or "failure to pay")

### Special Resolution
**Definition (s.1):** 
- (a) Consent resolution (100% written consent), OR
- (b) Resolution passed by 2/3 majority at general meeting (or 3/4 for housing co-ops)

**Rules may specify threshold between 2/3 and 3/4.**

**Use for:**
- Amending memorandum or rules (s.68)
- Changing association name (s.69)
- Substantial disposition of undertaking (s.71)
- Removal of director (s.82)
- Removal of auditor (s.113)
- Voluntary winding up (s.194.1)
- Confirming termination for "conduct detrimental" (s.37(2)(a))
- Any matter rules designate as requiring special resolution

### Separate Resolution (Investment Shareholders)
**Definition (s.1):** Resolution by 2/3 to 3/4 majority of investment shareholders of a class.

**Required when:**
- Amending rights of investment share class (s.70)
- Substantial disposition of undertaking (s.71(2))
- Any matter affecting class rights

### Consent Resolution
**Section 1 (special resolution definition):** Written resolution signed by 100% of members entitled to vote.

**Effect:** Same force as special resolution passed at meeting.

---

## Notice Requirements

| Meeting Type | Minimum Notice | Statutory Reference |
|--------------|----------------|---------------------|
| AGM (ordinary business only) | 7 days | s.146(1)(a) |
| General meeting with special resolution | 14 days | s.146(1)(b) |
| Director meeting | As rules specify | Model Rules §104 |
| Investment shareholder meeting | 7-14 days per rules | s.62(2) |

**Notice must include:**
- Date, time, place of meeting
- General nature of business
- Full text of any special resolution (s.146(3))

**Financial statements:** Must be provided at least 10 days before AGM (s.153(1)(b)(iv)).

---

## Quorum Rules

### Member Meetings
**Model Rules §75:** 10% of members entitled to vote, present in person or by proxy.

**If no quorum:**
- Wait 30 minutes
- If still no quorum: meeting adjourned to same day/time next week
- At adjourned meeting: members present constitute quorum (Model Rules §76)

### Director Meetings
**Model Rules §108:** Majority of directors in office.

**Note:** Cannot transact business without quorum throughout meeting.

---

## Proxy Voting Restrictions

**Section 43 - Key Limitations:**

| Restriction | Requirement |
|-------------|-------------|
| Distance | Member must reside >80km from meeting (or distance in rules) |
| Proxy holder | Must be a member of the association |
| Limit | Proxy holder may hold maximum 3 proxies |
| Scope | Valid only for specific meeting named in proxy |
| Form | Written, signed, specifies meeting |

**Co-op OS implication:** Proxy features should:
- Verify distance eligibility
- Track proxy assignments per holder (max 3)
- Expire after named meeting
- Generate compliant proxy forms

---

## Voting Methods

### Show of Hands (Default)
**Model Rules §78:** Unless poll demanded, voting by show of hands.

**Declaration by chair:** Conclusive evidence of result without recording individual votes.

### Poll (Ballot)
**Model Rules §80:** May be demanded by:
- Chair, OR
- At least 3 members present, OR
- One or more members holding 10%+ of membership shares

**When demanded:** Taken immediately (or as chair directs).

**Records:** Individual votes must be recorded.

### Electronic Voting
**Section 149:** Meetings may be held:
- Entirely by telephone/electronic means
- Partially electronic (some in person, some remote)

**Requirement:** All participants must be able to communicate with each other.

---

## Specific Voting Scenarios

### Director Elections

**Model Rules approach:**
- Nominations: 7+ days before meeting (§89)
- Separate vote for each position (§93)
- If only one nominee per position: elected by acclamation (§93(b))
- Multiple nominees: highest vote count wins (§94)
- Tie: decided by lot (§95)

**Alternative methods if rules specify:**
- Slate voting
- Cumulative voting
- Approval voting

### Director Removal

**Section 82:** Requires special resolution.

**OR** rules may provide for removal by 3/4 majority ordinary resolution.

**Notice to director:** Must receive copy of resolution and have opportunity to make representations.

### Member Termination

**Termination decision (s.34(5)):** 3/4 majority of all directors at meeting called for that purpose.

**Appeal vote at general meeting (s.37):**
- "Conduct detrimental": Special resolution to confirm
- "Material breach" or "non-payment": Ordinary resolution to confirm

### Bylaw Amendments

**Section 68(2):** Special resolution required.

**Investment shareholder protection (s.70):** Cannot prejudice class rights without separate resolution of that class.

---

## Co-op OS Decision Tracking

### For Each Decision, Track:

```yaml
decision:
  id: unique_identifier
  type: ordinary | special | separate | consent
  subject: brief_description
  date_proposed: YYYY-MM-DD
  meeting_id: reference_to_meeting
  notice_given: YYYY-MM-DD
  notice_method: email | mail | posted
  text: full_resolution_text
  
voting:
  eligible_members: count
  quorum_required: count
  quorum_present: count
  votes_for: count
  votes_against: count
  abstentions: count
  threshold_required: percentage
  threshold_achieved: percentage
  
result:
  passed: boolean
  certified_by: chair_name
  recorded_date: YYYY-MM-DD
  effective_date: YYYY-MM-DD
  
compliance:
  notice_compliant: boolean
  quorum_met: boolean
  threshold_met: boolean
  appeals_period: if_applicable
```

### Decision Templates

**Standard motions library:**
- Director election
- Director removal
- Auditor appointment
- Financial statement approval
- Bylaw amendment
- Member admission
- Member termination
- Patronage allocation
- Reserve allocation
- Borrowing authorization

---

## Housing Cooperative Special Rules

### Higher Thresholds
**Section 1 (special resolution):** 3/4 majority instead of 2/3.

### Termination Appeals
**Section 37(3):** Member may appeal to BC Supreme Court within 30 days of general meeting decision.

### Possession Orders
**Section 172:** Housing co-op may apply to court for possession.
**Section 172.1:** Terminated member may apply to court regarding tenancy.

---

## Common Voting Errors to Prevent

| Error | Consequence | Co-op OS Prevention |
|-------|-------------|---------------------|
| Insufficient notice | Decision invalid | Automated notice period checks |
| Wrong threshold applied | Decision invalid | Resolution type enforcement |
| No quorum | Decision invalid | Real-time quorum tracking |
| Proxy limit exceeded | Votes invalid | Proxy assignment limits |
| Non-member proxy holder | Proxy invalid | Membership verification |
| No text for special resolution | Resolution invalid | Required field for special resolutions |

---

## Quick Reference: What Vote Type?

| Action | Vote Type | Threshold |
|--------|-----------|-----------|
| Approve financial statements | Ordinary | 50%+1 |
| Elect directors | Ordinary (usually) | Plurality |
| Remove director | Special | 2/3 (or 3/4 if rules) |
| Amend bylaws | Special | 2/3 (or 3/4 housing) |
| Terminate member (confirm) | Ordinary or Special | Depends on grounds |
| Appoint auditor | Ordinary | 50%+1 |
| Remove auditor | Special | 2/3 |
| Allocate patronage | Ordinary | 50%+1 |
| Borrow money (above limit) | Special (if rules require) | 2/3 |
| Dissolve association | Special | 2/3 (or 3/4 housing) |
| Change name | Special | 2/3 |
| Substantial disposition | Special + Separate | Multiple votes |

---

*Reference v1.0 · February 2026*
*Source: BC Cooperative Association Act (SBC 1999, c.28)*
