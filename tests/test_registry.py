from typing import Any

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision
from azure_functions_durable_graph.registry import GraphRegistry


class DemoState(BaseModel):
    message: str
    approved: bool | None = None
    result: str | None = None


def classify(state: DemoState) -> dict[str, Any]:
    return {}


def route(state: DemoState) -> RouteDecision:
    if state.approved:
        return RouteDecision.next("finish")
    return RouteDecision.wait_for_event(
        event_name="approval",
        resume_node="finish",
    )


def finish(state: DemoState) -> dict[str, str]:
    return {"result": f"done:{state.message}"}


def apply_approval(state: DemoState, payload: Any) -> dict[str, bool]:
    return {"approved": bool(payload["approved"])}


@pytest.fixture()
def registry() -> tuple[GraphRegistry, str]:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("classify")
    builder.add_node("classify", classify, route=route)
    builder.add_event_handler("approval", apply_approval)
    builder.add_node("finish", finish, terminal=True)

    registration = builder.build()
    reg = GraphRegistry()
    reg.register(registration)
    return reg, registration.manifest.graph_hash


@pytest.mark.asyncio
async def test_registry_routes_to_wait_for_event(
    registry: tuple[GraphRegistry, str],
) -> None:
    reg, graph_hash = registry
    decision = await reg.resolve_route("demo", graph_hash, "classify", {"message": "hello"})
    assert decision["action"] == "wait_for_event"
    assert decision["event_name"] == "approval"


@pytest.mark.asyncio
async def test_registry_applies_event(registry: tuple[GraphRegistry, str]) -> None:
    reg, graph_hash = registry
    new_state = await reg.apply_event(
        "demo",
        graph_hash,
        "approval",
        {"message": "hello"},
        {"approved": True},
    )
    assert new_state["approved"] is True


@pytest.mark.asyncio
async def test_registration_by_hash_returns_correct_version(
    registry: tuple[GraphRegistry, str],
) -> None:
    """Verify that registration_by_hash resolves the exact version, not just the latest."""
    reg, graph_hash = registry
    registration = reg.registration_by_hash("demo", graph_hash)
    assert registration.manifest.graph_hash == graph_hash
    assert registration.manifest.graph_name == "demo"


def test_registration_by_hash_unknown_hash_raises() -> None:
    """Verify that an unknown hash raises KeyError."""
    reg = GraphRegistry()
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("classify")
    builder.add_node("classify", classify, next_node="finish")
    builder.add_node("finish", finish, terminal=True)
    reg.register(builder.build())

    with pytest.raises(KeyError, match="unknown graph"):
        reg.registration_by_hash("demo", "nonexistent_hash")


def test_multi_version_registration() -> None:
    """Multiple versions of the same graph should coexist by hash."""
    reg = GraphRegistry()

    builder_v1 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_v1.set_entrypoint("classify")
    builder_v1.add_node("classify", classify, next_node="finish")
    builder_v1.add_node("finish", finish, terminal=True)
    reg_v1 = builder_v1.build()
    reg.register(reg_v1)
    hash_v1 = reg_v1.manifest.graph_hash

    builder_v2 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="2")
    builder_v2.set_entrypoint("classify")
    builder_v2.add_node("classify", classify, next_node="finish")
    builder_v2.add_node("finish", finish, terminal=True)
    reg_v2 = builder_v2.build()
    reg.register(reg_v2)
    hash_v2 = reg_v2.manifest.graph_hash

    assert hash_v1 != hash_v2
    # Latest by name is v2
    assert reg.manifest("demo").version == "2"
    # But by-hash still resolves v1
    assert reg.registration_by_hash("demo", hash_v1).manifest.version == "1"
    assert reg.registration_by_hash("demo", hash_v2).manifest.version == "2"



def test_versions_tracks_registration_history() -> None:
    reg = GraphRegistry()

    builder_v1 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_v1.set_entrypoint("classify")
    builder_v1.add_node("classify", classify, next_node="finish")
    builder_v1.add_node("finish", finish, terminal=True)
    reg.register(builder_v1.build())

    builder_v2 = ManifestBuilder(graph_name="demo", state_model=DemoState, version="2")
    builder_v2.set_entrypoint("classify")
    builder_v2.add_node("classify", classify, next_node="finish")
    builder_v2.add_node("finish", finish, terminal=True)
    with pytest.warns(UserWarning, match="re-registered with a new hash"):
        reg.register(builder_v2.build())

    assert reg.versions("demo") == ["1", "2"]


def test_versions_unknown_graph_raises() -> None:
    reg = GraphRegistry()
    with pytest.raises(KeyError, match="unknown graph"):
        reg.versions("nope")