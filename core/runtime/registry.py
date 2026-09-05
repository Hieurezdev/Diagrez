"""Small plugin registry inspired by Cordis service composition."""

from dataclasses import dataclass
from typing import Protocol

from core.adapters.compiler import PlantUMLCompiler
from core.adapters.model import CompletionPort, OpenAICompatibleCompletion
from core.application.session import DiagramSession
from core.domain.revision_store import MemoryRevisionStore, RevisionStore
from core.runtime.events import JsonlWorkflowEventLog, WorkflowEventLog
from core.runtime.profiles import RuntimeProfile


class RuntimePlugin(Protocol):
    """A focused composition unit that installs one or more runtime services."""

    name: str

    def install(self, services: "RuntimeServices") -> None: ...


@dataclass
class RuntimeServices:
    profile: RuntimeProfile
    model: CompletionPort | None = None
    revisions: RevisionStore | None = None
    events: WorkflowEventLog | None = None

    def provide_model(self, model: CompletionPort) -> None:
        if self.model is not None:
            raise RuntimeError("A completion model has already been registered")
        self.model = model

    def provide_revisions(self, revisions: RevisionStore) -> None:
        if self.revisions is not None:
            raise RuntimeError("A revision store has already been registered")
        self.revisions = revisions

    def provide_events(self, events: WorkflowEventLog) -> None:
        if self.events is not None:
            raise RuntimeError("A workflow event log has already been registered")
        self.events = events


class OpenAIModelPlugin:
    name = "openai-compatible-model"

    def install(self, services: RuntimeServices) -> None:
        services.provide_model(OpenAICompatibleCompletion())


class MemoryRevisionPlugin:
    name = "memory-revisions"

    def install(self, services: RuntimeServices) -> None:
        services.provide_revisions(MemoryRevisionStore())


class JsonlWorkflowEventPlugin:
    name = "jsonl-workflow-events"

    def install(self, services: RuntimeServices) -> None:
        services.provide_events(
            JsonlWorkflowEventLog(services.profile.workflow_event_dir)
        )


class DiagramRuntime:
    """Compose application services once, then create independent sessions."""

    def __init__(
        self, profile: RuntimeProfile, plugins: tuple[RuntimePlugin, ...] | None = None
    ) -> None:
        self.services = RuntimeServices(profile=profile)
        for plugin in plugins or (
            OpenAIModelPlugin(),
            MemoryRevisionPlugin(),
            JsonlWorkflowEventPlugin(),
        ):
            plugin.install(self.services)
        if (
            self.services.model is None
            or self.services.revisions is None
            or self.services.events is None
        ):
            raise RuntimeError(
                "Runtime must provide a model, revision store, and workflow event log"
            )

    def session(self) -> DiagramSession:
        return DiagramSession(
            self.services.model,
            self.services.revisions,
            profile=self.services.profile,
            events=self.services.events,
        )

    def compiler(self) -> PlantUMLCompiler:
        return PlantUMLCompiler()
