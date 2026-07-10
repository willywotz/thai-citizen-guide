@context.md

# Rule

- when completed code change must update context.md then commit it
- when completed code change / merged to main must rebuild docker compose

# Multi-agent workflow (opt-in)

When the user says "implement with agents", act as the
**orchestrator**, not the implementor: dispatch `builder`/`researcher`/`verifier`/`super-advisor`
per `.claude/subagents.md`. Main owns grilling, planning, and integration (context.md + commit +
docker); Builders write code+tests, Verifier reviews with fresh context. Cap Build↔Verify at 2
rounds, then escalate. Default (no such instruction) = work in a single context.

## Critical Rules

- don't use claude worktree

## Branching — Mandatory

When running multiple tasks (e.g. implementing a feature, fixing several bugs, or executing a plan with more than one step), **always create a new git branch first**:

```bash
rtk git checkout -b <type>/<short-description>
```

Use conventional branch names: `feat/`, `fix/`, `chore/`, `refactor/`. Never commit multi-task work directly to `main`.

## CI/CD — Branch Strategy

- **`main`** — Production branch. Deploys to **prod**. Protected: **no direct pushes**; changes land **only via merged pull request**.
- **`dev`** — Development branch. Deploys to the **dev** environment.

Workflow: branch off `dev` → open a PR into `dev` for development → promote to prod by opening a PR from `dev` into `main`. Never push directly to `main`.

## TDD — Mandatory

Write failing test → confirm fail → minimal code to pass → confirm pass → refactor. No exceptions.

## Database Migrations (aerich) — Mandatory

Before creating, editing, or hand-writing ANY migration, read **[`docs/aerich-migrations.md`](docs/aerich-migrations.md)**.

The one rule that prevents our recurring breakage: **never hand-author or carry `MODELS_STATE` forward.** That base64 blob is aerich's diff baseline for the *next* `aerich migrate`; a stale one makes the next autogen emit duplicate ops (`column ... already exists`). Always regenerate it with `aerich migrate` run against a DB that has every prior migration applied:

```bash
cd backend
.venv/bin/aerich upgrade                        # apply all existing migrations first
# ...change models...
.venv/bin/aerich migrate --name <description>   # regenerates MODELS_STATE correctly
```

After `aerich migrate`, `git status` MUST show exactly one new file and nothing modified/deleted. Hand-add raw-SQL objects aerich doesn't track (`CREATE EXTENSION`, `hnsw`/`gin` expression indexes) idempotently. See the guide for the dirty-volume "already exists" fix and recovery steps.

## Development Workflow

**ALWAYS follow these steps after making code changes:**

### Go Code Changes

**Before writing any Go code** — invoke `/use-modern-go` skill first. No exceptions.

1. **Format** — Run `gofmt -w` on modified files
2. **Lint** — Run `golangci-lint run --allow-parallel-runners` to catch issues
   - **Important**: Run golangci-lint repeatedly until there are no issues (the linter has a max-issues limit and may not show all issues in a single run)
3. **Auto-fix** — Use `golangci-lint run --fix --allow-parallel-runners` to fix issues automatically
4. **Test** — Run relevant tests before committing
5. **Tidy** — After upgrading Go dependencies, run `go mod tidy` to clean up `go.mod` and `go.sum`

## Code Style

### General

- Follow Google style guides for all languages
  - [Go](https://google.github.io/styleguide/go/)
  - [HTML/CSS](https://google.github.io/styleguide/htmlcssguide.html)
  - [JavaScript](https://google.github.io/styleguide/jsguide.html)
  - [TypeScript](https://google.github.io/styleguide/tsguide.html)
  - [Python](https://google.github.io/styleguide/pyguide.html)
- Write clean, minimal code; fewer lines is better
- Prioritize simplicity for effective and maintainable software
- Only include comments that are essential to understanding functionality or convey non-obvious information

### Go

- Use standard Go error handling with detailed error messages
- Always use `defer` for resource cleanup like `rows.Close()` (sqlclosecheck)
- Avoid using `defer` inside loops (revive) — use IIFE or scope properly

## Naming

- Use American English
- Avoid plurals like "xxxList" for simplicity and to prevent singular/plural ambiguity stemming from poor design

### Imports

- Use organized imports (sorted by the import path)

### Formatting

- Use linting/formatting tools before committing

### Error Handling

- Be explicit but concise about error cases

## Pull Request Guidelines

- **Code Review** — Follow [Google's Code Review Guideline](https://google.github.io/eng-practices/)
- **Author Responsibility** — Authors are responsible for driving discussions, resolving comments, and promptly merging pull requests
- **Description** — Clearly describe what the PR changes and why
- **Testing** — Include information about how the changes were tested

## Common Go Lint Rules

Always follow these guidelines to avoid common linting errors:

- **Unused Parameters** — Prefix unused parameters with underscore (e.g., `func foo(_ *Bar)`)
- **Modern Go Conventions** — Use `any` instead of `interface{}` (since Go 1.18)
- **Confusing Naming** — Avoid similar names that differ only by capitalization
- **Identical Branches** — Don't use if-else branches that contain identical code
- **Unused Functions** — Mark unused functions with `// nolint:unused` comment if needed for future use
- **Function Receivers** — Don't create unnecessary function receivers; use regular functions if receiver is unused
- **Proper Import Ordering** — Maintain correct grouping and ordering of imports
- **Consistency** — Keep function signatures, naming, and patterns consistent with existing code
- **Export Rules** — Only export (capitalize) functions and types that need to be used outside the package
- **Linting Command** — Always run `golangci-lint run --allow-parallel-runners` without appending filenames to avoid "function not defined" errors (functions are defined in other files within the package)

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->