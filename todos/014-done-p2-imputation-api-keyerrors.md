# 014 P2: imputation API raises on documented partial inputs

- [x] Missing native matrix section leaves an unpriceable row unchanged.
- [x] Missing measurement source cannot raise and receives visible provenance when priceable.
- [x] Direct boundary tests pass.

## Evidence

`_priced_identity` now treats the native section and aliases as optional, and
provenance is assembled from present components. Direct tests reproduce both
former `KeyError` paths and pass in `tests.test_imputed_cost`.
