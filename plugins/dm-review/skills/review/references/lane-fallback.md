# Role-level lane fallback

Load this reference when a selected lane fails, is declined, or is unavailable.

1. Keep the logical lane and its review criteria fixed.
2. Let model-router descend within the requested role. Do not select a provider,
   model, transport, family, billing rail, or fallback order in dm-review.
3. Do not ask for approval to use another configured eligible rail.
4. Preserve any valid partial external result and dispatch only held sections.
5. For `independent-family`, pass opaque implementing receipt IDs on every
   retry. Never complete the lane with an implementing family.
6. Record the anonymous lane, role, disposition, role-level fallback reason,
   held/completed scope, and next action. Keep exact identity private.

If the role is exhausted, mark the named required lane unavailable. Ordinary
supplementary gaps are reported proportionally. A required full-diff security,
browser, build, or final-review lane stays `REVIEW INCOMPLETE`; it is never
silently waived. Pipeline's final review cannot use gap-and-continue.

Every retained P1/P2/P3 still requires repair and affected-lane recheck. Routing
failure never authorizes deferral.
