"""Real-Azure end-to-end tests for azure-functions-durable-graph.

These drive the NATIVE Durable HTTP routes on a live Azure Functions host that
was deployed from the release commit's own source (see the e2e-azure workflow
and examples/e2e_app). They are the runtime-behavior proof behind the release
gate's Azure certification.

Usage::

    E2E_BASE_URL=https://<app>.azurewebsites.net pytest tests/e2e -v -m e2e

Every test is marked ``e2e`` and skips automatically when ``E2E_BASE_URL`` is
unset (so ordinary unit runs, which exclude ``-m e2e``, never hit the network).
"""

from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
SKIP_REASON = "E2E_BASE_URL not set — skipping real-Azure e2e tests"
GRAPH = "e2e_pipeline"

# Durable-on-Y1: cold start + extension startup + orchestration completion.
POLL_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 5
TERMINAL_FAILURE = {"Failed", "Terminated", "Canceled"}

pytestmark = pytest.mark.e2e


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


@pytest.fixture(scope="session", autouse=True)
def warmup() -> None:
    """Retry /api/health until the Consumption cold-start finishes (max 5 min)."""
    if not BASE_URL:
        pytest.skip(SKIP_REASON)
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(_url("/api/health"), timeout=15)
            if r.status_code == 200:
                return
        except requests.RequestException as exc:  # pragma: no cover - network
            last_exc = exc
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"Function App never became healthy: {last_exc}")


def _graph_names(health_body: dict) -> set[str]:
    names: set[str] = set()
    for g in health_body.get("registered_graphs", []):
        if isinstance(g, dict):
            name = g.get("graph_name") or g.get("name")
            if name:
                names.add(name)
        elif isinstance(g, str):
            names.add(g)
    return names


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_health_lists_registered_graph() -> None:
    r = requests.get(_url("/api/health"), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True, body
    assert GRAPH in _graph_names(body), body


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_orchestration_runs_to_completion() -> None:
    # Start the orchestration through the public native route.
    start = requests.post(
        _url(f"/api/graphs/{GRAPH}/runs"),
        json={"input": {"source_url": "https://example.test/data"}},
        timeout=60,
    )
    assert start.status_code in (200, 201, 202), start.text
    started = start.json()
    instance_id = started.get("instanceId") or started.get("id")
    assert instance_id, f"no instance id in start response: {started}"

    # Poll our own public status route (the API contract we certify) until the
    # orchestration reaches a terminal state.
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_body: dict = {}
    while time.time() < deadline:
        r = requests.get(_url(f"/api/runs/{instance_id}"), timeout=30)
        assert r.status_code == 200, r.text
        last_body = r.json()
        status = last_body.get("runtime_status")
        if status == "Completed":
            break
        assert status not in TERMINAL_FAILURE, last_body
        time.sleep(POLL_INTERVAL_SECONDS)
    else:  # pragma: no cover - only on timeout
        raise AssertionError(f"orchestration did not complete in time: {last_body}")

    # Completion alone is not enough — assert the deterministic output payload.
    output = last_body.get("output")
    assert output is not None, last_body
    load_result = output.get("load_result") if isinstance(output, dict) else None
    assert load_result and "Loaded 3 records" in load_result, last_body


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_unknown_graph_returns_404() -> None:
    r = requests.post(
        _url("/api/graphs/does-not-exist/runs"),
        json={"input": {}},
        timeout=30,
    )
    assert r.status_code == 404, r.text
