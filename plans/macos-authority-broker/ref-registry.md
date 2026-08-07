# Pipeline Ref Registry

Feature: `macos-authority-broker`
Execution branch: `ai/workflow-authority-linux-m1`
Base: `main` at `8accfdedde83e43781b18fce37a9b97c64ba3f4b`

The pre-existing dirty worktree at
`/Users/trav/.codex/worktrees/f43c/depot` is excluded from execution and must
remain untouched. Its branch is `ai/macos-authority-broker`.

## Created this run

| Ref | Kind | Created at step | Base |
|---|---|---|---|
| `.worktrees/pipeline/macos-authority-broker/feature` | worktree | preflight | `main` |
| `ai/workflow-authority-linux-m1` | feature-branch | preflight | `main` |
| `.worktrees/pipeline/macos-authority-broker/01-contract-vectors-fake` | worktree | chunk 01 step 3b | `ai/workflow-authority-linux-m1` |
| `pipeline/macos-authority-broker/01-contract-vectors-fake` | chunk-branch | chunk 01 step 3b | `ai/workflow-authority-linux-m1` |
| `.worktrees/pipeline/macos-authority-broker/02-linux-authority-core` | worktree | level 1 chunk 02 | feature merge `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `pipeline/macos-authority-broker/02-linux-authority-core` | chunk-branch | level 1 chunk 02 | feature merge `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `.worktrees/pipeline/macos-authority-broker/03-depot-adapter` | worktree | level 1 chunk 03 | feature merge `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `pipeline/macos-authority-broker/03-depot-adapter` | chunk-branch | level 1 chunk 03 | feature merge `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `.worktrees/pipeline/macos-authority-broker/04-provider-transport` | worktree | level 2 chunk 04 | feature merge `58544b23ab0a2d0aaa3de921b19187301f8e43fd` |
| `pipeline/macos-authority-broker/04-provider-transport` | chunk-branch | level 2 chunk 04 | feature merge `58544b23ab0a2d0aaa3de921b19187301f8e43fd` |
| `.worktrees/pipeline/macos-authority-broker/05-linux-packaging-admin` | worktree | level 3 chunk 05 | feature merge `cee8be3637bfc6fb7ee17684abef144d08c0b323` |
| `pipeline/macos-authority-broker/05-linux-packaging-admin` | chunk-branch | level 3 chunk 05 | feature merge `cee8be3637bfc6fb7ee17684abef144d08c0b323` |
| `.worktrees/pipeline/macos-authority-broker/04b-ipc-composition` | worktree | serial dependency repair after chunk 05 review | reviewed chunk head `0d879511a8382938a4c164d8f4911d90507f64b4` |
| `pipeline/macos-authority-broker/04b-ipc-composition` | stacked repair branch | serial dependency repair after chunk 05 review | reviewed chunk head `0d879511a8382938a4c164d8f4911d90507f64b4` |
| `.worktrees/pipeline/macos-authority-broker/04b-daemon-server` | worktree | parallel IPC composition after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `pipeline/macos-authority-broker/04b-daemon-server` | stacked repair branch | parallel IPC composition after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `.worktrees/pipeline/macos-authority-broker/04b-client-verifier` | worktree | parallel IPC composition after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `pipeline/macos-authority-broker/04b-client-verifier` | stacked repair branch | parallel IPC composition after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `.worktrees/pipeline/macos-authority-broker/04b-fido-enrollment` | worktree | parallel enrollment dependency after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `pipeline/macos-authority-broker/04b-fido-enrollment` | stacked repair branch | parallel enrollment dependency after contract freeze | reviewed contract head `21e01362a5dc18879574654a7cd30211cbed2109` |
| `.worktrees/pipeline/macos-authority-broker/04c-adapter-terminal-outcomes` | worktree | terminal-outcome retry repair after client review | composition head `b567d73` |
| `pipeline/macos-authority-broker/04c-adapter-terminal-outcomes` | stacked repair branch | terminal-outcome retry repair after client review | composition head `b567d73` |
| `.worktrees/pipeline/macos-authority-broker/04d-runtime-composition` | worktree | production runtime join after daemon/client/enrollment review | composition head `ba15b7f` |
| `pipeline/macos-authority-broker/04d-runtime-composition` | stacked repair branch | production runtime join after daemon/client/enrollment review | composition head `ba15b7f` |
| `.worktrees/pipeline/macos-authority-broker/04e-signed-terminal-outcomes` | worktree | signed post-send failure/unknown repair after adapter review | composition head `ba15b7f` |
| `pipeline/macos-authority-broker/04e-signed-terminal-outcomes` | stacked repair branch | signed post-send failure/unknown repair after adapter review | composition head `ba15b7f` |

## Before-state summary

- Worktrees registered before this run: 9
- Execution-namespace worktrees before this run: 0
- Execution-namespace branches before this run: 0

## Dispositions

| Ref | Disposition | Evidence |
|---|---|---|
| `.worktrees/pipeline/macos-authority-broker/01-contract-vectors-fake` | removed after clean merge | chunk `a15fc0c2eec6b9f7cddac19841ed83f920656042`; feature merge `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `pipeline/macos-authority-broker/01-contract-vectors-fake` | deleted after ancestry proof | `a15fc0c2eec6b9f7cddac19841ed83f920656042` is an ancestor of `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `.worktrees/pipeline/macos-authority-broker/feature` | retained for remaining chunks | clean at `2c01f108f71b86204d4377ae2de1c22b8a818cc3` |
| `ai/workflow-authority-linux-m1` | retained for remaining chunks | Chunk 01 merged; no push or PR |
| `.worktrees/pipeline/macos-authority-broker/03-depot-adapter` | removed after clean merge | chunk head `dd1e94861aeae8227d5fc41dab7f376409dce49c`; feature merge `617195948a5315f31a2de851dae4d09fde25379f` |
| `pipeline/macos-authority-broker/03-depot-adapter` | deleted after ancestry proof | `dd1e94861aeae8227d5fc41dab7f376409dce49c` is an ancestor of `617195948a5315f31a2de851dae4d09fde25379f` |
| `.worktrees/pipeline/macos-authority-broker/feature` | retained for remaining chunks | clean at `617195948a5315f31a2de851dae4d09fde25379f`; Chunk 03 merged |
| `ai/workflow-authority-linux-m1` | retained for remaining chunks | Chunks 01 and 03 merged locally; no push or PR |
| `.worktrees/pipeline/macos-authority-broker/02-linux-authority-core` | removed after clean merge | chunk head `dcb53938c65dfd18e655d72a65f1278a68c57667`; feature merge `58544b23ab0a2d0aaa3de921b19187301f8e43fd` |
| `pipeline/macos-authority-broker/02-linux-authority-core` | deleted after ancestry proof | `dcb53938c65dfd18e655d72a65f1278a68c57667` is an ancestor of `58544b23ab0a2d0aaa3de921b19187301f8e43fd` |
| `.worktrees/pipeline/macos-authority-broker/feature` | retained for remaining chunks | clean at `58544b23ab0a2d0aaa3de921b19187301f8e43fd`; Level 1 integrated |
| `ai/workflow-authority-linux-m1` | retained for remaining chunks | Chunks 01, 02, and 03 merged locally; no push or PR |
| `.worktrees/pipeline/macos-authority-broker/04-provider-transport` | removed after clean merge | chunk head `8819ff18811f41391939ae8299dd0eceed00720b`; feature merge `cee8be3637bfc6fb7ee17684abef144d08c0b323` |
| `pipeline/macos-authority-broker/04-provider-transport` | deleted after ancestry proof | `8819ff18811f41391939ae8299dd0eceed00720b` is an ancestor of `cee8be3637bfc6fb7ee17684abef144d08c0b323` |
| `.worktrees/pipeline/macos-authority-broker/feature` | retained for remaining chunks | clean at `cee8be3637bfc6fb7ee17684abef144d08c0b323`; Chunk 04 integrated |
| `ai/workflow-authority-linux-m1` | retained for remaining chunks | Chunks 01 through 04 merged locally; no push or PR |
