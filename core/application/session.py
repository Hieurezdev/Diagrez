from collections.abc import Awaitable, Callable

from core.ace.engine import ACEEngine
from core.ace.store import MarkdownPlaybookStore
from core.adapters.compiler import PlantUMLCompiler
from core.adapters.model import CompletionPort
from core.domain.diagram_ir import DiagramRequest
from core.domain.revision import DiagramRevision
from core.domain.revision_store import RevisionStore
from core.graph.workflow import DiagramWorkflow
from core.requirements.analyst import RequirementsAnalyst
from core.requirements.models import ClarificationRequest
from core.runtime.events import MemoryWorkflowEventLog, WorkflowEventLog
from core.runtime.profiles import RuntimeProfile, load_profile


class DiagramSession:
    def __init__(
        self,
        model: CompletionPort,
        revisions: RevisionStore,
        profile: RuntimeProfile | None = None,
        events: WorkflowEventLog | None = None,
    ) -> None:
        self._revisions = revisions
        runtime_profile = profile or load_profile()
        self._events = events or MemoryWorkflowEventLog()
        ace = ACEEngine(model, MarkdownPlaybookStore(runtime_profile.ace_playbook_dir))
        self._workflow = DiagramWorkflow(
            model,
            PlantUMLCompiler(),
            ace,
            RequirementsAnalyst(model),
            max_reflection_rounds=runtime_profile.max_reflection_rounds,
            max_clarification_rounds=runtime_profile.max_clarification_rounds,
            events=self._events,
        )

    async def run(
        self,
        request: DiagramRequest,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> DiagramRevision | ClarificationRequest:
        result = await self._workflow.run(request, progress=progress)
        if isinstance(result, DiagramRevision):
            await self._revisions.save(result)
        return result

    async def get_revision(self, revision_id: str) -> DiagramRevision:
        return await self._revisions.get(revision_id)

    def list_events(self, thread_id: str):
        return self._events.list(thread_id)
