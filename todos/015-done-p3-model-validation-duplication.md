# 015 P3: routing and native model validation is duplicated

- [x] Shared validation owns slug, snapshot, and price checks.
- [x] Cross-section duplicate policy remains explicit.
- [x] Matrix validation tests pass.

## Evidence

`_validate_priced_models` now owns the common slug, snapshot, and finite-price
contract. The native call passes routing slugs as forbidden identities, and
the focused matrix tests pass.
