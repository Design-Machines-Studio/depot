# UX Testing Reference

*Personas and test scenarios for Co-op OS validation*

---

## Testing Philosophy

Co-op OS serves two distinct audiences with different needs:

1. **Regular worker-members** who need simplified, contextual information that helps them participate without mastering cooperative jargon
2. **Compliance-savvy members** (officers, directors, administrators) who need precise legal and financial details

Every feature must work for both. Testing validates this dual-audience design.

---

## Primary Personas

### Persona 1: Maria (Engaged Worker-Member)

**Profile:**
- Role: Worker-member, 3 years at co-op
- Tech comfort: Moderate (uses phone apps daily, laptop weekly)
- Co-op knowledge: Basic understanding, learning as she goes
- Engagement: Attends most meetings, votes regularly
- Pain points: Finds governance confusing, doesn't know what she's voting on sometimes

**Goals:**
- Know when meetings are and what she needs to do
- Understand enough to vote confidently
- Feel like an owner, not just an employee
- Not be embarrassed by asking "dumb" questions

**Testing focus:**
- Can she find when the next meeting is? (<10 seconds)
- Can she understand what a resolution means? (plain language test)
- Does she feel welcomed, not overwhelmed?
- Can she complete voting in under 2 minutes?

**Sample tasks:**
1. Find the date of the next member meeting
2. Review the agenda and identify what decisions you'll be asked to make
3. Cast a vote on a pending resolution
4. Find out how much equity you have in the co-op
5. See who the current directors are

**Success metrics:**
- Task completion rate: >95%
- Time to complete: <2 min per task
- Comprehension: Can explain decision in own words
- Satisfaction: "I feel informed" (4+ on 5-point scale)

---

### Persona 2: James (Reluctant Participant)

**Profile:**
- Role: Worker-member, 8 months at co-op
- Tech comfort: Low (prefers phone calls, minimal app use)
- Co-op knowledge: Minimal—joined for the job, not the structure
- Engagement: Attends required meetings only
- Pain points: Sees governance as bureaucracy, doesn't understand why it matters

**Goals:**
- Do the minimum required to stay in good standing
- Not feel stupid or excluded
- Understand why co-op stuff affects him
- Get in and out quickly

**Testing focus:**
- Is the bare minimum path obvious?
- Does the system explain *why* things matter, briefly?
- Can he complete required actions on his phone?
- Does anything feel patronizing or preachy?

**Sample tasks:**
1. Find out what you need to do this month (if anything)
2. Approve/submit your required monthly task
3. Find the answer to: "What happens if I don't attend the meeting?"
4. See your membership status

**Success metrics:**
- "Required actions" visibility: Found in <5 seconds
- Task completion: <90 seconds
- Emotional response: Not annoyed (3+ on 5-point scale)
- Understanding: Can state one reason governance matters

---

### Persona 3: Kenji (Board Secretary/Administrator)

**Profile:**
- Role: Board Secretary, 5 years at co-op
- Tech comfort: High (comfortable with databases, spreadsheets)
- Co-op knowledge: Deep—has read the bylaws, understands the Act
- Engagement: Manages much of the administrative work
- Pain points: Tracking everything is manual, worries about missing deadlines

**Goals:**
- Never miss a compliance deadline
- Generate accurate records and reports
- Have authoritative answers when questions arise
- Reduce time spent on administrative tasks

**Testing focus:**
- Can he set up the system with real co-op data?
- Does it correctly calculate/display compliance status?
- Can he generate required documents (minutes, reports)?
- Is the audit trail complete?

**Sample tasks:**
1. Enter a new member's information and shares
2. Record a board meeting and its decisions
3. Generate the annual report filing
4. Check compliance status for all statutory requirements
5. Find the exact bylaw provision that governs a specific situation
6. Process a member withdrawal and share redemption

**Success metrics:**
- Data entry accuracy: 100% (validation catches errors)
- Compliance dashboard: Shows all 8 key deadlines correctly
- Document generation: Produces valid, complete documents
- Time savings: >50% reduction vs. previous method

---

### Persona 4: Diane (Board Chair)

**Profile:**
- Role: Board Chair, elected 2 years ago
- Tech comfort: Moderate
- Co-op knowledge: Good working knowledge, not expert
- Engagement: Leads meetings, represents co-op externally
- Pain points: Needs to answer questions she doesn't always know, feels responsible for everything

**Goals:**
- Run effective meetings
- Ensure the co-op stays compliant
- Develop other members as future leaders
- Make good decisions with the information available

**Testing focus:**
- Can she prepare for meetings efficiently?
- Does the system support meeting facilitation?
- Can she delegate with confidence (knows who's responsible for what)?
- Does she have a clear view of overall governance health?

**Sample tasks:**
1. Prepare the agenda for next board meeting
2. Check who's responsible for each outstanding task
3. Review the compliance dashboard before AGM
4. Find guidance on how to handle a member dispute
5. See director term expirations and succession needs

**Success metrics:**
- Meeting prep time: <30 minutes
- Compliance confidence: "I know where we stand" (4+ on 5-point scale)
- Delegation clarity: Can name who owns each area
- Decision support: "I have what I need to decide" (4+)

---

### Persona 5: New Member (Onboarding Test)

**Profile:**
- Role: Just approved for membership, hasn't completed onboarding
- Tech comfort: Variable (test with low, medium, high)
- Co-op knowledge: Nearly zero—knows they're joining a co-op, that's about it
- Pain points: Confused about what they've signed up for

**Goals:**
- Understand what being a member means
- Complete required onboarding steps
- Feel welcomed, not overwhelmed
- Start participating

**Testing focus:**
- Is the onboarding flow clear and sequential?
- Does it explain co-op basics without being patronizing?
- Can they complete share purchase and agreements?
- Do they know what's expected of them going forward?

**Sample tasks:**
1. Complete your new member onboarding (end-to-end)
2. Find and sign the membership agreement
3. Purchase your membership shares
4. Understand your voting rights
5. Find your first meeting date

**Success metrics:**
- Onboarding completion: >90% (don't abandon)
- Time to complete: <15 minutes
- Comprehension quiz: 4/5 correct on basic co-op facts
- Sentiment: "I feel welcome" (4+ on 5-point scale)

---

## Secondary Personas

### Persona 6: Former Member (Exit Test)

Testing the offboarding experience:
- Can they initiate withdrawal?
- Is the share redemption process clear?
- Are all obligations documented?
- Is the exit respectful?

### Persona 7: External Stakeholder (Auditor/Advisor View)

Testing read-only access for external parties:
- Can auditor access financial records needed?
- Can legal advisor review governance documents?
- Is sensitive member info appropriately restricted?

### Persona 8: Housing Co-op Member (Specialized)

Additional scenarios for housing co-op variant:
- Occupancy-related tasks
- Rent/housing charge visibility
- Housing-specific termination procedures
- Possession and appeal processes

**Key statutory differences to test:**
- Special resolution threshold: 3/4 (not 2/3) per s.1 definition
- Member termination: Court appeal rights within 2 months (s.35.1)
- Possession orders: Residential Tenancy Branch involvement
- Occupancy agreements vs membership agreements
- Housing charge arrears as termination ground

---

## Test Scenario Library

### Governance Scenarios

**G1: Resolution Workflow**
```yaml
scenario: Pass a special resolution
personas: [Maria, Kenji, Diane]
steps:
  1. Board proposes bylaw amendment
  2. Notice sent to members (14 days)
  3. Members review full resolution text
  4. Meeting held, discussion occurs
  5. Vote conducted (need 2/3 majority; 3/4 for housing co-ops)
  6. Result recorded
  7. Filing completed (if required)
  
validation:
  - Notice period calculated correctly?
  - Resolution text visible to all members?
  - Voting threshold enforced correctly for co-op type?
    - Standard co-op: 2/3 majority (s.1 definition)
    - Housing co-op: 3/4 majority (s.1 definition)
  - Results documented?
```

**G2: Director Election**
```yaml
scenario: Elect two directors at AGM
personas: [Maria, Kenji, Diane]
steps:
  1. Nominations open (7+ days before meeting)
  2. Candidates identified
  3. Meeting held
  4. Election conducted
  5. Results declared
  6. Registrar filing completed (14 days)
  
validation:
  - Nomination deadline tracked?
  - Election method matches rules?
  - Results correctly recorded?
  - Filing reminder triggered?
```

**G3: Emergency Decision**
```yaml
scenario: Board needs to make urgent decision between meetings
personas: [Kenji, Diane]
steps:
  1. Issue arises requiring immediate action
  2. Written resolution circulated
  3. All directors consent in writing
  4. Decision recorded as consent resolution
  
validation:
  - Consent resolution process documented?
  - All director signatures/consents captured?
  - Same legal effect as meeting decision?
```

**G4: Proxy Voting Eligibility**
```yaml
scenario: Member requests to vote by proxy at AGM
personas: [Maria (requesting proxy), Kenji]
steps:
  1. Maria requests proxy form (lives 95km from meeting location)
  2. System checks eligibility (>80km from meeting place)
  3. Proxy form generated
  4. Maria designates proxy holder (must be another member)
  5. System validates holder is a member
  6. System checks holder doesn't already hold 3 proxies (max)
  7. Proxy registered before meeting
  8. At meeting, proxy votes counted
  
validation:
  - 80km distance rule enforced (s.44)?
  - Proxy holder must be member (s.44(2))?
  - Max 3 proxies per holder enforced (s.44(3))?
  - Proxy revocable until used?
  - Clear error if rules don't permit proxies?
```

**G5: Conflict of Interest Disclosure**
```yaml
scenario: Director has material interest in proposed contract
personas: [Diane (conflicted director), Kenji]
steps:
  1. Contract discussion added to board agenda
  2. Diane recognizes potential conflict
  3. Diane discloses interest before discussion
  4. System records disclosure with details
  5. Diane abstains from voting on the matter
  6. Decision recorded with abstention noted
  7. Disclosure appears in minutes
  
validation:
  - Disclosure captured before vote (s.91)?
  - Nature of interest documented?
  - Abstention from voting recorded?
  - If disclosure not made, decision voidable flagged?
  - Historical conflict disclosures searchable?
```

**G6: Electronic Meeting Participation**
```yaml
scenario: Member participates in GM via video conference
personas: [James (remote), Kenji, Diane]
steps:
  1. Meeting notice indicates electronic participation available
  2. James registers for remote participation
  3. System verifies rules permit electronic meetings (s.139)
  4. James receives connection details
  5. At meeting, James can hear and be heard
  6. James votes electronically
  7. Participation and votes recorded
  
validation:
  - Rules explicitly authorize electronic meetings?
  - Communication method allows real-time participation?
  - Electronic votes counted correctly?
  - Quorum includes electronic participants?
```

---

### Member Scenarios

**M1: New Member Joins**
```yaml
scenario: Complete new member admission
personas: [New Member, Kenji]
steps:
  1. Application submitted
  2. Board reviews and approves
  3. Member notified of approval
  4. Membership shares purchased/issued
  5. Member agreement signed
  6. Onboarding completed
  7. Added to member register
  
validation:
  - All required fields captured?
  - Share issuance recorded correctly?
  - Member register updated?
  - Welcome communications sent?
```

**M2: Member Withdraws**
```yaml
scenario: Member voluntary withdrawal
personas: [Maria, Kenji]
steps:
  1. Member submits withdrawal notice
  2. Notice period begins (per rules)
  3. Share redemption calculated
  4. Solvency test performed
  5. Payment processed (or scheduled)
  6. Member removed from active register
  7. Archived in former members
  
validation:
  - Withdrawal notice period correct?
  - Share calculation accurate?
  - Solvency test recorded?
  - Tax documents generated (if needed)?
```

**M3: Member Terminated (Contested)**
```yaml
scenario: Terminate member for conduct detrimental
personas: [James (as terminated), Kenji, Diane]
steps:
  1. Conduct documented
  2. Notice to member (7 days before board meeting)
  3. Board meeting held, member may attend
  4. 3/4 directors approve termination
  5. Member appeals to general meeting
  6. Vote on appeal (threshold depends on grounds)
  7. (Housing: court appeal possible within 2 months)
  
validation:
  - Notice period enforced (7 days)?
  - Board vote threshold correct (3/4)?
  - Appeal rights communicated with deadline?
  - Appeal vote threshold correct for grounds:
    - "Conduct detrimental" (s.35(2)(b)): Special resolution to confirm
    - "Material breach" (s.35(2)(a)): Ordinary resolution to terminate
  - Share redemption handled appropriately?
  - Housing co-op: Court appeal rights explained (2-month window)?
```

---

### Financial Scenarios

**F1: Patronage Allocation**
```yaml
scenario: Year-end patronage distribution
personas: [Kenji, Diane]
steps:
  1. Year-end surplus calculated
  2. Reserve allocation applied (per rules)
  3. Patronage formula applied
  4. Member-level allocations calculated
  5. Cash vs. retained split determined
  6. Solvency test performed
  7. Board approves allocation
  8. Members notified
  9. Distributions processed
  
validation:
  - Reserve calculation matches rules?
  - Patronage formula correctly applied?
  - Individual allocations sum to total?
  - Solvency test passed before payment?
```

**F2: Share Redemption During Tight Cash**
```yaml
scenario: Member withdraws but co-op cash is tight
personas: [Maria (withdrawing), Kenji]
steps:
  1. Withdrawal notice received
  2. Share redemption amount calculated
  3. Solvency test performed → marginal result
  4. System flags for board review
  5. Board considers redemption timeline
  6. Member notified of timeline per rules
  
validation:
  - Solvency test prevents insolvency?
  - Rules-based timeline options presented?
  - Member communication documented?
```

---

### Compliance Scenarios

**C1: AGM Preparation**
```yaml
scenario: Complete AGM preparation workflow
personas: [Kenji, Diane]
steps:
  1. AGM date selected (within 15 months)
  2. Financial statements prepared
  3. Auditor report received (if applicable)
  4. Notice prepared with all agenda items
  5. Financial statements sent (10 days before)
  6. Meeting notice sent (14 days for special resolutions)
  7. AGM held
  8. Minutes recorded
  9. Annual report filed (within 2 months)
  
validation:
  - All deadlines calculated correctly?
  - Document distribution tracked?
  - Required items on agenda?
  - Post-AGM filing reminder active?
```

**C2: Director Change Filing**
```yaml
scenario: Director resigns, need to file and replace
personas: [Kenji, Diane]
steps:
  1. Resignation received
  2. Recorded with effective date
  3. Filing deadline calculated (14 days)
  4. System checks residency compliance post-change
  5. Registrar notice prepared
  6. Filing submitted
  7. Vacancy filled (per rules)
  8. New director filing prepared
  
validation:
  - 14-day filing deadline enforced?
  - Vacancy handling per rules?
  - Director count still ≥3?
  - Majority still Canadian?
  - At least 1 BC resident remains?
  - Non-member director ratio still ≤1/5 (if applicable)?
  - System alerts if any requirement violated?
```

**C3: Critical Member Count Alert**
```yaml
scenario: Member withdrawal would drop count below minimum
personas: [Maria (withdrawing), Kenji, Diane]
steps:
  1. Co-op currently has exactly 3 members
  2. Maria submits withdrawal notice
  3. System detects this would violate s.10 (minimum 3 members)
  4. CRITICAL ALERT displayed to admin and board
  5. System blocks automatic processing
  6. Board notified of statutory violation risk
  7. Options presented: recruit new member or dissolution path
  
validation:
  - Alert triggered before violation occurs?
  - Alert severity clearly communicated (CRITICAL)?
  - Withdrawal blocked until resolved?
  - Guidance provided on resolution options?
  - Audit trail of alert and response?
```

**C4: Investment Shareholder Separate Vote**
```yaml
scenario: Resolution affecting investment share rights
personas: [Kenji, Diane]
steps:
  1. Board proposes resolution affecting share dividend rights
  2. System identifies this affects investment shareholders
  3. Two-track voting initiated (members + investment shareholders)
  4. Notice sent to both groups
  5. Votes collected separately
  6. Results require majority in BOTH classes
  7. Combined result recorded
  
validation:
  - System correctly identifies "class vote" triggers?
  - Separate vote tracking maintained?
  - Both majorities required for passage (s.59)?
  - Clear display of dual voting results?
```

---

## Testing Protocol

### Pre-Test Setup

1. **Clean test environment** with realistic sample data
2. **Persona briefing** - tester understands who they're playing
3. **Task list** - clear, numbered tasks
4. **Recording setup** - screen capture + think-aloud audio
5. **Success criteria** defined for each task

### During Test

1. **Think aloud** - tester narrates their process
2. **No hints** unless stuck >3 minutes
3. **Note emotions** - frustration, confusion, delight
4. **Time each task**
5. **Record exact error messages** and dead ends

### Post-Test Debrief

1. **Task success/failure** - did they complete it?
2. **Comprehension check** - can they explain what they did?
3. **Satisfaction rating** - 1-5 scale per task and overall
4. **What was confusing?** - open-ended
5. **What worked well?** - open-ended
6. **Would you use this?** - final verdict

---

## Scoring Framework

### Task Completion Score

| Score | Definition |
|-------|------------|
| 0 | Could not complete, gave up |
| 1 | Completed with significant assistance |
| 2 | Completed with minor hints |
| 3 | Completed independently but with difficulty |
| 4 | Completed smoothly with minor friction |
| 5 | Completed effortlessly |

### Comprehension Score

| Score | Definition |
|-------|------------|
| 0 | Cannot explain what they did |
| 1 | Vague understanding |
| 2 | Partial understanding |
| 3 | Good working understanding |
| 4 | Clear, accurate explanation |
| 5 | Could teach others |

### Satisfaction Score

| Score | Definition |
|-------|------------|
| 1 | Frustrated, would not use |
| 2 | Difficult, might use if required |
| 3 | Neutral, acceptable |
| 4 | Good, would use willingly |
| 5 | Excellent, would recommend |

---

## Testing Cadence

### Pre-Pilot

- **Week 1-2:** Internal testing with all 5 primary personas (team plays roles)
- **Week 3-4:** 2-3 external testers per persona type
- **Week 5:** Synthesize findings, prioritize fixes

### During Pilot

- **Monthly:** Quick satisfaction check with real users
- **Quarterly:** Full scenario testing with pilot co-op members
- **Post-pilot:** Comprehensive evaluation

### Ongoing

- **Per release:** Regression testing on critical paths
- **Quarterly:** New scenario testing as features added
- **Annually:** Full persona review (are personas still accurate?)

---

## Accessibility Requirements

Every test validates:

1. **Screen reader compatibility** - can navigate with VoiceOver/NVDA
2. **Keyboard navigation** - all functions accessible without mouse
3. **Color contrast** - meets WCAG AA (4.5:1 for text)
4. **Font sizing** - readable at 200% zoom
5. **Mobile responsive** - all critical functions work on phone
6. **Plain language** - Flesch-Kincaid grade level <10 for member-facing text

---

## Quick Reference: What to Test When

| New Feature | Personas to Test | Key Scenarios |
|-------------|------------------|---------------|
| Voting module | Maria, James, Diane | G1, G2, G4 |
| Member management | New Member, Kenji | M1, M2, M3 |
| Financial tracking | Kenji, Diane | F1, F2 |
| Compliance dashboard | Kenji, Diane | C1, C2, C3, C4 |
| Meeting management | Maria, Diane, Kenji | G1, G2, C1, G6 |
| Onboarding flow | New Member | M1, comprehension |
| Proxy voting | Maria, Kenji | G4 |
| Conflict of interest | Diane, Kenji | G5 |
| Remote participation | James, Kenji | G6 |
| Critical alerts | Kenji, Diane | C3 |
| Investment shares | Kenji | C4 |

---

*Reference v1.0 · February 2026*
*For Co-op OS development and validation*
