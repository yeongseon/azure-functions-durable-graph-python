"""Regression guard for the self-contained endpoint-metadata decision.

ADR-0001 records that ``azure-functions-durable-graph`` deliberately does **not**
emit the shared ``endpoint`` metadata namespace
(``_azure_functions_metadata["endpoint"]``) that sibling producer packages
(``azure-functions-validation``, ``azure-functions-langgraph``) attach to their
route handlers for cross-package OpenAPI discovery.

This test locks that decision in: if a future change accidentally starts writing
the shared namespace onto a runtime handler, it fails here and forces a conscious
re-evaluation of ADR-0001.

Like :mod:`tests.test_openapi`, this introspects the *real* durable-functions
blueprint internals, so the app/openapi modules are reloaded against the genuine
installed SDK (``test_app`` leaves mocked SDK bindings cached in ``sys.modules``).
"""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

# The shared toolkit attribute + namespace key used by sibling producer packages.
_HANDLER_METADATA_ATTR = "_azure_functions_metadata"
_ENDPOINT_NAMESPACE = "endpoint"

# Maximum decorator depth to walk when chasing ``__wrapped__`` (mirrors the
# openapi reader's bounded walk).
_MAX_WRAPPED_DEPTH = 20


def _reload_with_real_sdk() -> ModuleType:
    import azure_functions_durable_graph.app as app_mod
    import azure_functions_durable_graph.openapi as openapi_mod

    importlib.reload(openapi_mod)
    return importlib.reload(app_mod)


@pytest.fixture()
def app_mod() -> ModuleType:
    return _reload_with_real_sdk()


def _endpoint_namespace(handler: object) -> object | None:
    """Return the ``endpoint`` namespace payload on *handler*, walking wrappers."""
    current: object | None = handler
    for _ in range(_MAX_WRAPPED_DEPTH):
        if current is None:
            break
        metadata = getattr(current, _HANDLER_METADATA_ATTR, None)
        if isinstance(metadata, dict) and _ENDPOINT_NAMESPACE in metadata:
            payload: object = metadata[_ENDPOINT_NAMESPACE]
            return payload
        current = getattr(current, "__wrapped__", None)
    return None


def _runtime_handlers(app_mod: ModuleType) -> list[object]:
    """Every registered handler, gathered via BOTH access paths.

    ``get_user_function()`` is the public SDK accessor; ``builder._function._func``
    is the exact object the ``azure-functions-openapi`` reader inspects. These are
    the same object today, but collecting both guards against a future SDK change
    that diverges them, so the regression genuinely covers the reader's path.
    """
    blueprint = app_mod.DurableGraphApp().blueprint
    handlers: list[object] = []
    for builder in blueprint._function_builders:
        function = builder.build()
        handlers.append(function.get_user_function())
        # The path the openapi reader walks: builder._function._func.
        reader_func = getattr(getattr(builder, "_function", None), "_func", None)
        if reader_func is not None and reader_func not in handlers:
            handlers.append(reader_func)
    return handlers


def test_no_runtime_handler_emits_endpoint_namespace(app_mod: ModuleType) -> None:
    """ADR-0001: durable-graph stays self-contained — no ``endpoint`` namespace."""
    handlers = _runtime_handlers(app_mod)
    assert handlers, "expected the blueprint to register runtime handlers"

    offenders = [
        getattr(handler, "__name__", repr(handler))
        for handler in handlers
        if _endpoint_namespace(handler) is not None
    ]
    assert offenders == [], (
        "durable-graph handlers must NOT emit the shared 'endpoint' metadata "
        "namespace (see docs/decisions/0001-endpoint-metadata-self-contained.md). "
        f"Offending handlers: {offenders}"
    )
