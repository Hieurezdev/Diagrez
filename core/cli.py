"""Command line entry point for generating and inspecting UML diagrams."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

from core.adapters.compiler import PlantUMLCompiler
from core.config import configure_logging
from core.domain.diagram_factory import parse_diagram
from core.domain.diagram_ir import DiagramRequest
from core.domain.validator import validate_diagram_ir
from core.requirements.models import ClarificationRequest
from core.runtime import (
    DiagramRuntime,
    JsonlWorkflowEventLog,
    list_profiles,
    load_profile,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uml-harness", description="Generate, validate, and render UML diagrams."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser(
        "generate", help="Generate a diagram from a natural-language prompt"
    )
    generate.add_argument("prompt")
    generate.add_argument(
        "--diagram-type",
        choices=("use_case", "class", "sequence", "activity", "state_machine"),
        default="use_case",
    )
    generate.add_argument("--thread-id", default=None)
    generate.add_argument("--profile", default=None, choices=list_profiles())
    generate.add_argument(
        "--output", type=Path, default=None, help="Write the revision JSON to a file"
    )

    for name in ("validate", "render"):
        command = commands.add_parser(
            name, help=f"{name.title()} a typed IR or revision JSON file"
        )
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, default=None)
        command.add_argument(
            "--diagram-type",
            choices=("use_case", "class", "sequence", "activity", "state_machine"),
            default=None,
        )

    profile = commands.add_parser("profile", help="Inspect runtime profiles")
    profile.add_argument("action", choices=("list", "show"))
    profile.add_argument("name", nargs="?", default="default", choices=list_profiles())

    replay = commands.add_parser(
        "replay", help="Print the durable workflow event log for a thread"
    )
    replay.add_argument("thread_id")
    replay.add_argument("--profile", default=None, choices=list_profiles())

    commands.add_parser("serve", help="Run the FastAPI development server")
    return parser


async def _generate(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    runtime = DiagramRuntime(profile)

    async def progress(step: str) -> None:
        print(f"[workflow] {step}", file=sys.stderr, flush=True)

    request = DiagramRequest(
        prompt=args.prompt,
        thread_id=args.thread_id or str(uuid4()),
        diagram_type=args.diagram_type,
    )
    result = await runtime.session().run(request, progress=progress)
    payload = result.model_dump(mode="json")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(serialized)
    if isinstance(result, ClarificationRequest):
        return 2
    return 0


def _read_ir(path: Path, diagram_type: str | None):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("ir"), dict):
        payload = payload["ir"]
    selected_type = diagram_type or payload.get("type")
    if not isinstance(selected_type, str):
        raise TypeError(
            "Input JSON must include a diagram 'type' or use --diagram-type"
        )
    return parse_diagram(selected_type, payload)


def _inspect(args: argparse.Namespace) -> int:
    ir = _read_ir(args.input, args.diagram_type)
    validation = validate_diagram_ir(ir)
    if args.command == "validate":
        print(validation.model_dump_json(indent=2))
        return 0 if validation.valid else 1
    compiled = PlantUMLCompiler().compile(ir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(compiled.svg, encoding="utf-8")
        print(args.output)
    else:
        print(compiled.svg)
    return 0 if validation.valid else 1


def _profile(args: argparse.Namespace) -> int:
    if args.action == "list":
        print("\n".join(list_profiles()))
        return 0
    print(json.dumps(load_profile(args.name).__dict__, default=str, indent=2))
    return 0


def _replay(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    events = JsonlWorkflowEventLog(profile.workflow_event_dir).list(args.thread_id)
    print(
        json.dumps([event.as_dict() for event in events], ensure_ascii=False, indent=2)
    )
    return 0


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    if args.command == "generate":
        code = asyncio.run(_generate(args))
    elif args.command in {"validate", "render"}:
        code = _inspect(args)
    elif args.command == "profile":
        code = _profile(args)
    elif args.command == "replay":
        code = _replay(args)
    else:
        import uvicorn

        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8000,
            log_level="info",
            log_config=None,
            reload=False,
        )
        code = 0
    raise SystemExit(code)


if __name__ == "__main__":
    main()
