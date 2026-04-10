"""Tests for the public API surface of azure-functions-durable-graph v0.1."""

from typing import Any

from pydantic import BaseModel
import pytest

import azure_functions_durable_graph
from azure_functions_durable_graph import (
    GraphManifest,
    GraphRegistration,
    ManifestBuilder,
    RouteAction,
    RouteDecision,
)

# ---------------------------------------------------------------------------
# 1. API Surface — only the declared exports exist
# ---------------------------------------------------------------------------


class TestAPISurface:
    """Verify __all__ matches exactly the declared public names + __version__."""

    def test_all_exports(self) -> None:
        assert set(azure_functions_durable_graph.__all__) == {
            "__version__",
            "DurableGraphApp",
            "GraphManifest",
            "GraphRegistration",
            "ManifestBuilder",
            "RouteAction",
            "RouteDecision",
        }

    def test_version_is_0_1_0(self) -> None:
        assert azure_functions_durable_graph.__version__ == "0.1.0"

    def test_manifest_builder_is_class(self) -> None:
        assert isinstance(ManifestBuilder, type)

    def test_graph_manifest_is_class(self) -> None:
        assert isinstance(GraphManifest, type)

    def test_graph_registration_is_class(self) -> None:
        # GraphRegistration is a dataclass
        assert hasattr(GraphRegistration, "__dataclass_fields__")

    def test_route_action_is_enum(self) -> None:
        assert hasattr(RouteAction, "NEXT")
        assert hasattr(RouteAction, "COMPLETE")
        assert hasattr(RouteAction, "WAIT_FOR_EVENT")

    def test_route_decision_is_class(self) -> None:
        assert isinstance(RouteDecision, type)

    def test_durable_graph_app_importable(self) -> None:
        # DurableGraphApp may be None in pure unit test environments
        # without Azure packages, but it must be in __all__
        assert "DurableGraphApp" in azure_functions_durable_graph.__all__


# ---------------------------------------------------------------------------
# 2. RouteDecision factory methods
# ---------------------------------------------------------------------------


class TestRouteDecisionFactories:
    """Verify RouteDecision convenience constructors."""

    def test_next(self) -> None:
        d = RouteDecision.next("step_two")
        assert d.action == RouteAction.NEXT
        assert d.next_node == "step_two"

    def test_complete(self) -> None:
        d = RouteDecision.complete(note="done")
        assert d.action == RouteAction.COMPLETE
        assert d.note == "done"

    def test_wait_for_event(self) -> None:
        d = RouteDecision.wait_for_event(
            event_name="approval",
            resume_node="next_step",
        )
        assert d.action == RouteAction.WAIT_FOR_EVENT
        assert d.event_name == "approval"
        assert d.resume_node == "next_step"


# ---------------------------------------------------------------------------
# 3. ManifestBuilder basic workflow
# ---------------------------------------------------------------------------


class TestManifestBuilderBasic:
    """Verify ManifestBuilder produces valid registrations."""

    def test_build_minimal_graph(self) -> None:
        class State(BaseModel):
            value: int = 0

        def handler(state: State) -> dict[str, Any]:
            return {"value": state.value + 1}

        b = ManifestBuilder(graph_name="test", state_model=State)
        b.set_entrypoint("only")
        b.add_node("only", handler, terminal=True)
        reg = b.build()

        assert reg.manifest.graph_name == "test"
        assert reg.manifest.entrypoint == "only"
        assert "only" in reg.manifest.nodes
        assert reg.manifest.graph_hash  # non-empty

    def test_build_without_entrypoint_raises(self) -> None:
        class State(BaseModel):
            value: int = 0

        b = ManifestBuilder(graph_name="test", state_model=State)

        with pytest.raises(ValueError, match="entrypoint"):
            b.build()
