from __future__ import annotations

import json
import logging
from typing import Any
import uuid

import azure.durable_functions as df
import azure.functions as func
from pydantic import ValidationError

from . import __version__, openapi, runtime
from .contracts import (
    ErrorEnvelope,
    OrchestrationInput,
    RunStatusEnvelope,
)
from .manifest import GraphRegistration
from .registry import GraphRegistry


class DurableGraphApp:
    def __init__(
        self,
        *,
        auth_level: func.AuthLevel = func.AuthLevel.ANONYMOUS,
    ) -> None:
        self.function_app = func.FunctionApp(http_auth_level=auth_level)
        self.blueprint = df.Blueprint()
        self.registry = GraphRegistry()

        self._orchestrator_name = runtime.ORCHESTRATOR_NAME
        self._node_activity_name = runtime.NODE_ACTIVITY_NAME
        self._route_activity_name = runtime.ROUTE_ACTIVITY_NAME
        self._event_activity_name = runtime.EVENT_ACTIVITY_NAME

        self._register_runtime_functions()
        self.function_app.register_functions(self.blueprint)

    def register_registration(self, registration: GraphRegistration[Any]) -> None:
        self.registry.register(registration)

    def _register_runtime_functions(self) -> None:
        @self.blueprint.route(route="graphs/{graph_name}/runs", methods=("POST",))  # type: ignore[untyped-decorator]
        @self.blueprint.durable_client_input(client_name="client")  # type: ignore[untyped-decorator]
        async def start_graph_run(
            req: func.HttpRequest,
            client: df.DurableOrchestrationClient,
        ) -> func.HttpResponse:
            graph_name = req.route_params["graph_name"]

            try:
                manifest = self.registry.manifest(graph_name)
            except KeyError:
                return _error_response(f"unknown graph '{graph_name}'", status_code=404)

            body = _read_json(req)
            if body is None:
                return _error_response(
                    "request body must be valid JSON object", status_code=400
                )

            instance_id = body.get("instance_id") or str(uuid.uuid4())
            initial_state = body.get("input") or {}
            metadata = body.get("metadata") or {}

            try:
                request = OrchestrationInput(
                    graph_name=graph_name,
                    graph_hash=manifest.graph_hash,
                    initial_state=initial_state,
                    metadata=metadata,
                )
            except ValidationError as exc:
                return _error_response(
                    "invalid request body", status_code=400, details=exc.errors()
                )

            logging.info(
                "Starting graph '%s' instance '%s' version '%s'",
                graph_name,
                instance_id,
                manifest.version,
            )

            await client.start_new(
                self._orchestrator_name,
                instance_id=instance_id,
                client_input=request.model_dump(mode="python"),
            )
            return client.create_check_status_response(req, instance_id)  # type: ignore[no-any-return]

        @self.blueprint.route(route="runs/{instance_id}", methods=("GET",))  # type: ignore[untyped-decorator]
        @self.blueprint.durable_client_input(client_name="client")  # type: ignore[untyped-decorator]
        async def get_run_status(
            req: func.HttpRequest,
            client: df.DurableOrchestrationClient,
        ) -> func.HttpResponse:
            instance_id = req.route_params["instance_id"]
            status = await client.get_status(instance_id, show_input=True)

            if status is None:
                return _error_response("instance not found", status_code=404)

            envelope = RunStatusEnvelope(
                instance_id=instance_id,
                runtime_status=getattr(status, "runtime_status", None),
                custom_status=getattr(status, "custom_status", None),
                input=getattr(status, "input_", None) or getattr(status, "input", None),
                output=getattr(status, "output", None),
            )
            return _json_response(envelope.model_dump(mode="python"))

        @self.blueprint.route(  # type: ignore[untyped-decorator]
            route="runs/{instance_id}/events/{event_name}",
            methods=("POST",),
        )
        @self.blueprint.durable_client_input(client_name="client")  # type: ignore[untyped-decorator]
        async def send_run_event(
            req: func.HttpRequest,
            client: df.DurableOrchestrationClient,
        ) -> func.HttpResponse:
            instance_id = req.route_params["instance_id"]
            event_name = req.route_params["event_name"]
            event_payload, parsed_ok = _read_event_payload(req)
            if not parsed_ok:
                return _error_response(
                    "request body present but is not valid JSON", status_code=400
                )
            await client.raise_event(instance_id, event_name, event_payload)

            return _json_response(
                {
                    "instance_id": instance_id,
                    "event_name": event_name,
                    "accepted": True,
                },
                status_code=202,
            )

        @self.blueprint.route(route="runs/{instance_id}/cancel", methods=("POST",))  # type: ignore[untyped-decorator]
        @self.blueprint.durable_client_input(client_name="client")  # type: ignore[untyped-decorator]
        async def cancel_run(
            req: func.HttpRequest,
            client: df.DurableOrchestrationClient,
        ) -> func.HttpResponse:
            instance_id = req.route_params["instance_id"]
            body = _read_json(req) or {}
            reason = body.get("reason", "cancel requested by client")
            await client.terminate(instance_id, reason)
            return _json_response(
                {"instance_id": instance_id, "terminated": True, "reason": reason},
                status_code=202,
            )

        @self.blueprint.route(route="openapi.json", methods=("GET",))  # type: ignore[untyped-decorator]
        def openapi_document(req: func.HttpRequest) -> func.HttpResponse:
            _ = req
            return _json_response(self._build_openapi())

        @self.blueprint.route(route="health", methods=("GET",))  # type: ignore[untyped-decorator]
        def health(req: func.HttpRequest) -> func.HttpResponse:
            _ = req
            return _json_response({"ok": True, "registered_graphs": self.registry.list_manifests()})

        @self.blueprint.orchestration_trigger(context_name="context")  # type: ignore[untyped-decorator]
        def afdg_orchestrator(context: df.DurableOrchestrationContext) -> Any:
            result: dict[str, Any] = yield from runtime.orchestrate(context, self.registry)
            return result

        @self.blueprint.activity_trigger(input_name="payload")  # type: ignore[untyped-decorator]
        async def afdg_execute_node(payload: dict[str, Any]) -> dict[str, Any]:
            return await runtime.execute_node(self.registry, payload)

        @self.blueprint.activity_trigger(input_name="payload")  # type: ignore[untyped-decorator]
        async def afdg_resolve_route(payload: dict[str, Any]) -> dict[str, Any]:
            return await runtime.resolve_route(self.registry, payload)

        @self.blueprint.activity_trigger(input_name="payload")  # type: ignore[untyped-decorator]
        async def afdg_apply_event(payload: dict[str, Any]) -> dict[str, Any]:
            return await runtime.apply_event(self.registry, payload)

    def _build_openapi(self) -> dict[str, Any]:
        return openapi.build_openapi(
            self.blueprint,
            version=__version__,
            registered_graphs=self.registry.list_manifests(),
        )


def _read_json(req: func.HttpRequest) -> dict[str, Any] | None:
    """Parse request body as a JSON object, returning *None* on failure."""
    try:
        body = req.get_json()
        return body if isinstance(body, dict) else None
    except ValueError:
        return None


def _read_event_payload(req: func.HttpRequest) -> tuple[Any, bool]:
    """Parse an external-event body as arbitrary JSON.

    Returns ``(payload, parsed_ok)``.  An empty body is a valid "no payload"
    event → ``(None, True)``.  A non-empty body that fails to parse is a
    client error → ``(None, False)`` so the caller can return HTTP 400 instead
    of silently raising the event with null data.
    """
    raw = req.get_body()
    if not raw:
        return None, True
    try:
        return req.get_json(), True
    except ValueError:
        return None, False


def _json_response(payload: dict[str, Any], status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload, default=str),
        mimetype="application/json",
        status_code=status_code,
    )


def _error_response(
    error: str,
    status_code: int,
    details: Any | None = None,
) -> func.HttpResponse:
    """Build an HTTP error response from the shared :class:`ErrorEnvelope`."""
    return _json_response(
        ErrorEnvelope(error=error, details=details).model_dump(mode="python"),
        status_code=status_code,
    )

