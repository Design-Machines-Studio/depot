# Workflow Kernel Runtime Resolution

This is the single security-sensitive resolution contract for every consumer
(pipeline, dm-review, and any future orchestrator). Do not copy this contract
into consuming plugins; link here and keep only plugin-specific artifact paths
inline.

## The launcher is the only entry point

Invoke the kernel exclusively through `workflow-kernel-launcher.sh` (this
directory). The Python package under `references/workflow_kernel/` is not
importable from a project working directory; a bare `python3 -m
workflow_kernel` fails with `ModuleNotFoundError` everywhere except a
correctly prepared `PYTHONPATH`. The launcher owns runtime resolution,
interpreter verification (Python 3.12+ on a fixed `PATH`), module-path setup,
and then execs `python3 -m workflow_kernel "$@"`. Inline Python source is
forbidden; use only the stable CLI subcommands.

Resolve one launcher copy per run and reuse it:

```sh
WORKFLOW_KERNEL=""
for CANDIDATE in \
  "<depot-checkout>/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh" \
  "$HOME"/.claude/plugins/cache/depot/workflow-kernel/*/skills/workflow-kernel/references/workflow-kernel-launcher.sh \
  "$HOME"/.codex/plugins/cache/depot/workflow-kernel/*/skills/workflow-kernel/references/workflow-kernel-launcher.sh; do
  if [ -x "$CANDIDATE" ]; then WORKFLOW_KERNEL="$CANDIDATE"; break; fi
done
```

Use the depot-checkout candidate only when the consuming plugin itself
executes from a depot repository checkout; otherwise omit it. Any launcher
copy is sufficient: the launcher itself re-resolves the newest compatible
runtime (its own repo checkout first, then semver-sorted -- never
mtime-sorted -- versioned cache directories under `~/.claude` then
`~/.codex`), so a stale launcher copy still runs the newest installed kernel.

The launcher is the normative enforcement point for every trust boundary
below, in validate-before-execute order: realpath containment, plugin
manifest name/version checks (a cache candidate's declared version must equal
its directory segment), and semver compatibility all pass BEFORE the
importability probe executes any candidate code. It also unsets caller
`PYTHONPATH`/`PYTHONHOME`/`PYTHONSTARTUP` up front and hop-bounds its own
symlink-path resolution (a cycle exits `4`, never hangs). The Python
`resolve_workflow_kernel_runtime` helper in `cli.py` is the validator-side
mirror of the same rules (used by `tools/validate-workflow-kernel.py`); it
never launches the runtime.

## Trust boundaries (fail closed)

- Accept an in-repository runtime only beneath the same canonical Depot
  repository realpath as the executing plugin; otherwise use only versioned
  `workflow-kernel` entries under `~/.claude/plugins/cache/depot/` and then
  `~/.codex/plugins/cache/depot/`.
- Version compatibility is semantic: same-major versions at or above the
  declared `>=0.1.0` floor. Candidates are ordered by their parsed semver
  path segment, newest first, and the plugin manifest's declared name and
  version must match. Reject symlink escapes, project-cwd/PATH discovery,
  and incompatible plugin name/version metadata.
- Initialize each run at `.workflow-kernel/runs/<run-id>`; the kernel derives
  the nearest real Git repository from the state directory and binds the
  canonical `.workflow-kernel` root to an immutable random scope ID plus
  repository/root device and inode. No caller-selected lease root is
  accepted. Symlink, cross-repository, scope-metadata, and run-directory
  mismatches fail closed.
- If the launcher, runtime, or any observation step is unavailable or
  incompatible, preserve the authoritative Markdown result and record
  `shadow unavailable` with a safe reason. Launcher exit `4` means runtime
  unavailable; the kernel's stable exits are `0` success, `2` invalid
  input/schema, `3` unsafe/blocked, `4` unavailable/incompatible, `5` parity
  gap, `6` write/state conflict. None authorizes changing the canonical
  result.
