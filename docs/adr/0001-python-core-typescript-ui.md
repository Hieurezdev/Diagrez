# ADR 0001: Python core, TypeScript UI

## Status

Accepted.

## Context

UML Harness needs model orchestration, typed diagram semantics, deterministic
validation, compilation, and a visual editing workspace. The team wants the
core in Python and the UI in TypeScript.

## Decision

- Python owns the domain model, LangGraph workflow, OpenAI-compatible model
  adapter, validators, compilers, revisions, and FastAPI transport.
- TypeScript owns the browser experience and consumes a versioned JSON/SSE
  contract.
- `DiagramSession` is the deep module and the application seam. HTTP and UI
  code must not know LangGraph node names or provider payloads.
- `UseCaseIR` is a Pydantic model and the source of truth. PlantUML and SVG are
  derived artifacts.
- `LLM_API_KEY` is read from the environment. Credentials are never stored in
  source files, fixtures, or browser code.

## Consequences

The repository has two build systems, but semantic behavior remains testable
without a browser. The JSON contract must be kept stable and tested from both
languages. A future TypeScript client cannot directly manipulate checkpoint
state; it submits product-level requests and patches.

## Open decision exposed by grilling

The current implementation has `run` but not `patch`, and returns a completed
revision rather than a stream from the application seam. Before adding more
diagram types, make this contract honest: either implement the event stream and
patch path, or deliberately reduce the public interface to synchronous runs.
