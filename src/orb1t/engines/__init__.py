"""Engine adapters and registry."""

from .base import (
    CAPABILITIES,
    EngineAdapter,
    EngineCapabilities,
    EngineHealth,
    EngineRequest,
    EngineResponse,
    SessionInfo,
)
from .opencode import OpenCodeEngine
from .registry import available_engines, build_engine, register_engine, unregister_engine

__all__ = [
    "CAPABILITIES",
    "EngineAdapter",
    "EngineCapabilities",
    "EngineHealth",
    "EngineRequest",
    "EngineResponse",
    "SessionInfo",
    "OpenCodeEngine",
    "available_engines",
    "build_engine",
    "register_engine",
    "unregister_engine",
]
