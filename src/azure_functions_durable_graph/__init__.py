"""azure-functions-durable-graph package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .contracts import RouteAction, RouteDecision
from .manifest import GraphManifest, GraphRegistration, ManifestBuilder

if TYPE_CHECKING:
    from .app import DurableGraphApp

__all__ = [
    "__version__",
    "DurableGraphApp",
    "GraphManifest",
    "GraphRegistration",
    "ManifestBuilder",
    "RouteAction",
    "RouteDecision",
]

__version__ = "0.1.0"


def __getattr__(name: str) -> object:
    if name == "DurableGraphApp":
        try:
            from .app import DurableGraphApp as _cls

            return _cls
        except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
            raise ImportError(
                "DurableGraphApp requires 'azure-functions' and 'azure-functions-durable'. "
                "Install them with: pip install azure-functions azure-functions-durable"
            ) from exc
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
