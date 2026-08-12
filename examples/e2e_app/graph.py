"""Deterministic durable graph used by the real-Azure e2e certification.

Purpose-built for `tests/e2e` — kept separate from the user-facing
`examples/data_pipeline` so docs can evolve without breaking the release gate.

Topology (no external events, no LLM, fully deterministic)::

    extract -> transform -> load (terminal)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from azure_functions_durable_graph import ManifestBuilder


class PipelineState(BaseModel):
    """State flowing through the certification pipeline."""

    source_url: str
    raw_records: list[dict[str, Any]] = Field(default_factory=list)
    transformed_records: list[dict[str, Any]] = Field(default_factory=list)
    load_result: str | None = None
    record_count: int = 0


def extract(state: PipelineState) -> dict[str, Any]:
    raw = [
        {"id": 1, "name": "  Alice  ", "score": "85"},
        {"id": 2, "name": "  Bob  ", "score": "92"},
        {"id": 3, "name": "  Carol  ", "score": "78"},
    ]
    return {"raw_records": raw, "record_count": len(raw)}


def transform(state: PipelineState) -> dict[str, Any]:
    transformed = [
        {"id": r["id"], "name": str(r["name"]).strip(), "score": int(r["score"])}
        for r in state.raw_records
    ]
    return {"transformed_records": transformed}


def load(state: PipelineState) -> dict[str, Any]:
    count = len(state.transformed_records)
    return {"load_result": f"Loaded {count} records to {state.source_url}/output"}


builder = ManifestBuilder(
    graph_name="e2e_pipeline",
    state_model=PipelineState,
    version="0.1.0",
    metadata={"example": True, "profile": "e2e-certification"},
)
builder.set_entrypoint("extract")
builder.add_node("extract", extract, next_node="transform")
builder.add_node("transform", transform, next_node="load")
builder.add_node("load", load, terminal=True)

registration = builder.build()
