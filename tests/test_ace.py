import asyncio
from pathlib import Path
from typing import Any

from core.ace.engine import ACEEngine
from core.ace.models import ACEGenerationRequest, ACEObservation, Reflection
from core.ace.store import MarkdownPlaybookStore


class QueueCompletion:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str]] = []

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        if not self._responses:
            raise AssertionError("Unexpected model call")
        return self._responses.pop(0)


def test_all_default_markdown_playbooks_parse_and_initialize(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        engine = ACEEngine(QueueCompletion([]), store)
        scopes = ["use_case", "class", "sequence", "activity", "state_machine"]

        for scope in scopes:
            context = await engine.generation_context(scope)
            assert context.bullet_ids
            assert (tmp_path / "playbooks" / f"{scope}.md").exists()

    asyncio.run(scenario())


def test_ace_seeds_uml_playbook_and_persists_learning(tmp_path: Path) -> None:
    async def scenario() -> None:
        model = QueueCompletion(
            [
                {
                    "error_identification": "The actor was placed inside the boundary.",
                    "root_cause_analysis": "Actor and system responsibilities were mixed.",
                    "correct_approach": "Keep external roles outside the system boundary.",
                    "key_insight": "Actors represent external roles.",
                    "bullet_tags": [{"id": "not-00001", "tag": "helpful"}],
                },
                {
                    "operations": [
                        {
                            "type": "ADD",
                            "section": "layout_guidance",
                            "content": "Keep external actors visually separated from the system boundary.",
                        }
                    ]
                },
            ]
        )
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        engine = ACEEngine(model, store)

        context = await engine.generation_context("use_case")
        assert "not-00001" in context.bullet_ids
        assert "actors outside the system boundary" in context.prompt
        assert (tmp_path / "playbooks" / "use_case.md").exists()

        update = await engine.learn(
            ACEObservation(
                scope="use_case",
                request="Draw a shop use-case diagram",
                generated_ir='{"type":"use_case"}',
                diagnostics=["error:invalid_association: Invalid association"],
                valid=False,
                bullet_ids=context.bullet_ids,
            )
        )

        assert len(update.added_bullet_ids) == 1
        learned_bullet_id = update.added_bullet_ids[0]
        persisted = await store.get("use_case")
        assert persisted.bullets[0].helpful == 1
        bullets = {bullet.id: bullet for bullet in persisted.bullets}
        assert bullets[learned_bullet_id].section == "layout_guidance"

    asyncio.run(scenario())


def test_ace_deduplicates_curator_additions(tmp_path: Path) -> None:
    async def scenario() -> None:
        duplicate = "An association connects exactly one actor to one use case."
        model = QueueCompletion(
            [
                {"key_insight": duplicate, "bullet_tags": []},
                {
                    "operations": [
                        {
                            "type": "ADD",
                            "section": "semantic_checks",
                            "content": duplicate,
                        }
                    ]
                },
            ]
        )
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        engine = ACEEngine(model, store)
        context = await engine.generation_context("use_case")
        initial_bullet_count = len((await store.get("use_case")).bullets)

        update = await engine.learn(
            ACEObservation(
                scope="use_case",
                request="Draw a use-case diagram",
                generated_ir='{"type":"use_case"}',
                valid=True,
                bullet_ids=context.bullet_ids,
            )
        )

        assert update.added_bullet_ids == []
        assert len((await store.get("use_case")).bullets) == initial_bullet_count

    asyncio.run(scenario())


def test_generator_returns_only_selected_known_bullet_ids(tmp_path: Path) -> None:
    async def scenario() -> None:
        model = QueueCompletion(
            [
                {
                    "reasoning_summary": "Used the actor placement rule.",
                    "bullet_ids": ["not-00001", "unknown-99999", "not-00001"],
                    "final_answer": {"type": "use_case", "title": "Shop"},
                }
            ]
        )
        engine = ACEEngine(model, MarkdownPlaybookStore(tmp_path / "playbooks"))

        generation = await engine.generate(
            ACEGenerationRequest(
                scope="use_case",
                question="Draw a shop use-case diagram",
                task_contract="Return UseCaseIR JSON",
            )
        )

        assert generation.bullet_ids == ["not-00001"]
        assert generation.payload["type"] == "use_case"
        assert "Return the IDs of every bullet you actually used" in model.calls[0][0]

    asyncio.run(scenario())


def test_reflector_selects_ground_truth_prompt_variant(tmp_path: Path) -> None:
    async def scenario() -> None:
        model = QueueCompletion(
            [
                {"key_insight": "Compare with the reference.", "bullet_tags": []},
                {"operations": []},
                {"key_insight": "Use deterministic diagnostics.", "bullet_tags": []},
                {"operations": []},
            ]
        )
        engine = ACEEngine(model, MarkdownPlaybookStore(tmp_path / "playbooks"))
        context = await engine.generation_context("use_case")
        base = {
            "scope": "use_case",
            "request": "Draw a diagram",
            "generated_ir": '{"type":"use_case"}',
            "valid": True,
            "bullet_ids": context.bullet_ids,
        }

        with_ground_truth = ACEObservation(**base, ground_truth='{"type":"use_case"}')
        without_ground_truth = ACEObservation(**base)
        await engine.reflect(with_ground_truth)
        await engine.curate(
            with_ground_truth, Reflection(key_insight="Reference lesson")
        )
        await engine.reflect(without_ground_truth)
        await engine.curate(
            without_ground_truth, Reflection(key_insight="Diagnostic lesson")
        )

        assert "supplied ground truth" in model.calls[0][0]
        assert "ground truth comparison" in model.calls[1][0]
        assert "No ground truth is available" in model.calls[2][0]
        assert "No ground truth is available" in model.calls[3][0]

    asyncio.run(scenario())


def test_reflector_coerces_list_shaped_prose_fields(tmp_path: Path) -> None:
    async def scenario() -> None:
        model = QueueCompletion(
            [
                {
                    "error_identification": [
                        "Missing return message",
                        "Activation is too short",
                    ],
                    "root_cause_analysis": ["The response path was omitted."],
                    "correct_approach": "Add a meaningful return message.",
                    "key_insight": [
                        "Returns should represent information passed back to the caller."
                    ],
                    "bullet_tags": [],
                }
            ]
        )
        engine = ACEEngine(model, MarkdownPlaybookStore(tmp_path / "playbooks"))
        context = await engine.generation_context("sequence")
        reflection = await engine.reflect(
            ACEObservation(
                scope="sequence",
                request="Draw a checkout sequence",
                generated_ir='{"type":"sequence"}',
                valid=False,
                bullet_ids=context.bullet_ids,
            )
        )
        assert (
            reflection.error_identification
            == "Missing return message\nActivation is too short"
        )
        assert reflection.root_cause_analysis == "The response path was omitted."
        assert (
            reflection.key_insight
            == "Returns should represent information passed back to the caller."
        )

    asyncio.run(scenario())
