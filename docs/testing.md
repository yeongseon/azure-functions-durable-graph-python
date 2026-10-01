# Testing

This guide describes the test suite for `azure-functions-durable-graph`, including how to run tests, the structure of the test suite, and guidelines for contributing new tests.

## Overview

The `azure-functions-durable-graph` project maintains a high standard of quality through a comprehensive test suite. The suite ensures that manifest building, state management, routing logic, and registry behavior work correctly across different Python versions.

- **Supported Environments**: Python 3.10, 3.11, 3.12, 3.13, and 3.14

The test suite covers unit tests for individual modules and public API surface verification.

## Running Tests

The project uses `pytest` as its primary testing framework. You can run the tests using `make` targets or directly via `hatch`.

### Using Makefile

The simplest way to run tests is using the provided `Makefile` targets:

```bash
# Run all tests
make test

# Run tests and generate a coverage report
make cov
```

The `make cov` command generates a terminal report, an XML report for CI integration, and a detailed HTML report in the `htmlcov/` directory.

### Direct Commands

If you prefer to run commands manually via `hatch`:

```bash
# Run all tests with verbose output
hatch run test

# Run tests with coverage
hatch run cov
```

To pass specific arguments to `pytest` (e.g., to run a single test file):

```bash
hatch run pytest tests/test_manifest.py
```

## Test Structure

Tests are located in the `tests/` directory and organized by the functional area they cover:

| File | Description |
| :--- | :--- |
| `test_manifest.py` | Tests manifest building, node definitions, and manifest hashing. |
| `test_registry.py` | Tests handler dispatch, state merging, route resolution, and event handling. |
| `test_public_api.py` | Verifies the public API surface and export stability. |
| `conftest.py` | Shared fixtures for the test suite. |

## Test Organization

Tests are generally organized into classes to group related functionality. Common patterns include:

- `TestManifestBuilder`: Verifies graph compilation and validation.
- `TestGraphRegistry`: Verifies handler lookup, state merge, and route resolution.
- `TestAPISurface`: Verifies public exports and version string.
- `TestRouteDecisionFactories`: Verifies `RouteDecision` convenience constructors.

## Writing New Tests

When contributing new features or fixing bugs, please follow these guidelines:

1. **Location**: Place unit tests in the file corresponding to the module being tested. If it's a new functional area, create a new `test_*.py` file.
2. **Naming**: Use descriptive names for test functions, starting with `test_`. Use class-based grouping for related tests.
3. **Async**: If testing async functionality, the project uses `asyncio_mode = "auto"` so async tests run automatically.

Example of a new test:

```python
async def test_execute_node_merges_state():
    registry = GraphRegistry()
    registry.register(my_registration)
    result = await registry.execute_node("my_graph", my_registration.manifest.graph_hash, "step_a", {"value": 0})
    assert result["value"] == 1
```

## Coverage Configuration

Coverage settings are defined in `pyproject.toml`. The project tracks branch coverage to ensure all logical paths are exercised.

- **Source**: `src/azure_functions_durable_graph`
- **Reports**: Terminal (missing lines), XML (for CI), and HTML.
- **Branch Coverage**: Enabled (`branch = true`).
- **Minimum Coverage**: 80%

You can view the coverage configuration under the `[tool.coverage.run]` and `[tool.coverage.report]` sections of `pyproject.toml`.

## CI Test Matrix

The test suite runs automatically on every pull request and push to the main branch. The CI matrix ensures compatibility across:

- **OS**: `ubuntu-latest`
- **Python Versions**: 3.10, 3.11, 3.12, 3.13, 3.14

This is managed via the `.github/workflows/ci-test.yml` configuration.

## Troubleshooting

### Common Test Failures

- **PYTHONPATH Issues**: If tests cannot find the `src` or `examples` modules, ensure your environment is set up correctly. Running via `hatch run test` or `make test` handles this automatically via the `pythonpath` setting in `pyproject.toml`.
- **Pydantic Version**: The project supports Pydantic v2. Tests may fail if an older version of Pydantic is installed.
- **Async Setup**: Ensure `pytest-asyncio` is installed and `asyncio_mode = "auto"` is set in `pyproject.toml`.
- **Missing Dependencies**: If you see import errors for `azure.functions` or `azure.durable_functions`, ensure you have installed the development dependencies using `pip install -e .[dev]`.
