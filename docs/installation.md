# Installation

`azure-functions-durable-graph` targets the **Azure Functions Python v2 programming model** with **Durable Functions** orchestration.

## Requirements

- Python 3.10+
- `azure-functions`
- `azure-functions-durable`
- Azure Functions Python **v2** (`func.FunctionApp` with decorators)

> This package does not support the legacy `function.json`-based v1 programming model.

## Version Compatibility

| Component | Supported Range | Notes |
| --- | --- | --- |
| Python | 3.10+ | Project metadata currently declares `>=3.10,<3.15`. |
| Pydantic | v2 (`>=2.0,<3.0`) | State models should inherit from `pydantic.BaseModel`. |
| `azure-functions` | Required | Use with Python v2 decorator-based `FunctionApp`. |
| `azure-functions-durable` | Required | Provides Durable Functions orchestration primitives. |

Compatibility expectations:

- State models are based on Pydantic v2 behavior.
- Function definitions should follow the Python v2 decorator style.
- Durable Functions requires a compatible Azure Functions host (v4).

## From PyPI

```bash
pip install azure-functions-durable-graph
```

Ensure your Function App dependencies include:

```text
azure-functions
azure-functions-durable
azure-functions-durable-graph
```

If you pin dependencies, keep `pydantic` in the v2 major version.

## Verify Installation

Run the following command after installation:

```bash
python -c "import azure_functions_durable_graph; print(azure_functions_durable_graph.__version__)"
```

Expected outcome:

- the command prints a version string such as `0.1.0a0`
- no import errors are raised

You can also verify package metadata from your environment:

```bash
pip show azure-functions-durable-graph
```

Check that your active environment is the same one used by your Function App.

## Local Development

```bash
git clone https://github.com/yeongseon/azure-functions-durable-graph-python.git
cd azure-functions-durable-graph
make install
```

All project maintenance commands should go through the Makefile.

## Upgrading

Upgrade to the latest published version:

```bash
pip install --upgrade azure-functions-durable-graph
```

Recommended upgrade workflow:

1. Upgrade in a dedicated virtual environment.
2. Reinstall or confirm compatible `azure-functions`, `azure-functions-durable`, and Pydantic v2 versions.
3. Run your local Azure Functions smoke tests.
4. Confirm graph manifests still match your expected manifest hashes.

For deterministic deployments, pin an explicit version in your dependency file.

## Troubleshooting

### ImportError: No module named `azure_functions_durable_graph`

- Confirm installation ran in the correct environment.
- Run `python -m pip install azure-functions-durable-graph`.
- Verify with `python -c "import azure_functions_durable_graph"`.

### Pydantic version mismatch

- Ensure Pydantic is v2 (`pip show pydantic`).
- If v1 is installed transitively, pin `pydantic>=2,<3` and reinstall.

### Missing `azure-functions-durable`

- Install it explicitly: `pip install azure-functions-durable`.
- Ensure `host.json` includes the Durable Functions extension bundle.

### Function app starts but graph endpoints are not registered

- Confirm you are using the Python v2 programming model (`func.FunctionApp()`).
- Confirm `DurableGraphApp` is instantiated and a registration is added.
- Confirm `app = runtime.function_app` is the module-level variable Azure Functions discovers.
