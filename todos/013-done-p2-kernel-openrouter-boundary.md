# 013 P2: workflow-kernel owns an OpenRouter dependency

- [x] Matrix authority is supplied by the caller as a generic trusted installed-plugin asset.
- [x] Kernel cost code contains no OpenRouter plugin name, version, or internal asset path.
- [x] Invalid or unavailable assets skip imputation without gating emission.
- [x] Focused and workflow-contract release validators pass.

## Evidence

`resolve-plugin-asset` exposes the existing coherent-bundle resolver as a
generic caller seam; `resolve_trusted_plugin_asset` revalidates the selected
path before loading. The generated contract resolves OpenRouter outside the
cost implementation, preserves resolver stderr, and passes the resulting path
to all eleven consumers. The focused 69-test suite, sync check, and
`tools/validate-workflow-contracts.sh` passed.
