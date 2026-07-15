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

Resolve one launcher copy per run from the exact trusted workflow-kernel plugin
root supplied by the host's dependency loader, then reuse it. Never glob cache
directories for an executable launcher: executing a candidate is already a
trust decision.

```sh
WORKFLOW_KERNEL="<trusted workflow-kernel plugin root>/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
[ -x "$WORKFLOW_KERNEL" ] || exit 4
```

The host dependency loader owns that trusted root. In a Depot checkout it is
the repository's `plugins/workflow-kernel` root; in an installed environment
it is the exact dependency instance selected and manifest-validated by the
host. The launcher then uses the shared side-effect-free Python resolver to
select the newest compatible runtime (repository sibling first, then
semver-sorted caches under `~/.claude` and `~/.codex`). Installed launchers
derive that account root from their own canonical cache path; repository
launchers use the operating-system account database. Caller-supplied `HOME`
never selects executable code.

The dependency-neutral `workflow_kernel/runtime_resolution.py` module is the
single policy owner. The launcher runs its trusted copy with Python isolated
mode, receives only fully canonical candidate paths, and probes them in order.
It validates the manifest, references directory, package, every package
symlink, bootstrap resolver, initializer, and entry point beneath the plugin
root before any candidate code executes. The same resolver functions are
imported by `cli.py` for validation. The launcher also
starts Bash in privileged isolation, uses Python `-I`, unsets caller startup
variables, and hop-bounds its own symlink path (a cycle exits `4`).

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
