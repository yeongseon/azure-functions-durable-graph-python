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

from pydantic import BaseModel
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


def test_contract_component_schemas_present(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    schemas = _spec(app_mod)["components"]["schemas"]
    for name in (
        "RunStatusEnvelope",
        "ErrorEnvelope",
        "StartGraphRunRequest",
        "CancelRunRequest",
        "CheckStatusResponse",
        "EventAcceptedResponse",
        "RunCancelledResponse",
    ):
        assert name in schemas, name
    # Pydantic-derived schemas carry no leftover ``title`` noise.
    assert "title" not in schemas["RunStatusEnvelope"]
    assert "title" not in schemas["ErrorEnvelope"]
    assert schemas["RunStatusEnvelope"]["required"] == ["instance_id"]


def test_request_bodies_are_wire_accurate(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]

    start = paths["/api/graphs/{graph_name}/runs"]["post"]
    assert start["requestBody"]["required"] is False
    assert (
        start["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/StartGraphRunRequest"
    )

    # cancel_run reads an optional {reason?} body (wire-accurate; issue #113).
    cancel = paths["/api/runs/{instance_id}/cancel"]["post"]
    assert cancel["requestBody"]["required"] is False
    assert (
        cancel["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/CancelRunRequest"
    )

    # send_run_event accepts arbitrary JSON: an empty (any) schema.
    event = paths["/api/runs/{instance_id}/events/{event_name}"]["post"]
    assert event["requestBody"]["required"] is False
    assert event["requestBody"]["content"]["application/json"]["schema"] == {}

    # get_run_status is a GET with no request body.
    assert "requestBody" not in paths["/api/runs/{instance_id}"]["get"]


def _resp_ref(operation: dict[str, Any], code: str) -> str:
    schema: dict[str, Any] = operation["responses"][code]["content"]["application/json"]["schema"]
    ref: str = schema["$ref"]
    return ref


def test_responses_reference_expected_schemas(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]

    start = paths["/api/graphs/{graph_name}/runs"]["post"]
    assert _resp_ref(start, "202") == "#/components/schemas/CheckStatusResponse"
    assert _resp_ref(start, "400") == "#/components/schemas/ErrorEnvelope"
    assert _resp_ref(start, "404") == "#/components/schemas/ErrorEnvelope"

    status = paths["/api/runs/{instance_id}"]["get"]
    assert _resp_ref(status, "200") == "#/components/schemas/RunStatusEnvelope"
    assert _resp_ref(status, "404") == "#/components/schemas/ErrorEnvelope"

    event = paths["/api/runs/{instance_id}/events/{event_name}"]["post"]
    assert _resp_ref(event, "202") == "#/components/schemas/EventAcceptedResponse"
    assert _resp_ref(event, "400") == "#/components/schemas/ErrorEnvelope"

    cancel = paths["/api/runs/{instance_id}/cancel"]["post"]
    assert _resp_ref(cancel, "202") == "#/components/schemas/RunCancelledResponse"


def test_meta_endpoints_get_default_response(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]
    for route in ("/api/health", "/api/openapi.json"):
        responses = paths[route]["get"]["responses"]
        assert responses == {"200": {"description": "OK"}}


def test_operations_shared_error_envelope_not_aliased(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    """Every operation must carry an independent responses object even though the
    generator sources them from shared module-level constants."""
    app_mod, _ = modules
    paths = _spec(app_mod)["paths"]
    start = paths["/api/graphs/{graph_name}/runs"]["post"]["responses"]
    status = paths["/api/runs/{instance_id}"]["get"]["responses"]
    assert start["404"] is not status["404"]
    # Same schema $ref reused across sites; per-site descriptions differ.
    assert _resp_ref(
        paths["/api/graphs/{graph_name}/runs"]["post"], "404"
    ) == _resp_ref(paths["/api/runs/{instance_id}"]["get"], "404")
    assert start["404"]["description"] != status["404"]["description"]


def test_nullable_normalized_to_openapi_30_idiom(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    """Optional contract fields emit the 3.0.3 ``nullable: true`` idiom, never the
    3.1-only ``anyOf: [..., {type: null}]`` shape."""
    app_mod, _ = modules
    props = _spec(app_mod)["components"]["schemas"]["RunStatusEnvelope"]["properties"]
    # Typed optional -> nullable:true, no anyOf.
    assert props["runtime_status"] == {"type": "string", "nullable": True}
    # ``Any | None`` optional -> permissive empty schema (already allows null).
    assert props["custom_status"] == {}
    # No leftover 3.1 null branches anywhere in the document.
    assert "{'type': 'null'}" not in json.dumps(_spec(app_mod))


def test_model_component_flattens_nested_defs(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    """A contract model with a nested BaseModel has its ``$defs`` lifted into the
    shared components map with refs pointing at ``components.schemas``."""
    _, openapi_mod = modules

    class _Nested(BaseModel):
        value: str

    class _Outer(BaseModel):
        nested: _Nested
        note: str | None = None

    schemas: dict[str, Any] = {}
    openapi_mod._model_component(_Outer, schemas)

    assert "_Nested" in schemas
    assert "_Outer" in schemas
    assert schemas["_Outer"]["properties"]["nested"]["$ref"] == "#/components/schemas/_Nested"
    assert schemas["_Nested"]["properties"]["value"] == {"type": "string"}
    # Nullable normalization applies to the outer model too.
    assert schemas["_Outer"]["properties"]["note"] == {"type": "string", "nullable": True}


def test_normalize_nullable_edge_cases(
    modules: tuple[ModuleType, ModuleType],
) -> None:
    """Directly exercise the ``_normalize_nullable`` branches that the fixed
    contracts don't happen to produce: non-null ``anyOf`` unions, multi-member
    nullable unions, and a preserved non-null ``default``."""
    _, openapi_mod = modules
    normalize = openapi_mod._normalize_nullable

    # anyOf with no null branch is preserved (members still recursed).
    union = {"anyOf": [{"type": "string"}, {"type": "integer"}]}
    assert normalize(union) == union

    # Multi-member union + null -> keep anyOf, add nullable:true.
    nullable_union = {"anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]}
    assert normalize(nullable_union) == {
        "anyOf": [{"type": "string"}, {"type": "integer"}],
        "nullable": True,
    }

    # A meaningful (non-null) default is preserved through normalization.
    with_default = {"anyOf": [{"type": "string"}, {"type": "null"}], "default": "x"}
    assert normalize(with_default) == {"type": "string", "nullable": True, "default": "x"}

    # Non-dict/list scalars pass through untouched.
    assert normalize("plain") == "plain"
    assert normalize([{"type": "null"}]) == [{"type": "null"}]
