import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from core.ace.engine import ACEEngine
from core.ace.models import (
    ACEGeneration,
    ACEGenerationRequest,
    ACEObservation,
    ACEUpdate,
    Reflection,
)
from core.adapters.compiler import PlantUMLCompiler
from core.adapters.model import CompletionPort
from core.domain.diagram_factory import build_prompt, parse_diagram
from core.domain.diagram_ir import DiagramRequest, UseCaseIR
from core.domain.normalizer import normalize_use_case_payload
from core.domain.other_ir import DiagramIR
from core.domain.revision import DiagramRevision
from core.domain.validator import validate_diagram_ir
from core.requirements.analyst import RequirementsAnalyst
from core.requirements.models import ClarificationRequest, IntentAnalysis
from core.runtime.events import (
    MemoryWorkflowEventLog,
    WorkflowEventLog,
    WorkflowEventRecorder,
)

logger = logging.getLogger(__name__)
ProgressSink = Callable[[str], Awaitable[None]]
_progress_sink: ContextVar[ProgressSink | None] = ContextVar(
    "workflow_progress_sink", default=None
)
_event_recorder: ContextVar[WorkflowEventRecorder | None] = ContextVar(
    "workflow_event_recorder", default=None
)


class GraphState(TypedDict, total=False):
    request: DiagramRequest
    ir: UseCaseIR | DiagramIR
    revision: DiagramRevision
    error: str
    reflection_round: int
    diagnostics: list[str]
    ace_generation: ACEGeneration
    ace_reflection: Reflection
    ace_update: ACEUpdate
    intent_analysis: IntentAnalysis
    clarification_answer: str
    clarification_round: int


class DiagramWorkflow:
    def __init__(
        self,
        model: CompletionPort,
        compiler: PlantUMLCompiler,
        ace: ACEEngine,
        analyst: RequirementsAnalyst,
        max_reflection_rounds: int = 2,
        max_clarification_rounds: int = 2,
        events: WorkflowEventLog | None = None,
    ) -> None:
        if max_reflection_rounds < 0:
            raise ValueError("max_reflection_rounds cannot be negative")
        if max_clarification_rounds < 0:
            raise ValueError("max_clarification_rounds cannot be negative")
        self._model = model
        self._ace = ace
        self._analyst = analyst
        self._max_reflection_rounds = max_reflection_rounds
        self._max_clarification_rounds = max_clarification_rounds
        self._events = events or MemoryWorkflowEventLog()
        builder = StateGraph(GraphState)
        builder.add_node("analyze_intent", self._analyze_intent)
        builder.add_node("clarify_requirements", self._clarify_requirements)
        builder.add_node("refine_requirements", self._refine_requirements)
        builder.add_node("build_ir", self._build_ir)
        builder.add_node("review_ir", self._review_ir)
        builder.add_node("validate_ir", self._validate_ir)
        builder.add_node("repair_ir", self._repair_ir)
        builder.add_node("ace_reflect", self._ace_reflect)
        builder.add_node("ace_curate", self._ace_curate)
        builder.add_node("compile", self._compile)
        builder.add_edge(START, "analyze_intent")
        builder.add_conditional_edges(
            "analyze_intent",
            self._after_requirements_analysis,
            {"clarify": "clarify_requirements", "build": "build_ir"},
        )
        builder.add_edge("clarify_requirements", "refine_requirements")
        builder.add_conditional_edges(
            "refine_requirements",
            self._after_requirements_analysis,
            {"clarify": "clarify_requirements", "build": "build_ir"},
        )
        builder.add_edge("build_ir", "review_ir")
        builder.add_edge("review_ir", "validate_ir")
        builder.add_edge("validate_ir", "ace_reflect")
        builder.add_conditional_edges(
            "ace_reflect",
            self._after_reflection,
            {"repair": "repair_ir", "curate": "ace_curate"},
        )
        builder.add_edge("repair_ir", "review_ir")
        builder.add_conditional_edges(
            "ace_curate",
            self._after_curation,
            {"compile": "compile", "fail": END},
        )
        builder.add_edge("compile", END)
        self._compiler = compiler
        self._graph = builder.compile(checkpointer=InMemorySaver())

    async def run(
        self, request: DiagramRequest, progress: ProgressSink | None = None
    ) -> DiagramRevision | ClarificationRequest:
        started_at = time.perf_counter()
        logger.info(
            "workflow.start",
            extra={
                "thread_id": request.thread_id,
                "diagram_type": request.diagram_type,
            },
        )
        progress_token = _progress_sink.set(progress)
        recorder = WorkflowEventRecorder(request.thread_id, self._events)
        recorder.start_turn()
        event_token = _event_recorder.set(recorder)
        graph_input: GraphState | Command
        if request.clarification_answer:
            # Keep the request available even when a process restart or a
            # missing checkpoint causes LangGraph to re-enter from START.
            graph_input = Command(
                resume=request.clarification_answer,
                update={"request": request},
            )
        else:
            graph_input = {
                "request": request,
                "reflection_round": 0,
                "clarification_round": 0,
            }
        try:
            result = await self._graph.ainvoke(
                graph_input,
                {"configurable": {"thread_id": request.thread_id}},
            )
        except Exception:
            recorder.end_turn("error")
            logger.exception(
                "workflow.failed",
                extra={
                    "thread_id": request.thread_id,
                    "diagram_type": request.diagram_type,
                },
            )
            raise
        finally:
            _event_recorder.reset(event_token)
            _progress_sink.reset(progress_token)
        interrupts = result.get("__interrupt__", ())
        if interrupts:
            recorder.end_turn("clarification_required")
            logger.info(
                "workflow.clarification_required",
                extra={
                    "thread_id": request.thread_id,
                    "diagram_type": request.diagram_type,
                    "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
                },
            )
            return ClarificationRequest.model_validate(interrupts[0].value)
        if "revision" not in result:
            recorder.end_turn("failed")
            logger.error(
                "workflow.no_revision",
                extra={
                    "thread_id": request.thread_id,
                    "diagram_type": request.diagram_type,
                },
            )
            raise RuntimeError(result.get("error", "Diagram generation failed"))
        recorder.end_turn("completed")
        logger.info(
            "workflow.completed",
            extra={
                "thread_id": request.thread_id,
                "diagram_type": request.diagram_type,
                "revision_id": result["revision"].id,
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
            },
        )
        return result["revision"]

    async def _analyze_intent(self, state: GraphState) -> dict[str, Any]:
        request = state["request"]
        await self._emit_progress("analyze_intent")
        logger.info(
            "workflow.node.analyze_intent",
            extra={
                "thread_id": request.thread_id,
                "diagram_type": request.diagram_type,
            },
        )
        analysis = await self._analyst.analyze(
            prompt=request.prompt,
            diagram_type=request.diagram_type,
        )
        return {"intent_analysis": analysis}

    async def _clarify_requirements(self, state: GraphState) -> dict[str, Any]:
        analysis = state["intent_analysis"]
        await self._emit_progress("clarify_requirements")
        clarification_round = state.get("clarification_round", 0) + 1
        logger.info(
            "workflow.node.clarify_requirements",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
                "round": clarification_round,
                "missing_count": len(analysis.missing_information),
            },
        )
        answer = interrupt(
            ClarificationRequest(
                thread_id=state["request"].thread_id,
                question=analysis.clarification_question
                or "Please clarify the requested scope.",
                intent_summary=analysis.intent_summary,
                missing_information=analysis.missing_information,
                round=clarification_round,
            ).model_dump()
        )
        return {
            "clarification_answer": str(answer),
            "clarification_round": clarification_round,
        }

    async def _refine_requirements(self, state: GraphState) -> dict[str, Any]:
        request = state["request"]
        await self._emit_progress("analyze_intent")
        logger.info(
            "workflow.node.refine_requirements",
            extra={
                "thread_id": request.thread_id,
                "diagram_type": request.diagram_type,
                "round": state.get("clarification_round", 0),
            },
        )
        analysis = await self._analyst.analyze(
            prompt=request.prompt,
            diagram_type=request.diagram_type,
            previous=state["intent_analysis"],
            clarification_answer=state["clarification_answer"],
        )
        return {"intent_analysis": analysis}

    def _after_requirements_analysis(self, state: GraphState) -> str:
        if state["intent_analysis"].sufficient:
            return "build"
        if state.get("clarification_round", 0) >= self._max_clarification_rounds:
            return "build"
        return "clarify"

    async def _build_ir(self, state: GraphState) -> dict[str, Any]:
        diagram_type = state["request"].diagram_type
        await self._emit_progress("build_ir")
        logger.info(
            "workflow.node.build_ir",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": diagram_type,
            },
        )
        generation = await self._ace.generate(
            ACEGenerationRequest(
                scope=diagram_type,
                question=state["request"].prompt,
                task_contract=build_prompt(diagram_type),
                context=state["intent_analysis"].generation_context(),
            )
        )
        return {
            "ir": parse_diagram(diagram_type, generation.payload),
            "ace_generation": generation,
            "error": "",
        }

    async def _review_ir(self, state: GraphState) -> dict[str, Any]:
        if state["request"].diagram_type not in {"use_case", "state_machine"}:
            return {}
        await self._emit_progress("review_ir")
        logger.info(
            "workflow.node.review_ir",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
                "reflection_round": state.get("reflection_round", 0),
            },
        )
        if state["request"].diagram_type == "state_machine":
            raw = await self._model.complete_json(
                system=(
                    "You are a strict UML state-machine reviewer. Return only corrected state_machine JSON. "
                    "Model one entity lifecycle, not a list of unrelated activities. Preserve declared IDs and human-readable Vietnamese labels. "
                    "Use exactly one initial pseudo-state and at least one final state. Initial has no incoming transition; final states have no outgoing transition. "
                    "Every transition must have a meaningful event, optional [guard], or / action. "
                    "For alternative outcomes, branch from the processing state with mutually exclusive guards such as [success] and [failed]; do not draw an unlabeled bypass. "
                    "Keep entry/do/exit actions inside their state and preserve composite parent_id fields."
                ),
                user=(
                    f"Original request:\n{state['request'].prompt}\n\n"
                    f"Analyzed requirements:\n{state['intent_analysis'].generation_context()}\n\n"
                    f"Draft state machine IR:\n{state['ir'].model_dump_json()}"
                ),
            )
            from core.domain.diagram_factory import normalize_state_machine_payload

            return {
                "ir": parse_diagram(
                    "state_machine", normalize_state_machine_payload(raw)
                ),
                "error": "",
            }
        raw = await self._model.complete_json(
            system=(
                "You are a strict UML use-case reviewer. Return only corrected UseCaseIR JSON. "
                "Keep actors outside the system conceptually and use cases inside it. "
                "Keep only specific actor-to-use-case associations supported by the request; do not create a shared or blanket association. "
                "Use <<include>> only for mandatory reusable behavior: source is the base use case and target is the included use case. "
                "Use <<extend>> only for optional or conditional behavior: source is the extending use case and target is the base use case. "
                "Example: 'Forgot password' extends 'Log in', so source=forgot_password and target=log_in. "
                "Remove speculative include/extend relationships such as Search including Login unless the request explicitly requires them. "
                "Preserve system scopes and each use case scope_id; actors remain outside every scope. "
                "Preserve human-readable Vietnamese display names and stable ids. Every relationship must have string source and target."
            ),
            user=(
                f"Original request:\n{state['request'].prompt}\n\n"
                f"Analyzed requirements:\n{state['intent_analysis'].generation_context()}\n\n"
                f"Draft IR:\n{state['ir'].model_dump_json()}"
            ),
        )
        return {
            "ir": UseCaseIR.model_validate(normalize_use_case_payload(raw)),
            "error": "",
        }

    async def _validate_ir(self, state: GraphState) -> dict[str, Any]:
        await self._emit_progress("validate_ir")
        result = validate_diagram_ir(state["ir"])
        diagnostics = [
            f"{item.severity}:{item.code}: {item.message}"
            for item in result.diagnostics
        ]
        errors = [
            item.message for item in result.diagnostics if item.severity == "error"
        ]
        logger.info(
            "workflow.node.validate_ir",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
                "valid": result.valid,
                "diagnostic_count": len(result.diagnostics),
                "error_count": len(errors),
            },
        )
        return {"error": " | ".join(errors), "diagnostics": diagnostics}

    async def _ace_reflect(self, state: GraphState) -> dict[str, Any]:
        await self._emit_progress("ace_reflect")
        logger.info(
            "workflow.node.ace_reflect",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
                "reflection_round": state.get("reflection_round", 0),
            },
        )
        reflection = await self._ace.reflect(self._observation(state))
        return {"ace_reflection": reflection}

    async def _ace_curate(self, state: GraphState) -> dict[str, Any]:
        await self._emit_progress("ace_curate")
        logger.info(
            "workflow.node.ace_curate",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
                "reflection_round": state.get("reflection_round", 0),
            },
        )
        update = await self._ace.curate(
            self._observation(state),
            state["ace_reflection"],
        )
        return {"ace_update": update}

    async def _repair_ir(self, state: GraphState) -> dict[str, Any]:
        reflection_round = state.get("reflection_round", 0) + 1
        diagram_type = state["request"].diagram_type
        await self._emit_progress("repair_ir")
        logger.info(
            "workflow.node.repair_ir",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": diagram_type,
                "reflection_round": reflection_round,
            },
        )
        generation = await self._ace.generate(
            ACEGenerationRequest(
                scope=diagram_type,
                question=state["request"].prompt,
                task_contract=(
                    f"{build_prompt(diagram_type)} Preserve valid IDs and correct every reported error."
                ),
                context=(
                    f"Analyzed requirements: {state['intent_analysis'].generation_context()}\n"
                    f"Current IR: {state['ir'].model_dump_json()}\n"
                    f"Environment feedback: {state.get('error', '')}"
                ),
                reflection=state["ace_reflection"],
            )
        )
        return {
            "ir": parse_diagram(diagram_type, generation.payload),
            "ace_generation": generation,
            "reflection_round": reflection_round,
            "error": "",
        }

    def _observation(self, state: GraphState) -> ACEObservation:
        generation = state["ace_generation"]
        return ACEObservation(
            scope=state["request"].diagram_type,
            request=(
                f"{state['request'].prompt}\n\n"
                f"{state['intent_analysis'].generation_context()}"
            ),
            generated_ir=state["ir"].model_dump_json(),
            diagnostics=state.get("diagnostics", []),
            valid=not bool(state.get("error")),
            bullet_ids=generation.bullet_ids,
            reasoning_trace=generation.reasoning_summary,
            ground_truth=state["request"].ground_truth,
        )

    def _after_reflection(self, state: GraphState) -> str:
        if not state.get("error"):
            return "curate"
        if state.get("reflection_round", 0) < self._max_reflection_rounds:
            return "repair"
        return "curate"

    @staticmethod
    def _after_curation(state: GraphState) -> str:
        return "compile" if not state.get("error") else "fail"

    async def _compile(self, state: GraphState) -> dict[str, Any]:
        ir = state["ir"]
        await self._emit_progress("compile")
        logger.info(
            "workflow.node.compile",
            extra={
                "thread_id": state["request"].thread_id,
                "diagram_type": state["request"].diagram_type,
            },
        )
        compiled = self._compiler.compile(ir)
        return {
            "revision": DiagramRevision(
                id=str(uuid.uuid4()),
                thread_id=state["request"].thread_id,
                ir=ir,
                compiled=compiled,
            )
        }

    @staticmethod
    async def _emit_progress(step: str) -> None:
        recorder = _event_recorder.get()
        if recorder is not None:
            recorder.start_step(step)
        sink = _progress_sink.get()
        if sink is not None:
            await sink(step)
