# UML Harness glossary

| Term | Meaning |
|---|---|
| Diagram IR | Typed, editable semantic representation of one diagram. It is the source of truth. |
| DiagramSession | Deep application module hiding orchestration, model calls, validation, compilation, and persistence. |
| CompletionPort | Python interface for structured model completion; production and fake adapters satisfy it. |
| Adapter | Concrete implementation at a seam, such as the Qwen OpenAI-compatible client or in-memory revision store. |
| Checkpoint | LangGraph execution snapshot used to resume a thread. |
| Revision | User-visible immutable artifact containing IR, generated source, SVG, and diagnostics. |
| Diagnostic | Stable, explainable validation result attached to a node or relationship where possible. |
| Patch | A targeted change to an existing IR using stable IDs, rather than regeneration from an image. |
| Thread ID | Product-level session identifier mapped to LangGraph `configurable.thread_id`. |
| Compiler | Deterministic transformation from IR to diagram source and renderable output. |
