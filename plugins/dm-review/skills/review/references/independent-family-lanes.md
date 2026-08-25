# Independent-family lanes

Callers pass a run-private receipt registry plus opaque private receipt IDs,
never family names. model-router reads the private evidence and excludes every implementing family, returning only an anonymous participant and pass/fail
disposition. Mixed implementation passes all contributing receipt IDs. A
verified human-authored diff instead uses the explicit `--human-authored`
origin flag; it never fabricates a model receipt. That claim applies only while
the exact reviewed state has no model-authored contribution. Any model repair
invalidates it and requires the repair's live receipt in the run-private
registry; unavailable repair provenance keeps the lane incomplete. A missing
receipt, ambiguous origin, or exhausted independent role likewise keeps the
lane incomplete; dm-review cannot weaken or reinterpret the result.
