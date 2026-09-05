import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.application.session import DiagramSession
from core.domain.diagram_ir import DiagramRequest
from core.requirements.models import ClarificationRequest
from core.runtime import DiagramRuntime, load_profile

app = FastAPI(title="UML Harness Core", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_session: DiagramSession | None = None
WORKFLOW_LABELS = {
    "analyze_intent": "Analyzing requirements",
    "clarify_requirements": "Waiting for clarification",
    "build_ir": "Building UML structure",
    "review_ir": "Reviewing UML notation",
    "validate_ir": "Validating semantics",
    "ace_reflect": "Reflecting on diagnostics",
    "repair_ir": "Repairing the diagram",
    "ace_curate": "Updating the playbook",
    "compile": "Rendering diagram",
}


def session() -> DiagramSession:
    global _session
    if _session is None:
        _session = DiagramRuntime(load_profile()).session()
    return _session


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/diagram-runs")
async def create_run(request: DiagramRequest) -> StreamingResponse:
    async def events():
        yield f"data: {json.dumps({'type': 'started'})}\n\n"
        progress_events: asyncio.Queue[dict[str, str]] = asyncio.Queue()

        async def progress(step: str) -> None:
            await progress_events.put(
                {
                    "type": "workflow_step",
                    "step": step,
                    "label": WORKFLOW_LABELS.get(step, step),
                }
            )

        run = asyncio.create_task(session().run(request, progress=progress))
        try:
            while not run.done():
                try:
                    event = await asyncio.wait_for(progress_events.get(), timeout=0.25)
                except TimeoutError:
                    continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            while not progress_events.empty():
                yield f"data: {json.dumps(progress_events.get_nowait(), ensure_ascii=False)}\n\n"
            result = await run
            if isinstance(result, ClarificationRequest):
                event = {
                    "type": "clarification_required",
                    **result.model_dump(mode="json"),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                return
            yield f"data: {json.dumps({'type': 'completed', 'revision': result.model_dump(mode='json')})}\n\n"
        except (RuntimeError, ValueError) as exc:
            if not run.done():
                run.cancel()
            yield f"data: {json.dumps({'type': 'failed', 'error': str(exc)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/v1/revisions/{revision_id}")
async def get_revision(revision_id: str):
    try:
        return await session().get_revision(revision_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/v1/workflow-runs/{thread_id}/events")
async def get_workflow_events(thread_id: str):
    """Return safe workflow lifecycle events without prompts or credentials."""
    return {
        "thread_id": thread_id,
        "events": [event.as_dict() for event in session().list_events(thread_id)],
    }
