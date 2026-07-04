# Development Guide

This guide covers how to set up a local development environment, run tests, and manage code quality for **azure-functions-durable-graph**, using Hatch and a Makefile for workflow automation.

---

## Prerequisites

- **Python 3.10+**
- **Git**
- **Hatch** (`pip install hatch`)
- **Make**
- **git-cliff** for changelog generation

---

## Project Structure

```text
azure-functions-durable-graph/
├── src/
│   └── azure_functions_durable_graph/
│       ├── __init__.py
│       ├── app.py
│       ├── contracts.py
│       ├── manifest.py
│       ├── registry.py
│       └── adapters/
│           └── __init__.py
├── tests/
├── examples/
├── docs/
├── infra/
├── .github/
│   └── workflows/
├── cliff.toml
├── Makefile
├── pyproject.toml
├── CHANGELOG.md
└── README.md
```

- **`Makefile`** — common commands for environment setup, testing, linting, releasing, and publishing.
- **`pyproject.toml`** — Hatch environments, project metadata, and tool configuration.
- **`cliff.toml`** — git-cliff configuration for changelog generation from conventional commits.
- **`src/azure_functions_durable_graph/`** — core library code.
- **`tests/`** — unit and integration tests.
- **`docs/`** — documentation files served by MkDocs.

---

## Initial Setup

1. **Clone the repository**:
    ```bash
    git clone https://github.com/yeongseon/azure-functions-durable-graph-python.git
    cd azure-functions-durable-graph
    ```

2. **Create environment and install dependencies**:
    ```bash
    make install
    ```

3. **Install pre-commit hooks**:
    ```bash
    make precommit-install
    ```

---

## Pre-commit Hooks

This project uses pre-commit to ensure consistent code quality across formatting, linting, typing, and security.

| Tool   | Version  | Purpose                        |
|--------|----------|--------------------------------|
| ruff   | v0.15.7  | Formatter + linter + import sorter |
| mypy   | v1.19.1  | Static type checker            |
| bandit | 1.9.4    | Security checker on `src/` only |

### Run Hooks Manually

```bash
make precommit
```

---

## Development Workflow

1. **Create a feature branch**:
    ```bash
    git checkout -b feature/your-description
    ```

2. **Implement changes** in `src/azure_functions_durable_graph/` and add tests in `tests/`.

3. **Run quality checks** locally:
    ```bash
    make check-all
    ```

4. **Commit changes** with [Conventional Commits](https://www.conventionalcommits.org/) format:
    ```bash
    git commit -m "feat: add new node type"
    ```

5. **Push and open a Pull Request** to `main`.

---

## Makefile Targets

Use these as the **golden commands** for local validation and CI parity. Prefer `make` targets over direct tool commands.

| Target | Description |
|--------|-------------|
| `make install` | Create Hatch env and install pre-commit hooks |
| `make format` | Format code (ruff) |
| `make lint` | Run linter (ruff + mypy) |
| `make typecheck` | Run mypy type checking |
| `make security` | Run Bandit security scan |
| `make test` | Run pytest |
| `make cov` | Run tests with coverage |
| `make check` | Run lint + typecheck |
| `make check-all` | Run lint + typecheck + test |
| `make build` | Build package |
| `make changelog` | Regenerate CHANGELOG.md via git-cliff |
| `make release-patch` | Bump patch version + changelog + tag |
| `make release-minor` | Bump minor version + changelog + tag |
| `make release-major` | Bump major version + changelog + tag |
| `make publish-pypi` | Publish to PyPI |
| `make publish-test` | Publish to TestPyPI |
| `make precommit` | Run all pre-commit hooks |
| `make precommit-install` | Install pre-commit hooks |
| `make doctor` | Show environment diagnostic info |
| `make clean` | Remove build artifacts |
| `make clean-all` | Deep clean (caches, coverage, venv) |

---

## Tips

- Ensure you're using Python 3.10+.
- Use `make check-all` before committing to validate your changes.
- Prefer `make` commands to ensure consistent dev experience across platforms.
- Follow Conventional Commits for proper changelog generation.
