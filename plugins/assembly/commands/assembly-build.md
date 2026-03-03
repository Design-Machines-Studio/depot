---
name: assembly-build
description: Build and test Assembly via Docker
argument-hint: "[optional: test, generate, or full]"
---

# Assembly Build

Run the Assembly build pipeline inside Docker.

## Modes

| Argument | What it does |
|----------|-------------|
| (none) / `full` | templ generate + go build + go test |
| `generate` | templ generate only |
| `test` | go test only |
| `build` | go build only |

## Commands

All commands run inside Docker — never bare on the host.

### Full Build (default)

```bash
docker compose exec app templ generate
docker compose exec app go build -o bin/app ./cmd/api
docker compose exec app go test ./...
```

### Generate Only

```bash
docker compose exec app templ generate
```

### Test Only

```bash
docker compose exec app go test ./...
```

### Build Only

```bash
docker compose exec app go build -o bin/app ./cmd/api
```

## On Failure

If any step fails:
1. Show the error output
2. Read the failing file if a file path is mentioned
3. Suggest a fix
4. Ask whether to apply the fix and re-run
