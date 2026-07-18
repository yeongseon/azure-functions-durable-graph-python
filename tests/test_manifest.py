from typing import Any

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder


class DemoState(BaseModel):
    counter: int = 0


def first(state: DemoState) -> dict[str, Any]:
    return {"counter": state.counter + 1}


def second(state: DemoState) -> dict[str, Any]:
    return {"counter": state.counter + 1}


def test_manifest_hash_is_stable_for_same_topology() -> None:
    builder_a = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_a.set_entrypoint("first")
    builder_a.add_node("first", first, next_node="second")
    builder_a.add_node("second", second, terminal=True)
    reg_a = builder_a.build()

    builder_b = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder_b.set_entrypoint("first")
    builder_b.add_node("first", first, next_node="second")
    builder_b.add_node("second", second, terminal=True)
    reg_b = builder_b.build()

    assert reg_a.manifest.graph_hash == reg_b.manifest.graph_hash



# ---------------------------------------------------------------------------
# Build-time validation: explicit unit assertions on ``ManifestBuilder.build``
# guard rails and the ``NodeDefinition`` invariants (issue #83).
# ---------------------------------------------------------------------------


def test_build_requires_entrypoint() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.add_node("first", first, terminal=True)
    with pytest.raises(ValueError, match="entrypoint must be set"):
        builder.build()


def test_build_entrypoint_must_reference_registered_node() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("missing")
    builder.add_node("first", first, terminal=True)
    with pytest.raises(ValueError, match="entrypoint must reference a registered node"):
        builder.build()


def test_build_rejects_unknown_next_node() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("first")
    builder.add_node("first", first, next_node="nowhere")
    with pytest.raises(ValueError, match="unknown next_node"):
        builder.build()


def test_build_rejects_unreachable_nodes() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("first")
    builder.add_node("first", first, terminal=True)
    builder.add_node("second", second, terminal=True)
    with pytest.raises(ValueError, match="unreachable from entrypoint"):
        builder.build()


def test_build_rejects_duplicate_node_name() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("first")
    builder.add_node("first", first, terminal=True)
    with pytest.raises(ValueError, match="duplicate node name"):
        builder.add_node("first", second, terminal=True)


def test_terminal_node_cannot_define_next_node() -> None:
    builder = ManifestBuilder(graph_name="demo", state_model=DemoState, version="1")
    builder.set_entrypoint("first")
    with pytest.raises(ValueError, match="terminal nodes cannot define"):
        builder.add_node("first", first, next_node="second", terminal=True)