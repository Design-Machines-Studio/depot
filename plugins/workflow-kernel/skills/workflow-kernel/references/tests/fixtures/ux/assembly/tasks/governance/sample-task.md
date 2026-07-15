---
id: GOV-SAMPLE-001
title: Review a proposal
area: governance
feature: proposals
route: /governance/proposals/sample
requires_auth: true
auth_fields:
  - session_cookie
preconditions:
  - "A signed-in member has a proposal to review"
personas:
  - id: casual-member
    expected: FRICTION
    reason: "A live-shape descriptive explanation that is never retained"
---

# Scenario

Review the proposal and understand the next action.
