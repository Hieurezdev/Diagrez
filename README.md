# UML Harness

Agentic diagram compiler: natural-language requirements → typed Diagram IR →
validated source → rendered SVG.

Supported UML views:

- Use Case (interactive actors, use cases, relationships, and system scopes)
- Class
- Sequence
- Activity
- State Machine

See [the codebase design](docs/codebase-design.md) for the LangGraph,
OpenAI adapter, TypeScript UI/UX, module interfaces, seams, and delivery plan.

## Adaptive Context Engine

The Python core adapts the ACE architecture in `ace/ace` to UML generation:

```text
ACE playbook → Generator {bullet_ids, diagram IR}
                              ↓
                    review → deterministic validation
                              ↓
                         Reflector
                    invalid ↙       ↘ valid/exhausted
             regenerate                 Curator
                  └──── bounded rounds ────┘
                                         ↓
                                  compile / fail
```

Default Markdown playbooks are visible in `core/ace/playbooks/`. At runtime,
each diagram scope is copied to and updated in `.data/ace-playbooks/<scope>.md`.
Set `ACE_PLAYBOOK_DIR` to use another runtime directory.
The original ACE offline training harness and embedding-based bullet merger are
not part of the request path; the core keeps the online Generator–Reflector–
Curator loop behind `ACEEngine`.

`ACE_MAX_REFLECTION_ROUNDS` controls how many reflection-driven regeneration
attempts run after the first draft (default: `2`). An optional `ground_truth`
field on a diagram request selects the ground-truth Reflector and Curator
prompts; normal interactive requests use deterministic diagnostics and the
no-ground-truth variants.

## Requirements clarification

The Requirements Analyst runs before ACE. It extracts intent, diagram scope,
actors or participants, goals, constraints, assumptions, missing information,
and atomic normalized requirements. Sparse requests produce a
clarification_required SSE event. Submit clarification_answer with the same
thread_id to resume the LangGraph checkpoint. MAX_CLARIFICATION_ROUNDS defaults
to 2; after that, the Analyst proceeds with explicit assumptions.

The Use Case editor supports adding, renaming, moving, and removing actors,
use cases, and system scope boundaries. Use cases can be reassigned between
scopes from the Inspector. Removing a node also removes its relationships;
removing a scope reassigns its use cases and the final scope cannot be removed.

## Export and continue editing

After a revision is generated, use the `Export` menu in the workbench:

- `.drawio` — opens in draw.io as an SVG-backed canvas for presentation and annotation.
- `.svg` — vector output for documentation and wiki pages.
- `.png` — raster output for sharing in tickets or chat.
- `.json` — the typed Diagram IR for version control, API use, or later regeneration.

The `.drawio` artifact follows the drawio-ai-kit handoff model: generate in the
workbench, download the artifact, continue editing in draw.io, then share or
commit the source representation.

The workbench also provides zoom, pointer-pan, undo/redo, import, a UML palette,
live validation, render preview, local autosave, and a revision timeline.

## Development commands

Run the backend with the project watcher so changes inside `.venv` do not
restart the server:

```bash
uv run python scripts/dev_backend.py
```

The development watcher monitors `core/`. Restart the backend manually after
changing `main.py` or project configuration.

`make setup` stores the pre-commit environment in the ignored
`.pre-commit-cache/` directory so setup does not require write access to the
user-level pre-commit cache.

Run the frontend separately from `web/`:

```bash
npm run dev
```

The same runtime can also be used without starting the web UI. After `uv sync`,
the `uml-harness` command exposes the workflow and deterministic inspection
tools:

```bash
uv run uml-harness profile list
uv run uml-harness generate "Vẽ state machine cho quy trình mua hàng của khách hàng" \
  --diagram-type state_machine --output .data/order-state.json
uv run uml-harness validate .data/order-state.json
uv run uml-harness render .data/order-state.json --output .data/order-state.svg
uv run uml-harness replay <thread-id>
uv run uml-harness serve
```

`core/runtime` is the composition seam shared by the HTTP server and CLI. A
profile provides workflow settings, while plugins provide the model and
revision store and durable workflow events. The event log records only safe
turn/step/node lifecycle data, never prompts or credentials. This keeps the
Cordis-inspired lifecycle small and explicit;
tests or another host can replace those plugins without changing
`DiagramSession` or the LangGraph workflow.

The same events are available over `GET /v1/workflow-runs/{thread_id}/events`
for the frontend timeline and post-run debugging.

The backend emits structured workflow logs for intent analysis, clarification,
IR generation/review, validation, ACE reflection/curation, repair, and compile.
Logs include safe correlation fields such as `thread_id`, `diagram_type`,
rounds, diagnostic counts, and elapsed time; prompts and credentials are never
logged.
