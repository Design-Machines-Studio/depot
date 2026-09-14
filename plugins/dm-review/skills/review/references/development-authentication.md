# Development authentication

Inspect only the browser-discovery contract's closed root, runbook, and
verification sources for the documented development login, seed account, role,
and scenario preconditions. Use that account through the real UI. Keep secrets
out of commands, screenshots, reports, and committed evidence.

Attempt the documented path once. Missing login documentation is
`application_authentication_unavailable: login_documentation_missing`;
rejected documented credentials are `documented_credentials_rejected`; a valid
login reaching the wrong role or empty seed is `incorrect_seed_state`. None is
`browser_transport_unavailable` or `dev_server_unavailable`. Never guess a
password, bypass authorization, reset data, or manufacture an account.
