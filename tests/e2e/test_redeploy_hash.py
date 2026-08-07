"""E2E scenario: hash-fencing across a redeploy.

When a graph is re-registered with a changed manifest (a new ``version`` or
changed node identity) it gets a new ``graph_hash``. In-flight runs stay pinned
new runs use the latest hash. This scenario asserts:

* changing the manifest structure (version + node identity) changes the ``graph_hash``;
* both versions remain independently runnable via their own hash;
* looking up an unknown/stale hash raises ``KeyError``.
"""

from __future__ import annotations

from typing import Any
import warnings

from pydantic import BaseModel
import pytest

from azure_functions_durable_graph import ManifestBuilder, RouteDecision
from azure_functions_durable_graph.registry import GraphRegistry

from ._harness import run_graph


class _State(BaseModel):
    value: int = 0


def _plus_one(state: _State) -> dict[str, Any]:
    return {"value": state.value + 1}


def _plus_ten(state: _State) -> dict[str, Any]:
    return {"value": state.value + 10}


def _terminal_router(_state: _State) -> RouteDecision:
    return RouteDecision.complete()


def _build(version: str, handler: Any) -> Any:
    builder = ManifestBuilder(graph_name="calc", state_model=_State, version=version)
    builder.set_entrypoint("step")
    builder.add_node("step", handler, route=_terminal_router, terminal=False)
    return builder.build()


def test_changed_handler_changes_hash_and_runs_are_fenced() -> None:
    reg_v1 = _build("1", _plus_one)
    reg_v2 = _build("2", _plus_ten)

    hash_v1 = reg_v1.manifest.graph_hash
    hash_v2 = reg_v2.manifest.graph_hash

    # Different manifest structure (new version + handler name) ⇒ different hash.
    assert hash_v1 != hash_v2

    registry = GraphRegistry()
    registry.register(reg_v1)
    # Re-registering the same graph name with a new hash warns but is allowed.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        registry.register(reg_v2)
    assert any(
        "re-registered with a new hash" in str(w.message) for w in caught
    ), "expected a re-registration warning when registering a new hash for 'calc'"

    # A run pinned to v1's hash uses v1 logic (+1); v2's hash uses v2 logic (+10).
    out_v1 = run_graph(
        registry,
        graph_name="calc",
        graph_hash=hash_v1,
        initial_state={"value": 0},
    )
    out_v2 = run_graph(
        registry,
        graph_name="calc",
        graph_hash=hash_v2,
        initial_state={"value": 0},
    )

    assert out_v1.output["state"] == {"value": 1}
    assert out_v1.output["graph_hash"] == hash_v1
    assert out_v2.output["state"] == {"value": 10}
    assert out_v2.output["graph_hash"] == hash_v2

    # Registry history records both versions.
    assert registry.versions("calc") == ["1", "2"]


def test_unknown_hash_lookup_raises() -> None:
    registry = GraphRegistry()
    registry.register(_build("1", _plus_one))

    with pytest.raises(KeyError):
        registry.registration_by_hash("calc", "deadbeefdeadbeef")

    # And driving a run against a stale hash surfaces the same failure.
    with pytest.raises(KeyError):
        run_graph(
            registry,
            graph_name="calc",
            graph_hash="deadbeefdeadbeef",
            initial_state={"value": 0},
        )
