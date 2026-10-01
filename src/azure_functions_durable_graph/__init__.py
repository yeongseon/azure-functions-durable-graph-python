"""azure-functions-durable-graph package."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING
import warnings

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

__version__ = "0.3.0"


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


if sys.version_info < (3, 11):
    warnings.warn(
        "azure-functions-durable-graph will drop support for Python 3.10 "
        "in its next minor release. "
        "Python 3.10 reaches end of life in October 2026; upgrade to Python 3.11 "
        "or newer to keep receiving updates.",
        FutureWarning,
        stacklevel=2,
    )
