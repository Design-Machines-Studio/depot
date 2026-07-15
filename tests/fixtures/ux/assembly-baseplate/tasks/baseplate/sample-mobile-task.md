---
id: BP-MOBILE-001
title: Open mobile navigation
area: baseplate
feature: navigation
route: /dashboard
implementation_status: current
requires_auth: true
requires_role: member
preconditions:
  - "Viewport is set to 375x812 (mobile)"
personas:
  - id: casual-member
    expected: SUCCESS
tags:
  - mobile
  - responsive
---

# Scenario

Open the mobile drawer and navigate to the dashboard.
