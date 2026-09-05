# UML Harness — Codebase Design

## 1. Design thesis

UML Harness is a **diagram compiler with an agentic front end**:

```text
Natural language
      ↓
DiagramSession
      ↓
Typed Diagram IR
      ↓
Semantic validation → deterministic compiler → SVG
      ↓                         ↓
repair / clarification       visual workspace
```

The product contract is not “generate Mermaid.” The contract is:

> Given a request and an optional previous revision, return a validated,
> editable diagram document plus explainable diagnostics.

The first supported notation is **Use Case Diagram**. `SequenceIR` and
`ActivityIR` are future Python modules, not optional fields in one universal
schema.

## 2. Deep module and seam

The external seam is `DiagramSession`. The web route, CLI, and future editor
all use the same interface. LangGraph, OpenAI, persistence, Mermaid/PlantUML,
and repair loops stay behind this seam.

```python
class DiagramSession(Protocol):
    def run(self, request: DiagramRequest) -> AsyncIterator[DiagramEvent]: ...
    def patch(self, request: PatchRequest) -> AsyncIterator[DiagramEvent]: ...
    async def get_revision(self, revision_id: RevisionId) -> DiagramRevision: ...
```

Interface invariants:

- `run` and `patch` are resumable by `threadId`.
- Every successful output contains a typed IR, source text, SVG, and diagnostics.
- A failed validation never produces an apparently valid final result.
- The caller may render progress, but must not depend on internal graph node names.
- Provider failures, invalid user input, and semantic validation failures are
  distinct error kinds.

This is a deep module because callers do not need to know how requirement
extraction, model retries, validation, compilation, checkpointing, or revision
patching work.

## 3. Repository shape

```text
core/                              # Python package
  ace/
    engine.py                      # ACE facade: context + learning loop
    models.py                      # typed playbook/reflection operations
    store.py                       # Markdown parser and durable scoped playbooks
    playbooks/                     # reviewable default .md playbooks
  requirements/
    analyst.py                     # intent and requirement analysis sub-agent
    models.py                      # analysis and clarification contracts
    prompts.py                     # diagram-specific sufficiency policy
  domain/
    diagram_ir.py                  # Pydantic UseCaseIR and value types
    diagnostics.py                 # stable error and warning types
    revision.py                     # immutable revision and patch types
  application/
    diagram_session.py             # external seam; hides orchestration
    events.py                       # streaming events for HTTP and UI
  graph/
    state.py                        # LangGraph state and reducers
    build_graph.py                  # graph topology only
    nodes/
      extract_requirements.py
      build_ir.py
      validate_ir.py
      repair_ir.py
      compile_diagram.py
      render_diagram.py
      apply_patch.py
  adapters/
    model/
      completion_port.py            # injected model seam
      openai_completion.py          # production adapter
      fake_completion.py            # deterministic test adapter
    compiler/
      diagram_compiler.py           # compiler port
      plantuml_compiler.py          # first deterministic compiler
    persistence/
      revision_store.py
      memory_revision_store.py
      postgres_checkpointer.py
  transport/
    http.py                         # FastAPI + SSE adapter
tests/
  domain/
  application/
  graph/
  adapters/

web/                                # TypeScript UI only
  src/
    app/
    diagram-canvas/
    prompt-composer/
    diagnostics-panel/
    revision-history/
```

The graph nodes are implementation details. They may have internal seams for
tests, but those seams should not leak into `DiagramSession`.

## 4. Domain interface: Diagram IR

The IR is the source of truth. Generated PlantUML, SVG, and UI coordinates are
derived artifacts.

```python
class UseCaseIR(BaseModel):
    type: Literal["use_case"]
    title: str
    actors: list[Actor]
    scopes: list[SystemScope]
    use_cases: list[UseCase]
    relationships: list[UseCaseRelationship]
    assumptions: list[Assumption]
```

The runtime implementation uses Pydantic schemas at the model boundary. The
model is allowed to suggest assumptions, but it cannot bypass schema
validation. The HTTP adapter serializes this domain model into the JSON
contract consumed by TypeScript.
IDs are stable across revisions so a patch can target a node without matching
on display text.

## 5. Ports and adapters

There are two real adapter seams:

### Completion port

```python
class CompletionPort(Protocol):
    async def complete(self, input: CompletionInput[T]) -> T: ...
```

`OpenAICompletionAdapter` is the production Python adapter. It uses structured
JSON schema output for requirement extraction, IR construction, and IR patches.
`FakeCompletionAdapter` returns fixtures and failure modes for tests. Nodes do
not instantiate an OpenAI client and never read environment variables.

The implementation should prefer the current OpenAI Responses API structured
output mechanism through the adapter. If LangChain's `ChatOpenAI` adapter is
used, it remains an implementation choice behind `CompletionPort`.

### Compiler port

```python
class DiagramCompiler(Protocol[TIR]):
    def compile(self, ir: TIR) -> CompiledDiagram: ...
```

The first adapter is `PlantUMLCompiler`; a Mermaid adapter can be added without
changing the graph or UI. Compilation is deterministic and has no model call.

Persistence is also injected, but only once there are both memory and durable
implementations. LangGraph's checkpointer owns execution state; the revision
store owns user-visible artifacts.

## 6. LangGraph topology

```text
START
  ↓
analyze_intent (Requirements Analyst)
  ├── sufficient ────────────────────────────────┐
  └── sparse → clarify_requirements (interrupt)  │
                    ↓ human answer               │
              refine_requirements                │
                    └─────────────────────────────┤
                                                  ↓
build_ir (ACE Generator selects playbook bullet IDs)
  ↓
review_ir
  ↓
validate_ir
  ↓
ace_reflect (ground-truth or diagnostics variant)
  ├── invalid and rounds left ────→ repair_ir/Generator ──→ review_ir
  └── valid or rounds exhausted ──→ ace_curate
                                        ├── invalid → END (failure)
                                        └── valid
                  ↓
          compile_diagram
                  ↓
                 END
```

The model-backed `build_ir` and `repair_ir` nodes call ACE's Generator, which
returns the diagram payload and only the playbook bullet IDs it actually used.
LangGraph coordinates the bounded Generator–Reflector rounds and calls Curator
once when they finish. Prompt variants, bullet scoring, deduplication, and JSON
persistence remain internal to the ACE module.

`patch` follows a separate path:

```text
START → load_revision → apply_patch → validate_ir → compile → render → END
```

Keep the topology small. A graph node should do one domain operation and return
state updates, not write directly to the HTTP response or database.

State is intentionally not the public domain object:

```python
class DiagramGraphState(TypedDict):
    request: DiagramRequest
    requirements: NotRequired[ExtractedRequirements]
    ir: NotRequired[UseCaseIR]
    diagnostics: list[Diagnostic]
    compiled: NotRequired[CompiledDiagram]
    revision: NotRequired[DiagramRevision]
    reflection_round: int
    ace_generation: ACEGeneration
    ace_reflection: Reflection
    intent_analysis: IntentAnalysis
    clarification_round: int
```

Use a LangGraph checkpointer with `configurable.thread_id` for resumable runs.
Production persistence should be Postgres; `MemorySaver` is suitable only for
local development and tests.

## 7. Streaming events

The UI gets stable events, not LangGraph internals:

```python
class DiagramEvent(BaseModel):
    type: Literal[
        "started", "progress", "clarification_required", "diagnostics",
        "preview", "completed", "failed"
    ]
    payload: dict[str, object]
```

The FastAPI transport adapter exposes these events over SSE. WebSocket is not
needed for the MVP because the server-to-browser flow is primarily streaming
output, while user actions are discrete requests. TypeScript defines a
matching discriminated union generated or checked against the OpenAPI schema.

## 8. Validation strategy

Validation is layered and deterministic:

1. **Schema** — required fields, enum values, unique IDs.
2. **Graph** — all relationship references exist, no self-association,
   reachable nodes, sensible relationship direction.
3. **Notation** — `include` and `extend` obey Use Case rules.
4. **Presentation** — compiler output exists and contains no broken references.

Visual checks should initially be rule-based: clipped labels, overlapping
bounding boxes, excessive canvas dimensions, and unreadable font size. A visual
critic model can be added later as an advisory diagnostic; it must return
layout corrections, never rewrite the complete IR.

## 9. TypeScript UI/UX design

### Product choice

The UI is a **diagram workbench**, not a chat screen. Its single job is to help
the user reach a trustworthy, editable diagram quickly.

### Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ UML HARNESS     revision · saved              Export  Share  │
├───────────────┬───────────────────────────────┬─────────────┤
│ Prompt        │                               │ Inspector   │
│ composer      │       SVG diagram canvas      │ diagnostics │
│               │                               │ assumptions │
│ Revision list │                               │ IR details  │
└───────────────┴───────────────────────────────┴─────────────┘
```

Visual direction: **technical drafting table** — warm paper background, ink
black text, blueprint blue for active graph edges, and a single signal orange
for validation failures. Use a condensed grotesk for labels and a readable
system sans for body copy. Avoid a generic dark “AI dashboard” aesthetic.

Important states:

- Empty: show three concrete prompts, not a blank chat.
- Generating: canvas keeps the last valid revision while progress appears in
  the prompt composer.
- Clarification: ask one focused question at a time and preserve the draft.
- Invalid: highlight the affected edge/node and show the repair action.
- Completed: expose “Edit request”, “Edit structure”, and “Export” as separate
  actions.
- Mobile: stack prompt → canvas → diagnostics; do not shrink the canvas into
  an unreadable thumbnail.

Accessibility requirements: keyboard-visible focus, semantic buttons, live
region for progress, sufficient color contrast, and reduced-motion support.

## 10. HTTP interface

The HTTP adapter remains thin:

```text
POST /v1/diagram-runs       → SSE<DiagramEvent>
POST /v1/diagram-patches    → SSE<DiagramEvent>
GET  /v1/revisions/:id      → DiagramRevision
```

The browser sends `threadId`, not a LangGraph checkpoint ID. The server maps
the product-level session to LangGraph configuration.

## 11. Testing through the interface

Tests cross the deepest useful seam: `DiagramSession`.

- Fake completion adapter: valid extraction, malformed output, refusal,
  timeout, and repair exhaustion.
- In-memory checkpointer and revision store.
- Golden IR fixtures for valid and invalid Use Case relationships.
- Compiler snapshots for deterministic PlantUML output.
- SSE contract tests for event ordering and terminal events.
- UI tests assert user-visible behavior through stable test IDs.

Avoid tests that assert LangGraph node names, prompt wording, or OpenAI request
internals. Those are implementation details and should remain replaceable.

## 12. Delivery sequence

1. Python `UseCaseIR`, Pydantic schema, diagnostics, and deterministic
   validator.
2. PlantUML compiler with golden fixtures.
3. Python `CompletionPort` plus fake adapter and OpenAI adapter.
4. LangGraph run and patch graphs with memory checkpointing.
5. `DiagramSession` and SSE transport.
6. TypeScript workbench with empty, generating, invalid, and completed states.
7. Postgres checkpointer/revision store and observability.
8. Sequence/Activity modules and optional visual critic.

The deletion test passes for `DiagramSession`: without it, orchestration,
provider calls, repair policy, persistence, and event translation would spread
across every route and UI caller. That is the right place for depth and
locality.

## 13. Decisions and non-goals

- No universal diagram IR in v1.
- No direct model-generated Mermaid/PlantUML in the public contract.
- No UI dependence on graph node names.
- No visual critic before deterministic diagnostics are useful.
- No legacy text-completion API assumption; model access is isolated behind an
  adapter so the provider mechanism can evolve without changing the domain.
