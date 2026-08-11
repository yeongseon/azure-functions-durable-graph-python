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

durable-graph deliberately derives its OpenAPI here rather than emitting the
shared ``endpoint`` metadata namespace consumed by ``azure-functions-openapi``.
See ``docs/decisions/0001-endpoint-metadata-self-contained.md`` (ADR-0001) for
the rationale and the conditions under which that decision should be revisited.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from .contracts import ErrorEnvelope, RunStatusEnvelope

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


def _strip_titles(obj: Any) -> Any:
    """Recursively drop Pydantic-emitted ``title`` keys for a stable, terse spec."""
    if isinstance(obj, dict):
        return {k: _strip_titles(v) for k, v in obj.items() if k != "title"}
    if isinstance(obj, list):
        return [_strip_titles(item) for item in obj]
    return obj


def _normalize_nullable(obj: Any) -> Any:
    """Rewrite Pydantic v2 / JSON-Schema-2020 ``anyOf: [X, {type: null}]`` into the
    OpenAPI 3.0.3 ``nullable: true`` idiom.

    ``model_json_schema`` emits ``{"type": "null"}`` for optional fields, which is
    OpenAPI 3.1 syntax and is rejected by 3.0.3 validators/codegen. This collapses
    the null branch: a single non-null member merges with ``nullable: true``; an
    empty (``{}``, i.e. "any value") member becomes ``{}`` (already permits null). A
    redundant ``default: null`` sibling is dropped.
    """
    if isinstance(obj, list):
        return [_normalize_nullable(item) for item in obj]
    if not isinstance(obj, dict):
        return obj

    normalized = {k: _normalize_nullable(v) for k, v in obj.items() if k != "anyOf"}
    any_of = obj.get("anyOf")
    if not isinstance(any_of, list) or not any(
        isinstance(m, dict) and m.get("type") == "null" for m in any_of
    ):
        # No null branch: keep anyOf as-is (still recurse into its members).
        if isinstance(any_of, list):
            normalized["anyOf"] = [_normalize_nullable(m) for m in any_of]
        return normalized

    def _is_null(member: Any) -> bool:
        return isinstance(member, dict) and member.get("type") == "null"

    members = [_normalize_nullable(m) for m in any_of if not _is_null(m)]
    if obj.get("default") is None:
        normalized.pop("default", None)
    if len(members) == 1:
        member = members[0]
        if isinstance(member, dict) and member:
            normalized.update(member)
            normalized["nullable"] = True
        # else: empty ``{}`` already permits any value including null.
    elif members:
        normalized["anyOf"] = members
        normalized["nullable"] = True
    return normalized


def _model_component(model_cls: Any, schemas: dict[str, Any]) -> None:
    """Add *model_cls* (and any nested ``$defs``) to ``schemas`` as OpenAPI
    components, rewriting local refs to point at ``components.schemas`` and
    normalising nullable fields to the OpenAPI 3.0.3 idiom."""
    schema = model_cls.model_json_schema(ref_template="#/components/schemas/{model}")
    for name, definition in (schema.pop("$defs", None) or {}).items():
        schemas.setdefault(name, _normalize_nullable(_strip_titles(definition)))
    schemas[model_cls.__name__] = _normalize_nullable(_strip_titles(schema))


# Hand-authored schemas for wire shapes that have no Pydantic contract model
# (request bodies and the ad-hoc 202 acknowledgement payloads).
_STATIC_SCHEMAS: dict[str, dict[str, Any]] = {
    "StartGraphRunRequest": {
        "type": "object",
        "description": "Wire body for starting a graph run. The server injects "
        "graph_name/graph_hash; only these fields are client-supplied.",
        "properties": {
            "instance_id": {"type": "string"},
            "input": {"type": "object"},
            "metadata": {"type": "object"},
        },
    },
    "CancelRunRequest": {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
    },
    "CheckStatusResponse": {
        "type": "object",
        "description": "Azure Durable Functions check-status payload (management "
        "URLs). Shape is owned by the durable SDK and is intentionally open.",
        "additionalProperties": True,
    },
    "EventAcceptedResponse": {
        "type": "object",
        "properties": {
            "instance_id": {"type": "string"},
            "event_name": {"type": "string"},
            "accepted": {"type": "boolean"},
        },
    },
    "RunCancelledResponse": {
        "type": "object",
        "properties": {
            "instance_id": {"type": "string"},
            "terminated": {"type": "boolean"},
            "reason": {"type": "string"},
        },
    },
}


def _json_ref(name: str) -> dict[str, Any]:
    """An ``application/json`` content block referencing a component schema."""
    return {"content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{name}"}}}}


def _ref_response(description: str, name: str) -> dict[str, Any]:
    return {"description": description, **_json_ref(name)}


def _error_response(description: str) -> dict[str, Any]:
    return _ref_response(description, "ErrorEnvelope")


def _ref_body(name: str) -> dict[str, Any]:
    return {"required": False, **_json_ref(name)}


# Request bodies and responses keyed by the registered function name. Anything
# not listed falls back to a generic ``200 OK`` so meta endpoints (openapi.json,
# health) still produce a valid operation object.
_OPERATION_IO: dict[str, dict[str, Any]] = {
    "start_graph_run": {
        "requestBody": _ref_body("StartGraphRunRequest"),
        "responses": {
            "202": _ref_response("Run accepted; durable check-status URLs.", "CheckStatusResponse"),
            "400": _error_response("Invalid or malformed request body."),
            "404": _error_response("Unknown graph."),
        },
    },
    "get_run_status": {
        "responses": {
            "200": _ref_response("Current run status.", "RunStatusEnvelope"),
            "404": _error_response("Instance not found."),
        },
    },
    "send_run_event": {
        "requestBody": {
            "required": False,
            "content": {"application/json": {"schema": {}}},
        },
        "responses": {
            "202": _ref_response("Event accepted.", "EventAcceptedResponse"),
            "400": _error_response("Request body present but is not valid JSON."),
        },
    },
    "cancel_run": {
        "requestBody": _ref_body("CancelRunRequest"),
        "responses": {
            "202": _ref_response("Run cancellation accepted.", "RunCancelledResponse"),
        },
    },
}

_DEFAULT_RESPONSES: dict[str, Any] = {"200": {"description": "OK"}}


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


def _deepcopy_operation(operation: dict[str, Any]) -> dict[str, Any]:
    """Copy an operation so shared module-level IO dicts are not aliased across
    methods/paths in the emitted document."""
    return copy.deepcopy(operation)


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

        io = _OPERATION_IO.get(name)
        if io and "requestBody" in io:
            operation["requestBody"] = io["requestBody"]
        operation["responses"] = io["responses"] if io else _DEFAULT_RESPONSES

        path_item = paths.setdefault(f"/api/{route}", {})
        for method in _methods(binding_dict):
            path_item[method] = _deepcopy_operation(operation)

    schemas: dict[str, Any] = {
        "RegisteredGraphs": {
            "type": "array",
            "items": {"type": "object"},
            "x-afdg-graphs": registered_graphs,
        },
    }
    _model_component(RunStatusEnvelope, schemas)
    _model_component(ErrorEnvelope, schemas)
    for name, static_schema in _STATIC_SCHEMAS.items():
        schemas[name] = static_schema

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "azure-functions-durable-graph runtime",
            "version": version,
        },
        "paths": paths,
        "components": {"schemas": schemas},
    }
