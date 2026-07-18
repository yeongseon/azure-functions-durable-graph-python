"""Derive the runtime OpenAPI document from the durable-functions blueprint.

Rather than hand-maintaining a parallel copy of every HTTP route (which drifts
the moment a route is added, renamed, or re-parametrised), we introspect the
registered function builders on the blueprint and synthesise the spec from the
same source of truth the Functions host uses.

The blueprint exposes its registrations through the *private*
``_function_builders`` attribute.  That is an internal detail of
``azure-durable-functions``; :func:`_get_function_builders` guards against it
disappearing so an SDK upgrade fails loudly here (with a test to match) instead
of silently emitting an empty spec.
"""

from __future__ import annotations

import re
from typing import Any

_PARAM_RE = re.compile(r"\{(\w+)\}")

# Human-readable summaries keyed by the registered function name.  Anything not
# listed still appears in the spec with a generated summary, so a new route is
# never silently dropped.
_SUMMARIES: dict[str, str] = {
    "start_graph_run": "Start a graph run",
    "get_run_status": "Get run status",
    "send_run_event": "Raise an external event",
    "cancel_run": "Terminate a run",
    "openapi_document": "OpenAPI document",
    "health": "Health",
}


def _get_function_builders(blueprint: Any) -> list[Any]:
    """Return the blueprint's function builders, failing loudly if the SDK changed."""
    builders = getattr(blueprint, "_function_builders", None)
    if builders is None:
        raise RuntimeError(
            "azure-durable-functions Blueprint no longer exposes "
            "'_function_builders'; the OpenAPI generator in "
            "azure_functions_durable_graph.openapi must be updated to the "
            "current SDK internals."
        )
    return list(builders)


def _http_trigger_binding(function: Any) -> dict[str, Any] | None:
    """Return the httpTrigger binding dict for *function*, or ``None``."""
    for binding in function.get_bindings():
        binding_dict: dict[str, Any] = binding.get_dict_repr()
        if binding_dict.get("type") == "httpTrigger":
            return binding_dict
    return None  # pragma: no cover - an http function always has an httpTrigger


def _methods(binding_dict: dict[str, Any]) -> list[str]:
    """Normalise the trigger's HTTP methods to lowercase operation keys."""
    methods = binding_dict.get("methods") or []
    return [getattr(method, "value", str(method)).lower() for method in methods]


def _path_parameters(route: str) -> list[dict[str, Any]]:
    """Build OpenAPI path-parameter objects for every ``{param}`` in *route*."""
    return [
        {
            "name": name,
            "in": "path",
            "required": True,
            "schema": {"type": "string"},
        }
        for name in _PARAM_RE.findall(route)
    ]


def build_openapi(
    blueprint: Any,
    *,
    version: str,
    registered_graphs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Synthesise the OpenAPI 3.0.3 document from the blueprint's HTTP routes."""
    paths: dict[str, Any] = {}

    for builder in _get_function_builders(blueprint):
        function = builder.build()
        if not function.is_http_function():
            continue

        binding_dict = _http_trigger_binding(function)
        if binding_dict is None:  # pragma: no cover - http function always has trigger
            continue

        route = binding_dict.get("route")
        if not route:  # pragma: no cover - runtime routes always declare a route
            continue

        name = function.get_function_name()
        summary = _SUMMARIES.get(name, name.replace("_", " ").capitalize())
        parameters = _path_parameters(route)

        operation: dict[str, Any] = {"summary": summary}
        if parameters:
            operation["parameters"] = parameters

        path_item = paths.setdefault(f"/api/{route}", {})
        for method in _methods(binding_dict):
            path_item[method] = dict(operation)

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "azure-functions-durable-graph runtime",
            "version": version,
        },
        "paths": paths,
        "components": {
            "schemas": {
                "RegisteredGraphs": {
                    "type": "array",
                    "items": {"type": "object"},
                    "x-afdg-graphs": registered_graphs,
                }
            }
        },
    }
