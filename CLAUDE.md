@docs/rtk.md
@docs/skills.md
@docs/claude-mem.md

## Branching — Mandatory

When running multiple tasks (e.g. implementing a feature, fixing several bugs, or executing a plan with more than one step), **always create a new git branch first**:

```bash
rtk git checkout -b <type>/<short-description>
```

Use conventional branch names: `feat/`, `fix/`, `chore/`, `refactor/`. Never commit multi-task work directly to `main`.

## TDD — Mandatory

Write failing test → confirm fail → minimal code to pass → confirm pass → refactor. No exceptions.

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
