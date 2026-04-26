# AGENTS.md

## Purpose
`azure-functions-durable-graph` provides a manifest-first graph runtime for Azure Functions Python v2 applications using Durable Functions orchestration.

## Read First
- `README.md`
- `CONTRIBUTING.md`

## Working Rules
- Runtime code must remain compatible with Python 3.10+.
- Public APIs must be fully typed.
- The orchestrator must remain deterministic — all user logic runs in Durable Functions activities, never inside the orchestrator.
- Keep documentation examples, manifest builder behaviour, and tests synchronized.
- When bumping version, update `tests/test_public_api.py` to match the new version string.

## Issue Conventions

Follow these conventions when opening issues so the backlog stays consistent with sibling DX Toolkit repositories.

### Title

- Use Conventional Commit prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `ci:`, `build:`, `perf:`.
- Add a scope qualifier when it narrows the area: `feat(orchestrator):`, `docs(manifest):`, `refactor(activity):`.
- Keep the title imperative, under ~80 characters, no trailing period.
- Do **not** put `[P0]` / `[P1]` / `[P2]` (or any priority marker) in the title — priority lives in the body.

### Body

Use the following sections, in order, omitting any that do not apply:

```
## Priority: P0 | P1 | P2 (target vX.Y.Z, optional)

## Context
What problem this issue addresses and why now.

## Acceptance Checklist
- [ ] Concrete, verifiable items.

## Out of scope
- Items intentionally excluded, with links to the issues that track them.

## References
- PRs, ADRs, sibling issues, external docs.
```

### Labels

- Apply at least one of `bug`, `enhancement`, `documentation`, `chore`.
- Add `area:*` labels when they exist in the repository.
- Use `blocker` only when the issue blocks a release.

### Umbrella issues

When splitting a large piece of work into focused issues, keep the umbrella open as a tracker that links each child issue with a checkbox; close it once every child is closed or explicitly deferred.

## Validation
- `make test`
- `make lint`
- `make typecheck`
- `make build`
