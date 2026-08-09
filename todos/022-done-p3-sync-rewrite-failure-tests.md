# 022 P3: sync rewrite-stage failures need durable coverage

- [x] Missing and duplicate invocation flags repair to one canonical flag.
- [x] Missing and duplicate resolution lines repair to one canonical line.
- [x] A missing repository-commit insertion marker fails closed.
- [x] Rewrite-stage failure leaves the affected consumer unchanged.
- [x] Focused tests and workflow contracts pass.

## Evidence

The isolated fixture tests execute the real synchronizer and cover normalization
of missing and duplicate flags and resolution lines. TDD exposed that duplicate
flags and missing repository-commit markers were previously accepted as current;
the synchronizer now counts literal flag occurrences and requires exactly one
insertion marker. The missing-marker case exits 2 with the affected consumer
byte-for-byte unchanged. All 44 focused tests and workflow contracts pass.
