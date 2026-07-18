"""Tests for DurableGraphApp HTTP handlers and activity functions."""

from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision
from azure_functions_durable_graph.contracts import (
    EventApplyRequest,
    NodeExecutionRequest,
    OrchestrationInput,
    RouteAction,
    RouteResolutionRequest,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


class DemoState(BaseModel):
    value: int = 0


def increment(state: DemoState) -> dict[str, Any]:
    return {"value": state.value + 1}


def router(state: DemoState) -> RouteDecision:
    if state.value >= 3:
        return RouteDecision.complete()
    return RouteDecision.next("inc")


def _build_registration() -> Any:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("inc")
    builder.add_node("inc", increment, route=router, terminal=False)
    return builder.build()


def _make_http_request(
    *,
    route_params: dict[str, str] | None = None,
    body: Any = None,
    body_bytes: bytes | None = None,
) -> MagicMock:
    """Build a mock azure.functions.HttpRequest."""
    req = MagicMock()
    req.route_params = route_params or {}
    if body_bytes is not None:
        req.get_json.side_effect = ValueError("invalid json")
        req.get_body.return_value = body_bytes
    elif body is not None:
        req.get_json.return_value = body
        req.get_body.return_value = b"<non-empty>"
    else:
        req.get_json.side_effect = ValueError("no body")
        req.get_body.return_value = b""
    return req


# ── Module-level helpers ─────────────────────────────────────────────────────


def _import_app() -> Any:
    """Import DurableGraphApp with mocked Azure SDK packages."""
    with (
        patch.dict(
            "sys.modules",
            {
                "azure": MagicMock(),
                "azure.functions": MagicMock(),
                "azure.durable_functions": MagicMock(),
            },
        ),
    ):
        # Force re-import so the mocks are used
        import importlib

        import azure_functions_durable_graph.app as app_mod

        importlib.reload(app_mod)
        return app_mod


class _CapturingBlueprint:
    def __init__(self) -> None:
        self.routes: dict[tuple[str, tuple[str, ...]], Any] = {}
        self.orchestrator: Any = None
        self.activities: dict[str, Any] = {}

    def route(self, route: str = "", methods: tuple[str, ...] = ("GET",)) -> Any:
        def decorator(fn: Any) -> Any:
            self.routes[(route, methods)] = fn
            return fn

        return decorator

    def durable_client_input(self, client_name: str = "client") -> Any:
        _ = client_name

        def decorator(fn: Any) -> Any:
            return fn

        return decorator

    def orchestration_trigger(self, context_name: str = "context") -> Any:
        _ = context_name

        def decorator(fn: Any) -> Any:
            self.orchestrator = fn
            return fn

        return decorator

    def activity_trigger(self, input_name: str = "payload") -> Any:
        _ = input_name

        def decorator(fn: Any) -> Any:
            self.activities[fn.__name__] = fn
            return fn

        return decorator


class _FakeHttpResponse:
    def __init__(self, *, body: str, mimetype: str, status_code: int) -> None:
        self.body = body
        self.mimetype = mimetype
        self.status_code = status_code


def _import_app_with_capture() -> tuple[Any, Any, _CapturingBlueprint]:
    """Import app module with concrete decorators that capture handlers."""

    blueprint = _CapturingBlueprint()

    class _FakeFunctionApp:
        def __init__(self, *, http_auth_level: Any) -> None:
            self.http_auth_level = http_auth_level

        def register_functions(self, bp: Any) -> None:
            _ = bp

    mock_func = ModuleType("azure.functions")
    setattr(mock_func, "AuthLevel", SimpleNamespace(ANONYMOUS="anonymous"))
    setattr(mock_func, "FunctionApp", _FakeFunctionApp)
    setattr(mock_func, "HttpResponse", _FakeHttpResponse)
    setattr(mock_func, "HttpRequest", object)

    mock_df = ModuleType("azure.durable_functions")
    setattr(mock_df, "Blueprint", lambda: blueprint)
    setattr(mock_df, "DurableOrchestrationClient", object)
    setattr(mock_df, "DurableOrchestrationContext", object)

    mock_azure = ModuleType("azure")
    mock_azure.__path__ = []
    setattr(mock_azure, "functions", mock_func)
    setattr(mock_azure, "durable_functions", mock_df)

    with patch.dict(
        "sys.modules",
        {
            "azure": mock_azure,
            "azure.functions": mock_func,
            "azure.durable_functions": mock_df,
        },
    ):
        import importlib

        import azure_functions_durable_graph.app as app_mod

        importlib.reload(app_mod)
        app = app_mod.DurableGraphApp()
        return app_mod, app, blueprint


def _json_body(response: _FakeHttpResponse) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(response.body)
    return payload


# ── DurableGraphApp construction ─────────────────────────────────────────────


class TestDurableGraphAppInit:
    """Test that DurableGraphApp initialises with mocked Azure SDK."""

    def test_creates_instance(self) -> None:
        app_mod = _import_app()
        app = app_mod.DurableGraphApp()
        assert app.registry is not None
        assert app.function_app is not None
        assert app.blueprint is not None

    def test_register_registration(self) -> None:
        app_mod = _import_app()
        app = app_mod.DurableGraphApp()
        registration = _build_registration()
        app.register_registration(registration)
        manifests = app.registry.list_manifests()
        assert len(manifests) == 1
        assert manifests[0]["graph_name"] == "demo"


class TestRuntimeHandlers:
    def _handler(self, bp: _CapturingBlueprint, route: str, method: str) -> Any:
        return bp.routes[(route, (method,))]

    @pytest.mark.asyncio
    async def test_start_graph_run_success(self) -> None:
        app_mod, app, bp = _import_app_with_capture()
        _ = app_mod
        registration = _build_registration()
        app.register_registration(registration)
        handler = self._handler(bp, "graphs/{graph_name}/runs", "POST")

        req = _make_http_request(
            route_params={"graph_name": "demo"},
            body={"instance_id": "run-1", "input": {"value": 1}, "metadata": {"source": "test"}},
        )
        client = MagicMock()
        client.start_new = AsyncMock()
        check_response = _FakeHttpResponse(body="{}", mimetype="application/json", status_code=202)
        client.create_check_status_response.return_value = check_response

        response = await handler(req, client)
        assert response is check_response
        client.start_new.assert_awaited_once()
        _, kwargs = client.start_new.await_args
        assert kwargs["instance_id"] == "run-1"
        assert kwargs["client_input"]["graph_name"] == "demo"
        assert kwargs["client_input"]["graph_hash"] == registration.manifest.graph_hash

    @pytest.mark.asyncio
    async def test_start_graph_run_unknown_graph(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "graphs/{graph_name}/runs", "POST")
        req = _make_http_request(route_params={"graph_name": "missing"}, body={"input": {}})

        response = await handler(req, MagicMock())
        assert response.status_code == 404
        assert _json_body(response)["error"] == "unknown graph 'missing'"

    @pytest.mark.asyncio
    async def test_start_graph_run_invalid_json_body(self) -> None:
        _, app, bp = _import_app_with_capture()
        app.register_registration(_build_registration())
        handler = self._handler(bp, "graphs/{graph_name}/runs", "POST")
        req = _make_http_request(route_params={"graph_name": "demo"}, body=["not", "object"])

        response = await handler(req, MagicMock())
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_start_graph_run_invalid_orchestration_input(self) -> None:
        _, app, bp = _import_app_with_capture()
        app.register_registration(_build_registration())
        handler = self._handler(bp, "graphs/{graph_name}/runs", "POST")
        req = _make_http_request(
            route_params={"graph_name": "demo"},
            body={"input": ["not", "dict"]},
        )

        response = await handler(req, MagicMock())
        assert response.status_code == 400
        payload = _json_body(response)
        assert payload["error"] == "invalid request body"
        assert payload["details"]

    @pytest.mark.asyncio
    async def test_get_run_status_success(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "runs/{instance_id}", "GET")
        req = _make_http_request(route_params={"instance_id": "inst-1"})
        status = SimpleNamespace(
            runtime_status="Completed",
            custom_status={"node": "inc"},
            input_={"value": 1},
            output={"value": 2},
        )
        client = MagicMock()
        client.get_status = AsyncMock(return_value=status)

        response = await handler(req, client)
        assert response.status_code == 200
        payload = _json_body(response)
        assert payload["instance_id"] == "inst-1"
        assert payload["runtime_status"] == "Completed"

    @pytest.mark.asyncio
    async def test_get_run_status_not_found(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "runs/{instance_id}", "GET")
        req = _make_http_request(route_params={"instance_id": "missing"})
        client = MagicMock()
        client.get_status = AsyncMock(return_value=None)

        response = await handler(req, client)
        assert response.status_code == 404
        assert _json_body(response)["error"] == "instance not found"

    @pytest.mark.asyncio
    async def test_send_run_event_success(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "runs/{instance_id}/events/{event_name}", "POST")
        req = _make_http_request(
            route_params={"instance_id": "inst-1", "event_name": "approval"},
            body=["payload"],
        )
        client = MagicMock()
        client.raise_event = AsyncMock()

        response = await handler(req, client)
        assert response.status_code == 202
        client.raise_event.assert_awaited_once_with("inst-1", "approval", ["payload"])

    @pytest.mark.asyncio
    async def test_cancel_run_default_reason(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "runs/{instance_id}/cancel", "POST")
        req = _make_http_request(route_params={"instance_id": "inst-1"}, body={})
        client = MagicMock()
        client.terminate = AsyncMock()

        response = await handler(req, client)
        assert response.status_code == 202
        payload = _json_body(response)
        assert payload["terminated"] is True
        assert payload["reason"] == "cancel requested by client"

    @pytest.mark.asyncio
    async def test_cancel_run_custom_reason(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "runs/{instance_id}/cancel", "POST")
        req = _make_http_request(
            route_params={"instance_id": "inst-2"}, body={"reason": "operator request"}
        )
        client = MagicMock()
        client.terminate = AsyncMock()

        response = await handler(req, client)
        assert response.status_code == 202
        client.terminate.assert_awaited_once_with("inst-2", "operator request")

    def test_openapi_document_contains_openapi_key(self) -> None:
        _, _, bp = _import_app_with_capture()
        handler = self._handler(bp, "openapi.json", "GET")

        response = handler(_make_http_request())
        assert response.status_code == 200
        assert "openapi" in _json_body(response)

    def test_health_reports_registered_graphs(self) -> None:
        _, app, bp = _import_app_with_capture()
        app.register_registration(_build_registration())
        handler = self._handler(bp, "health", "GET")

        response = handler(_make_http_request())
        assert response.status_code == 200
        payload = _json_body(response)
        assert payload["ok"] is True
        assert payload["registered_graphs"][0]["graph_name"] == "demo"


class TestOrchestrator:
    def test_orchestrator_complete_path(self) -> None:
        _, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        assert bp.orchestrator is not None

        context = MagicMock()
        context.get_input.return_value = {
            "graph_name": "demo",
            "graph_hash": registration.manifest.graph_hash,
            "initial_state": {"value": 0},
            "metadata": {},
        }
        context.call_activity.side_effect = ["exec-call", "route-call"]

        gen = bp.orchestrator(context)
        assert next(gen) == "exec-call"
        assert gen.send({"value": 1}) == "route-call"
        with pytest.raises(StopIteration) as done:
            gen.send({"action": "complete"})

        output = done.value.value
        assert output["final_node"] == "inc"
        assert output["state"] == {"value": 1}

    def test_orchestrator_next_path_loops_to_next_node(self) -> None:
        _, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        assert bp.orchestrator is not None

        context = MagicMock()
        context.get_input.return_value = {
            "graph_name": "demo",
            "graph_hash": registration.manifest.graph_hash,
            "initial_state": {"value": 0},
            "metadata": {},
        }
        context.call_activity.side_effect = ["exec-1", "route-1", "exec-2"]

        gen = bp.orchestrator(context)
        assert next(gen) == "exec-1"
        assert gen.send({"value": 1}) == "route-1"
        assert gen.send({"action": "next", "next_node": "inc"}) == "exec-2"

    def test_orchestrator_wait_for_event_path(self) -> None:
        _, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        assert bp.orchestrator is not None

        context = MagicMock()
        context.get_input.return_value = {
            "graph_name": "demo",
            "graph_hash": registration.manifest.graph_hash,
            "initial_state": {"value": 0},
            "metadata": {},
        }
        context.call_activity.side_effect = ["exec-1", "route-1", "event-apply", "exec-2"]
        context.wait_for_external_event.return_value = "wait-event"

        gen = bp.orchestrator(context)
        assert next(gen) == "exec-1"
        assert gen.send({"value": 1}) == "route-1"
        assert (
            gen.send({"action": "wait_for_event", "event_name": "approval", "resume_node": "inc"})
            == "wait-event"
        )
        assert gen.send({"approved": True}) == "event-apply"
        assert gen.send({"value": 2}) == "exec-2"


class TestActivityFunctions:
    def _activity(self, bp: _CapturingBlueprint, name: str) -> Any:
        return bp.activities[name]

    @pytest.mark.asyncio
    async def test_execute_node_activity_success(self) -> None:
        _, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        activity = self._activity(bp, "afdg_execute_node")

        payload = NodeExecutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 3},
        ).model_dump(mode="python")
        result = await activity(payload)
        assert result["value"] == 4

    @pytest.mark.asyncio
    async def test_execute_node_activity_logs_and_raises_on_error(self) -> None:
        app_mod, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        activity = self._activity(bp, "afdg_execute_node")
        payload = NodeExecutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 3},
        ).model_dump(mode="python")

        app.registry.execute_node = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(app_mod.logging, "exception") as log_exception:
            with pytest.raises(RuntimeError, match="boom"):
                await activity(payload)
        log_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_route_activity_success(self) -> None:
        _, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        activity = self._activity(bp, "afdg_resolve_route")

        payload = RouteResolutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 0},
        ).model_dump(mode="python")
        result = await activity(payload)
        assert result["action"] == "next"

    @pytest.mark.asyncio
    async def test_resolve_route_activity_logs_and_raises_on_error(self) -> None:
        app_mod, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        activity = self._activity(bp, "afdg_resolve_route")
        payload = RouteResolutionRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            node_name="inc",
            state={"value": 3},
        ).model_dump(mode="python")

        app.registry.resolve_route = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(app_mod.logging, "exception") as log_exception:
            with pytest.raises(RuntimeError, match="boom"):
                await activity(payload)
        log_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_event_activity_success(self) -> None:
        _, app, bp = _import_app_with_capture()

        class EventState(BaseModel):
            value: int = 0

        def event_handler(state: EventState, payload: Any) -> dict[str, Any]:
            return {"value": state.value + payload["delta"]}

        builder = ManifestBuilder(graph_name="event-demo", state_model=EventState, version="1")
        builder.set_entrypoint("inc")
        builder.add_node("inc", lambda s: {"value": s.value + 1}, terminal=True)
        builder.add_event_handler("delta", event_handler)
        registration = builder.build()
        app.register_registration(registration)

        activity = self._activity(bp, "afdg_apply_event")
        payload = EventApplyRequest(
            graph_name="event-demo",
            graph_hash=registration.manifest.graph_hash,
            event_name="delta",
            state={"value": 5},
            event_payload={"delta": 2},
        ).model_dump(mode="python")
        result = await activity(payload)
        assert result["value"] == 7

    @pytest.mark.asyncio
    async def test_apply_event_activity_logs_and_raises_on_error(self) -> None:
        app_mod, app, bp = _import_app_with_capture()
        registration = _build_registration()
        app.register_registration(registration)
        activity = self._activity(bp, "afdg_apply_event")
        payload = EventApplyRequest(
            graph_name="demo",
            graph_hash=registration.manifest.graph_hash,
            event_name="approval",
            state={"value": 1},
            event_payload={"ok": True},
        ).model_dump(mode="python")

        app.registry.apply_event = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(app_mod.logging, "exception") as log_exception:
            with pytest.raises(RuntimeError, match="boom"):
                await activity(payload)
        log_exception.assert_called_once()


# ── HTTP helpers ─────────────────────────────────────────────────────────────


class TestReadJson:
    """Test _read_json and _read_event_payload helpers."""

    def test_read_json_valid_dict(self) -> None:
        app_mod = _import_app()
        req = _make_http_request(body={"key": "value"})
        result = app_mod._read_json(req)
        assert result == {"key": "value"}

    def test_read_json_returns_none_for_list(self) -> None:
        app_mod = _import_app()
        req = _make_http_request(body=["a", "b"])
        result = app_mod._read_json(req)
        assert result is None

    def test_read_json_returns_none_for_invalid(self) -> None:
        app_mod = _import_app()
        req = _make_http_request(body_bytes=b"not json")
        result = app_mod._read_json(req)
        assert result is None

    def test_read_event_payload_valid(self) -> None:
        app_mod = _import_app()
        req = _make_http_request(body=["a", "b"])
        payload, parsed_ok = app_mod._read_event_payload(req)
        assert payload == ["a", "b"]
        assert parsed_ok is True

    def test_read_event_payload_empty_body_is_ok(self) -> None:
        app_mod = _import_app()
        req = _make_http_request()
        payload, parsed_ok = app_mod._read_event_payload(req)
        assert payload is None
        assert parsed_ok is True

    def test_read_event_payload_invalid_body_flags_error(self) -> None:
        app_mod = _import_app()
        req = _make_http_request(body_bytes=b"not json")
        payload, parsed_ok = app_mod._read_event_payload(req)
        assert payload is None
        assert parsed_ok is False


class TestJsonResponse:
    """Test _json_response helper."""

    def test_default_200(self) -> None:
        app_mod = _import_app()
        app_mod._json_response({"ok": True})
        call_kwargs = app_mod.func.HttpResponse.call_args
        assert call_kwargs.kwargs["status_code"] == 200
        body = json.loads(call_kwargs.kwargs["body"])
        assert body == {"ok": True}

    def test_custom_status_code(self) -> None:
        app_mod = _import_app()
        app_mod._json_response({"error": "not found"}, status_code=404)
        call_kwargs = app_mod.func.HttpResponse.call_args
        assert call_kwargs.kwargs["status_code"] == 404


# ── Contract models with graph_hash ──────────────────────────────────────────


class TestContractsWithGraphHash:
    """Verify all request models carry graph_hash."""

    def test_orchestration_input_has_graph_hash(self) -> None:
        oi = OrchestrationInput(graph_name="g", graph_hash="abc123", initial_state={})
        assert oi.graph_hash == "abc123"

    def test_node_execution_request_has_graph_hash(self) -> None:
        req = NodeExecutionRequest(graph_name="g", graph_hash="abc123", node_name="n", state={})
        assert req.graph_hash == "abc123"

    def test_route_resolution_request_has_graph_hash(self) -> None:
        req = RouteResolutionRequest(graph_name="g", graph_hash="abc123", node_name="n", state={})
        assert req.graph_hash == "abc123"

    def test_event_apply_request_has_graph_hash(self) -> None:
        req = EventApplyRequest(
            graph_name="g",
            graph_hash="abc123",
            event_name="e",
            state={},
            event_payload=None,
        )
        assert req.graph_hash == "abc123"

    def test_route_decision_wait_for_event_no_handler_name(self) -> None:
        """After Fix #2 — event_handler_name is removed, only event_name."""
        d = RouteDecision.wait_for_event(event_name="approval", resume_node="next")
        assert d.action == RouteAction.WAIT_FOR_EVENT
        assert d.event_name == "approval"
        assert d.resume_node == "next"
        assert not hasattr(d, "event_handler_name") or "event_handler_name" not in d.model_fields


# ── Manifest builder validation (Fix #3) ─────────────────────────────────────


class TestManifestBuilderValidation:
    """Test duplicate detection in ManifestBuilder."""

    def test_duplicate_node_name_raises(self) -> None:
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, terminal=True)
        with pytest.raises(ValueError, match="duplicate node name"):
            builder.add_node("a", increment, terminal=True)

    def test_duplicate_event_handler_raises(self) -> None:
        def handler(state: DemoState, payload: Any) -> dict[str, Any]:
            return {}

        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.add_event_handler("evt", handler)
        with pytest.raises(ValueError, match="duplicate event handler"):
            builder.add_event_handler("evt", handler)

    def test_same_handler_different_nodes_ok(self) -> None:
        """Same function used for two different node names should be fine."""
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="b")
        builder.add_node("b", increment, terminal=True)
        reg = builder.build()
        assert "a" in reg.manifest.nodes
        assert "b" in reg.manifest.nodes


# ── Registry hash-based lookup (Fix #1) ──────────────────────────────────────


class TestRegistryHashLookup:
    """Test GraphRegistry.registration_by_hash and composite keying."""

    def test_registration_by_hash_succeeds(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        graph_hash = registration.manifest.graph_hash
        found = reg.registration_by_hash("demo", graph_hash)
        assert found is registration

    def test_registration_by_hash_unknown_hash_raises(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        with pytest.raises(KeyError, match="unknown graph"):
            reg.registration_by_hash("demo", "bad_hash")

    def test_registration_by_hash_unknown_name_raises(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        with pytest.raises(KeyError, match="unknown graph"):
            reg.registration_by_hash("nonexistent", registration.manifest.graph_hash)

    def test_duplicate_registration_same_hash_raises(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(registration)

    def test_list_manifests_after_register(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        reg = GraphRegistry()
        reg.register(_build_registration())
        manifests = reg.list_manifests()
        assert len(manifests) == 1
        assert "graph_hash" in manifests[0]

    def test_manifest_shortcut(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        reg = GraphRegistry()
        registration = _build_registration()
        reg.register(registration)
        manifest = reg.manifest("demo")
        assert manifest.graph_name == "demo"

    def test_manifest_unknown_graph_raises(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        reg = GraphRegistry()
        with pytest.raises(KeyError, match="unknown graph"):
            reg.manifest("nope")


# ── Registry async operations ─────────────────────────────────────────────────


class TestRegistryAsyncOps:
    """Test execute_node, resolve_route, apply_event with graph_hash."""

    @pytest.fixture()
    def registry_and_hash(self) -> tuple[Any, str]:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        return reg, registration.manifest.graph_hash

    @pytest.mark.asyncio
    async def test_execute_node(self, registry_and_hash: tuple[Any, str]) -> None:
        reg, graph_hash = registry_and_hash
        result = await reg.execute_node("demo", graph_hash, "inc", {"value": 5})
        assert result["value"] == 6

    @pytest.mark.asyncio
    async def test_resolve_route_complete(self, registry_and_hash: tuple[Any, str]) -> None:
        reg, graph_hash = registry_and_hash
        decision = await reg.resolve_route("demo", graph_hash, "inc", {"value": 3})
        assert decision["action"] == "complete"

    @pytest.mark.asyncio
    async def test_resolve_route_next(self, registry_and_hash: tuple[Any, str]) -> None:
        reg, graph_hash = registry_and_hash
        decision = await reg.resolve_route("demo", graph_hash, "inc", {"value": 0})
        assert decision["action"] == "next"
        assert decision["next_node"] == "inc"


# ── Registry edge cases ──────────────────────────────────────────────────────


class TestRegistryEdgeCases:
    """Cover remaining registry branches for coverage."""

    @pytest.mark.asyncio
    async def test_resolve_route_terminal_node(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        builder = ManifestBuilder(graph_name="t", state_model=DemoState, version="1")
        builder.set_entrypoint("end")
        builder.add_node("end", increment, terminal=True)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        decision = await reg.resolve_route(
            "t", registration.manifest.graph_hash, "end", {"value": 0}
        )
        assert decision["action"] == "complete"

    @pytest.mark.asyncio
    async def test_resolve_route_next_node_static(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        builder = ManifestBuilder(graph_name="s", state_model=DemoState, version="1")
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="b")
        builder.add_node("b", increment, terminal=True)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        decision = await reg.resolve_route("s", registration.manifest.graph_hash, "a", {"value": 0})
        assert decision["action"] == "next"
        assert decision["next_node"] == "b"

    @pytest.mark.asyncio
    async def test_resolve_route_implicit_completion(self) -> None:
        """Node with no next_node, no route, not terminal → implicit complete."""
        from azure_functions_durable_graph.registry import GraphRegistry

        builder = ManifestBuilder(graph_name="ic", state_model=DemoState, version="1")
        builder.set_entrypoint("solo")
        # terminal=False, no next_node, no route
        builder.add_node("solo", increment)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        decision = await reg.resolve_route(
            "ic", registration.manifest.graph_hash, "solo", {"value": 0}
        )
        assert decision["action"] == "complete"
        assert "implicit" in (decision.get("note") or "")

    @pytest.mark.asyncio
    async def test_apply_event_unknown_handler_raises(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        registration = _build_registration()
        reg = GraphRegistry()
        reg.register(registration)
        with pytest.raises(KeyError, match="unknown event handler"):
            await reg.apply_event(
                "demo",
                registration.manifest.graph_hash,
                "nonexistent_event",
                {"value": 0},
                {},
            )

    @pytest.mark.asyncio
    async def test_apply_event_success(self) -> None:
        from azure_functions_durable_graph.registry import GraphRegistry

        class S(BaseModel):
            x: int = 0

        def evt_handler(state: S, payload: Any) -> dict[str, Any]:
            return {"x": state.x + payload["delta"]}

        builder = ManifestBuilder(graph_name="ev", state_model=S, version="1")
        builder.set_entrypoint("n")
        builder.add_node("n", lambda s: None, terminal=True)
        builder.add_event_handler("tick", evt_handler)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        result = await reg.apply_event(
            "ev", registration.manifest.graph_hash, "tick", {"x": 5}, {"delta": 10}
        )
        assert result["x"] == 15

    @pytest.mark.asyncio
    async def test_execute_node_with_none_result(self) -> None:
        """Node handler returning None should leave state unchanged."""
        from azure_functions_durable_graph.registry import GraphRegistry

        def noop(state: DemoState) -> None:
            pass

        builder = ManifestBuilder(graph_name="np", state_model=DemoState, version="1")
        builder.set_entrypoint("n")
        builder.add_node("n", noop, terminal=True)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        result = await reg.execute_node("np", registration.manifest.graph_hash, "n", {"value": 42})
        assert result["value"] == 42

    @pytest.mark.asyncio
    async def test_execute_node_with_model_result(self) -> None:
        """Node handler returning a BaseModel should merge correctly."""
        from azure_functions_durable_graph.registry import GraphRegistry

        def model_handler(state: DemoState) -> DemoState:
            return DemoState(value=state.value * 2)

        builder = ManifestBuilder(graph_name="mr", state_model=DemoState, version="1")
        builder.set_entrypoint("n")
        builder.add_node("n", model_handler, terminal=True)
        registration = builder.build()
        reg = GraphRegistry()
        reg.register(registration)
        result = await reg.execute_node("mr", registration.manifest.graph_hash, "n", {"value": 5})
        assert result["value"] == 10


# ── _normalize_route_decision branches ────────────────────────────────────────


class TestNormalizeRouteDecision:
    """Cover all branches of _normalize_route_decision."""

    def _make_node(self, *, next_node: str | None = None, terminal: bool = False) -> Any:
        from azure_functions_durable_graph.manifest import NodeDefinition

        return NodeDefinition(
            name="test",
            handler_name="test_handler",
            next_node=next_node,
            terminal=terminal,
        )

    def test_none_with_next_node(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node(next_node="b")
        result = _normalize_route_decision(node=node, raw=None)
        assert result.action == RouteAction.NEXT
        assert result.next_node == "b"

    def test_none_without_next_node(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        result = _normalize_route_decision(node=node, raw=None)
        assert result.action == RouteAction.COMPLETE

    def test_route_decision_passthrough(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        decision = RouteDecision.complete(note="done")
        result = _normalize_route_decision(node=node, raw=decision)
        assert result is decision

    def test_string_next(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        result = _normalize_route_decision(node=node, raw="step_b")
        assert result.action == RouteAction.NEXT
        assert result.next_node == "step_b"

    def test_string_complete(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        result = _normalize_route_decision(node=node, raw="__complete__")
        assert result.action == RouteAction.COMPLETE

    def test_dict_decision(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        result = _normalize_route_decision(node=node, raw={"action": "next", "next_node": "c"})
        assert result.action == RouteAction.NEXT
        assert result.next_node == "c"

    def test_unsupported_type_raises(self) -> None:
        from azure_functions_durable_graph.registry import _normalize_route_decision

        node = self._make_node()
        with pytest.raises(TypeError, match="unsupported route decision"):
            _normalize_route_decision(node=node, raw=42)  # type: ignore[arg-type]


# ── _merge_state edge case ────────────────────────────────────────────────────


class TestMergeState:
    """Cover the TypeError branch in _merge_state."""

    def test_unsupported_type_raises(self) -> None:
        from azure_functions_durable_graph.registry import _merge_state

        state = DemoState(value=1)
        with pytest.raises(TypeError, match="unsupported state merge"):
            _merge_state(state, 42, DemoState)  # type: ignore[arg-type]


# ── _callable_name ────────────────────────────────────────────────────────────


class TestCallableName:
    """Test _callable_name uses module.qualname."""

    def test_regular_function(self) -> None:
        from azure_functions_durable_graph.manifest import _callable_name

        name = _callable_name(increment)
        # Should contain module and qualname
        assert "increment" in name
        assert "." in name

    def test_lambda(self) -> None:
        from azure_functions_durable_graph.manifest import _callable_name

        fn = lambda x: x  # noqa: E731
        name = _callable_name(fn)
        assert "<lambda>" in name

    def test_none_raises(self) -> None:
        from azure_functions_durable_graph.manifest import _callable_name

        with pytest.raises(ValueError, match="callable cannot be None"):
            _callable_name(None)


# ── NodeDefinition validation ─────────────────────────────────────────────────


class TestNodeDefinitionValidation:
    """Test model_validator on NodeDefinition."""

    def test_terminal_with_next_node_raises(self) -> None:
        from azure_functions_durable_graph.manifest import NodeDefinition

        with pytest.raises(ValueError, match="terminal nodes cannot"):
            NodeDefinition(
                name="n",
                handler_name="h",
                terminal=True,
                next_node="other",
            )

    def test_terminal_with_route_raises(self) -> None:
        from azure_functions_durable_graph.manifest import NodeDefinition

        with pytest.raises(ValueError, match="terminal nodes cannot"):
            NodeDefinition(
                name="n",
                handler_name="h",
                terminal=True,
                route_handler_name="r",
            )


# ── ManifestBuilder build-time validation ─────────────────────────────────────


class TestManifestBuilderBuildValidation:
    """Test build() validation: entrypoint must be set and reference a node."""

    def test_entrypoint_not_registered_raises(self) -> None:
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("ghost")
        with pytest.raises(ValueError, match="entrypoint must reference"):
            builder.build()

    def test_openapi_schema_fragment(self) -> None:
        registration = _build_registration()
        frag = registration.manifest.openapi_schema_fragment()
        assert frag["graph_name"] == "demo"
        assert "graph_hash" in frag
        assert "entrypoint" in frag


# ── RouteDecision model_validator (Fix #6) ─────────────────────────────────────


class TestRouteDecisionValidator:
    """Test model_validator on RouteDecision enforces field requirements."""

    def test_next_without_next_node_raises(self) -> None:
        with pytest.raises(ValueError, match="action 'next' requires next_node"):
            RouteDecision(action=RouteAction.NEXT)

    def test_next_with_next_node_ok(self) -> None:
        d = RouteDecision(action=RouteAction.NEXT, next_node="step_b")
        assert d.next_node == "step_b"

    def test_wait_for_event_without_event_name_raises(self) -> None:
        with pytest.raises(ValueError, match="requires both event_name and resume_node"):
            RouteDecision(
                action=RouteAction.WAIT_FOR_EVENT,
                resume_node="next",
            )

    def test_wait_for_event_without_resume_node_raises(self) -> None:
        with pytest.raises(ValueError, match="requires both event_name and resume_node"):
            RouteDecision(
                action=RouteAction.WAIT_FOR_EVENT,
                event_name="approval",
            )

    def test_wait_for_event_with_both_ok(self) -> None:
        d = RouteDecision(
            action=RouteAction.WAIT_FOR_EVENT,
            event_name="approval",
            resume_node="after_approval",
        )
        assert d.event_name == "approval"
        assert d.resume_node == "after_approval"

    def test_complete_with_next_node_raises(self) -> None:
        with pytest.raises(ValueError, match="action 'complete' must not set next_node"):
            RouteDecision(action=RouteAction.COMPLETE, next_node="oops")

    def test_complete_ok(self) -> None:
        d = RouteDecision(action=RouteAction.COMPLETE, note="done")
        assert d.action == RouteAction.COMPLETE

    def test_factory_next(self) -> None:
        d = RouteDecision.next("b")
        assert d.action == RouteAction.NEXT
        assert d.next_node == "b"

    def test_factory_complete(self) -> None:
        d = RouteDecision.complete()
        assert d.action == RouteAction.COMPLETE

    def test_factory_wait_for_event(self) -> None:
        d = RouteDecision.wait_for_event(event_name="e", resume_node="r")
        assert d.action == RouteAction.WAIT_FOR_EVENT


# ── ManifestBuilder edge reference validation (Fix #7) ────────────────────────


class TestManifestBuilderEdgeValidation:
    """Test build-time edge reference and reachability checks."""

    def test_unknown_next_node_raises(self) -> None:
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="nonexistent")
        with pytest.raises(ValueError, match="references unknown next_node"):
            builder.build()

    def test_unreachable_node_raises(self) -> None:
        """Node 'orphan' is registered but not reachable from entrypoint."""
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, terminal=True)
        builder.add_node("orphan", increment, terminal=True)
        with pytest.raises(ValueError, match="nodes unreachable from entrypoint"):
            builder.build()

    def test_all_reachable_ok(self) -> None:
        """Linear chain: a -> b -> c (terminal). All reachable."""
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="b")
        builder.add_node("b", increment, next_node="c")
        builder.add_node("c", increment, terminal=True)
        reg = builder.build()
        assert len(reg.manifest.nodes) == 3

    def test_reachable_via_route_only(self) -> None:
        """Node with route (no static next_node) — sibling only reachable via route.
        Since BFS only follows static next_node, route-only targets must be next_node-connected.
        This tests that the builder does NOT false-positive on route-connected nodes."""
        # Node 'a' has a route but also static next_node='b'
        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="b", route=router)
        builder.add_node("b", increment, terminal=True)
        reg = builder.build()
        assert len(reg.manifest.nodes) == 2


# ── Tests for Oracle Second Review Fixes ─────────────────────────────────────


class TestRouteTargetValidation:
    """Fix #1: Runtime validation of route decision targets against manifest."""

    @pytest.mark.asyncio
    async def test_resolve_route_unknown_next_node(self) -> None:
        """Dynamic route returning unknown node name raises ValueError."""
        from azure_functions_durable_graph.registry import GraphRegistry

        def bad_router(state: DemoState) -> RouteDecision:
            # Returns a node name that doesn't exist in the manifest
            return RouteDecision.next("does_not_exist")

        builder = ManifestBuilder(graph_name="test", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, route=bad_router, next_node="b")
        builder.add_node("b", increment, terminal=True)
        reg = builder.build()

        registry = GraphRegistry()
        registry.register(reg)

        with pytest.raises(ValueError, match="unknown node 'does_not_exist'"):
            await registry.resolve_route("test", reg.manifest.graph_hash, "a", {"value": 0})

    @pytest.mark.asyncio
    async def test_resolve_route_unknown_resume_node(self) -> None:
        """Route returning wait_for_event with unknown resume_node raises ValueError."""
        from azure_functions_durable_graph.registry import GraphRegistry

        def event_router(state: DemoState) -> RouteDecision:
            return RouteDecision.wait_for_event(event_name="approval", resume_node="does_not_exist")

        builder = ManifestBuilder(graph_name="test2", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, route=event_router, next_node="b")
        builder.add_node("b", increment, terminal=True)
        reg = builder.build()

        registry = GraphRegistry()
        registry.register(reg)

        with pytest.raises(ValueError, match="unknown resume_node 'does_not_exist'"):
            await registry.resolve_route("test2", reg.manifest.graph_hash, "a", {"value": 0})


class TestRouteDecisionFieldCleaning:
    """Fix #3: Spurious fields are cleaned per action type."""

    def test_next_clears_event_fields(self) -> None:
        """action=NEXT should clear event_name and resume_node."""
        d = RouteDecision(
            action=RouteAction.NEXT,
            next_node="b",
            event_name="stale",
            resume_node="stale",
        )
        assert d.next_node == "b"
        assert d.event_name is None
        assert d.resume_node is None


class TestLazyImportAndManifestEdges:
    def test_package_getattr_raises_helpful_import_error_without_azure_sdk(self) -> None:
        import azure_functions_durable_graph as pkg

        saved_app = sys.modules.get("azure_functions_durable_graph.app")
        try:
            sys.modules.pop("azure_functions_durable_graph.app", None)
            with patch.dict(
                "sys.modules",
                {
                    "azure": MagicMock(),
                    "azure.functions": None,
                    "azure.durable_functions": None,
                },
                clear=False,
            ):
                with pytest.raises(ImportError, match="DurableGraphApp requires"):
                    getattr(pkg, "DurableGraphApp")
        finally:
            if saved_app is not None:
                sys.modules["azure_functions_durable_graph.app"] = saved_app

    def test_manifest_builder_rejects_different_handlers_with_same_callable_name(self) -> None:
        def make_handler() -> Any:
            def duplicate_name(state: DemoState) -> dict[str, Any]:
                _ = state
                return {"value": 1}

            return duplicate_name

        h1 = make_handler()
        h2 = make_handler()

        builder = ManifestBuilder(graph_name="collision", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", h1, next_node="b")
        with pytest.raises(ValueError, match="already registered to a different callable"):
            builder.add_node("b", h2, terminal=True)

    def test_manifest_builder_rejects_different_routes_with_same_callable_name(self) -> None:
        def make_route() -> Any:
            def duplicate_route(state: DemoState) -> RouteDecision:
                _ = state
                return RouteDecision.complete()

            return duplicate_route

        r1 = make_route()
        r2 = make_route()

        builder = ManifestBuilder(graph_name="route-collision", state_model=DemoState)
        builder.set_entrypoint("a")
        builder.add_node("a", increment, next_node="b", route=r1)
        with pytest.raises(ValueError, match="route handler name .* already registered"):
            builder.add_node("b", increment, terminal=True, route=r2)

    def test_manifest_builder_reachability_tolerates_missing_node_popped_from_queue(self) -> None:
        from azure_functions_durable_graph.manifest import NodeDefinition

        class FlakyNodeMap(dict[str, NodeDefinition]):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._entrypoint_checks = 0

            def __contains__(self, key: object) -> bool:
                if key == "ghost":
                    self._entrypoint_checks += 1
                    return self._entrypoint_checks == 1
                return super().__contains__(key)

        builder = ManifestBuilder(graph_name="flaky", state_model=DemoState)
        builder.entrypoint = "ghost"
        builder._nodes = FlakyNodeMap(
            {
                "a": NodeDefinition(name="a", handler_name="h", terminal=True),
            }
        )

        with pytest.raises(ValueError, match="nodes unreachable from entrypoint"):
            builder.build()

    def test_wait_for_event_clears_next_node(self) -> None:
        """action=WAIT_FOR_EVENT should clear next_node."""
        d = RouteDecision(
            action=RouteAction.WAIT_FOR_EVENT,
            event_name="approval",
            resume_node="b",
            next_node="stale",
        )
        assert d.event_name == "approval"
        assert d.resume_node == "b"
        assert d.next_node is None

    def test_complete_clears_event_fields(self) -> None:
        """action=COMPLETE should clear event_name and resume_node."""
        d = RouteDecision(
            action=RouteAction.COMPLETE,
            event_name="stale",
            resume_node="stale",
        )
        assert d.event_name is None
        assert d.resume_node is None
