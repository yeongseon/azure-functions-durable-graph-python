"""Tests for the blueprint-derived OpenAPI generator.

These lock down three properties:

* **Golden snapshot** — the fully derived document matches a checked-in
  fixture (version-normalised), so accidental drift is caught in review.
* **Structural invariants** — every runtime HTTP route is present with the
  right methods and path parameters, independent of ordering.
* **SDK guard** — the generator fails loudly if the durable-functions
  ``_function_builders`` internal ever disappears.

``test_app`` reloads the ``app`` module against a *mocked* Azure SDK and leaves
those bindings cached in ``sys.modules``.  Because this generator introspects
the real blueprint internals, :func:`_reload_with_real_sdk` reloads the modules
against the genuine (installed) SDK before each test.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_GOLDEN = Path(__file__).parent / "fixtures" / "openapi_golden.json"


def _reload_with_real_sdk() -> tuple[ModuleType, ModuleType]:
    import azure_functions_durable_graph.app as app_mod
    import azure_functions_durable_graph.openapi as openapi_mod

    openapi_mod = importlib.reload(openapi_mod)
    app_mod = importlib.reload(app_mod)
    return app_mod, openapi_mod


@pytest.fixture()
def modules() -> tuple[ModuleType, ModuleType]:
    return _reload_with_real_sdk()


def _spec(app_mod: ModuleType) -> dict[str, Any]:
    spec: dict[str, Any] = app_mod.DurableGraphApp()._build_openapi()
    return spec


def test_matches_golden_snapshot(modules: tuple[ModuleType, ModuleType]) -> None:
    app_mod, _ = modules
    spec = _spec(app_mod)
    # Version is dynamic; normalise before comparing against the frozen golden.
    assert spec["info"]["version"] == app_mod.__version__
    spec["info"]["version"] = "<VERSION>"

    golden = json.loads(_GOLDEN.read_text())
    assert spec == golden


def test_top_level_shape(modules: tuple[ModuleType, ModuleType]) -> None:
    app_mod, _ = modules
    spec = _spec(app_mod)
    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["title"] == "azure-functions-durable-graph runtime"
    assert "RegisteredGraphs" in spec["components"]["schemas"]


def test_all_runtime_routes_present(modules: tuple[ModuleType, ModuleType]) -> None:
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]
    expected = {
        "/api/graphs/{graph_name}/runs": {"post"},
        "/api/runs/{instance_id}": {"get"},
        "/api/runs/{instance_id}/events/{event_name}": {"post"},
        "/api/runs/{instance_id}/cancel": {"post"},
        "/api/openapi.json": {"get"},
        "/api/health": {"get"},
    }
    assert set(paths) == set(expected)
    for path, methods in expected.items():
        assert set(paths[path]) == methods


def test_path_parameters_derived_from_route(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]
    events = paths["/api/runs/{instance_id}/events/{event_name}"]["post"]
    names = [param["name"] for param in events["parameters"]]
    assert names == ["instance_id", "event_name"]
    for param in events["parameters"]:
        assert param["in"] == "path"
        assert param["required"] is True
        assert param["schema"] == {"type": "string"}


def test_parameterless_route_has_no_parameters(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    health = _spec(app_mod)["paths"]["/api/health"]["get"]
    assert "parameters" not in health


def test_registered_graphs_flow_into_components(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    app = app_mod.DurableGraphApp()
    spec = app._build_openapi()
    assert (
        spec["components"]["schemas"]["RegisteredGraphs"]["x-afdg-graphs"]
        == app.registry.list_manifests()
    )


def test_guard_raises_when_sdk_internal_missing(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    _, openapi_mod = modules

    class _Fake:
        pass

    with pytest.raises(RuntimeError, match="_function_builders"):
        openapi_mod._get_function_builders(_Fake())


def test_blueprint_still_exposes_function_builders(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    """Canary: if this fails, the durable-functions SDK changed its internals."""
    app_mod, openapi_mod = modules
    blueprint = app_mod.DurableGraphApp().blueprint
    assert hasattr(blueprint, "_function_builders")
    assert openapi_mod._get_function_builders(blueprint)
