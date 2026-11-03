# Agent Playbook

## Retirement rule

**Retired and unsupported as of 2026-10-02.** No maintenance or security updates
will be provided. `yeongseon` never published an official PyPI release; history,
tags and GitHub releases are source snapshots only.

The retirement rule in `AGENTS.md` overrides the historical workflow below and
all linked development/release guides. Documentation cleanup does not authorize
feature work, dependency maintenance, release recovery, credential renewal,
publishing (including TestPyPI), or re-enabling automation. Revival requires an
explicit maintainer decision and updated, re-audited dependencies and Actions
before workflows are re-enabled, as recorded in
[PR #209](https://github.com/yeongseon/azure-functions-durable-graph-python/pull/209#issuecomment-5944447065).
Local checks may validate documentation corrections without reviving the project.

## Source Of Truth
- `AGENTS.md` for repository-wide engineering and agent rules.
- `README.md` for installation, quick start, and CLI examples.
- `CONTRIBUTING.md` for branch, commit, and release workflow.
- `pyproject.toml` and `Makefile` for supported commands.

## Repository Map
- `src/azure_functions_durable_graph/` package code.
- `tests/` graph runtime and orchestration coverage.
- `examples/` example graph applications.
- `docs/` documentation site content.

## Change Workflow
1. Confirm whether the change affects graph runtime API, orchestration behavior, manifest format, or docs only.
2. Update examples when they are used as public contract material.
3. Keep tests and docs in lockstep for public behavior changes.
4. Do not broaden supported Python versions or dependency ranges casually.

## Validation
- `make test`
- `make lint`
- `make typecheck`
- `make security`
- `make build`
