"""Composable runtime services for HTTP, CLI, and embedded use."""

from core.runtime.events import (
    JsonlWorkflowEventLog,
    MemoryWorkflowEventLog,
    WorkflowEvent,
    WorkflowEventLog,
)
from core.runtime.profiles import RuntimeProfile, list_profiles, load_profile


def __getattr__(name: str):
    if name in {
        "DiagramRuntime",
        "JsonlWorkflowEventPlugin",
        "MemoryRevisionPlugin",
        "OpenAIModelPlugin",
        "RuntimePlugin",
    }:
        from core.runtime.registry import (
            DiagramRuntime,
            JsonlWorkflowEventPlugin,
            MemoryRevisionPlugin,
            OpenAIModelPlugin,
            RuntimePlugin,
        )

        return {
            "DiagramRuntime": DiagramRuntime,
            "JsonlWorkflowEventPlugin": JsonlWorkflowEventPlugin,
            "MemoryRevisionPlugin": MemoryRevisionPlugin,
            "OpenAIModelPlugin": OpenAIModelPlugin,
            "RuntimePlugin": RuntimePlugin,
        }[name]
    raise AttributeError(name)


__all__ = [
    "DiagramRuntime",
    "JsonlWorkflowEventLog",
    "JsonlWorkflowEventPlugin",
    "MemoryRevisionPlugin",
    "MemoryWorkflowEventLog",
    "OpenAIModelPlugin",
    "RuntimePlugin",
    "RuntimeProfile",
    "WorkflowEvent",
    "WorkflowEventLog",
    "list_profiles",
    "load_profile",
]
