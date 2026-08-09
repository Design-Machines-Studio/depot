# 016 P3: matrix trust branches lack negative tests

- [x] Schema, date, price, ratio, cross-section, and alias failures are tested.
- [x] Tests exercise the public validator with independent mutations.
- [x] Focused tests pass.

## Evidence

`test_matrix_validation_rejects_each_trust_boundary` independently mutates
each named branch and calls `validate_model_matrix`; the focused imputation
suite passes.
