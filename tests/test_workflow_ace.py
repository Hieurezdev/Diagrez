import asyncio
from pathlib import Path
from typing import Any

from core.ace.engine import ACEEngine
from core.ace.store import MarkdownPlaybookStore
from core.adapters.compiler import PlantUMLCompiler
from core.domain.diagram_ir import DiagramRequest
from core.graph.workflow import DiagramWorkflow
from core.requirements.analyst import RequirementsAnalyst
from core.requirements.models import ClarificationRequest


class QueueCompletion:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.system_prompts: list[str] = []
        self.user_prompts: list[str] = []

    async def complete_json(self, *, system: str, user: str) -> dict[str, Any]:
        self.system_prompts.append(system)
        self.user_prompts.append(user)
        if not self._responses:
            raise AssertionError("Unexpected model call")
        return self._responses.pop(0)


def sufficient_analysis() -> dict[str, Any]:
    return {
        "intent_summary": "Model the customer checkout scope.",
        "domain": "e-commerce",
        "requested_view": "Customer checkout use cases",
        "actors": ["Customer"],
        "goals": ["Checkout"],
        "constraints": [],
        "assumptions": [],
        "missing_information": [],
        "sufficient": True,
        "clarification_question": None,
        "normalized_requirements": ["Customer can check out an order."],
    }


def test_workflow_uses_ace_context_and_learns_after_validation(tmp_path: Path) -> None:
    diagram = {
        "type": "use_case",
        "title": "Shop",
        "actors": [{"id": "customer", "name": "Customer"}],
        "use_cases": [{"id": "checkout", "name": "Checkout"}],
        "relationships": [
            {"type": "association", "source": "customer", "target": "checkout"}
        ],
        "assumptions": [],
    }

    async def scenario() -> None:
        model = QueueCompletion(
            [
                sufficient_analysis(),
                {
                    "reasoning_summary": "Used the association semantic check.",
                    "bullet_ids": ["sem-00002"],
                    "final_answer": diagram,
                },
                diagram,
                {
                    "correct_approach": "Keep the valid actor-to-use-case association.",
                    "key_insight": "Associations connect actors and use cases.",
                    "bullet_tags": [{"id": "sem-00002", "tag": "helpful"}],
                },
                {"operations": []},
            ]
        )
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        workflow = DiagramWorkflow(
            model,
            PlantUMLCompiler(),
            ACEEngine(model, store),
            RequirementsAnalyst(model),
        )

        revision = await workflow.run(
            DiagramRequest(
                prompt="Customer checks out",
                thread_id="test-thread",
                diagram_type="use_case",
            )
        )

        assert revision.ir.type == "use_case"
        assert "Generator in an Adaptive Context Engine" in model.system_prompts[1]
        assert "sem-00002" in model.user_prompts[1]
        bullets = {
            bullet.id: bullet for bullet in (await store.get("use_case")).bullets
        }
        assert bullets["sem-00002"].helpful == 1

    asyncio.run(scenario())


def test_workflow_runs_multiple_reflection_rounds_before_curation(
    tmp_path: Path,
) -> None:
    invalid_diagram = {
        "type": "use_case",
        "title": "Shop",
        "actors": [
            {"id": "customer", "name": "Customer"},
            {"id": "admin", "name": "Admin"},
        ],
        "use_cases": [{"id": "checkout", "name": "Checkout"}],
        "relationships": [
            {"type": "association", "source": "customer", "target": "admin"}
        ],
        "assumptions": [],
    }
    repaired_diagram = {
        **invalid_diagram,
        "relationships": [
            {"type": "association", "source": "customer", "target": "checkout"}
        ],
    }
    learned_rule = "Check both association endpoints against their declared node kinds."

    async def scenario() -> None:
        model = QueueCompletion(
            [
                sufficient_analysis(),
                {
                    "reasoning_summary": "Selected an association rule incorrectly.",
                    "bullet_ids": ["sem-00002"],
                    "final_answer": invalid_diagram,
                },
                invalid_diagram,
                {
                    "correct_approach": "Connect an actor to a use case.",
                    "key_insight": learned_rule,
                    "bullet_tags": [{"id": "sem-00002", "tag": "harmful"}],
                },
                {
                    "reasoning_summary": "Applied the reflection to repair the association.",
                    "bullet_ids": ["sem-00002"],
                    "final_answer": repaired_diagram,
                },
                repaired_diagram,
                {
                    "correct_approach": "Keep the corrected association.",
                    "key_insight": learned_rule,
                    "bullet_tags": [{"id": "sem-00002", "tag": "helpful"}],
                },
                {
                    "operations": [
                        {
                            "type": "ADD",
                            "section": "semantic_checks",
                            "content": learned_rule,
                        }
                    ]
                },
            ]
        )
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        workflow = DiagramWorkflow(
            model,
            PlantUMLCompiler(),
            ACEEngine(model, store),
            RequirementsAnalyst(model),
        )

        revision = await workflow.run(
            DiagramRequest(
                prompt="Customer checks out",
                thread_id="repair-thread",
                diagram_type="use_case",
            )
        )

        assert revision.ir.relationships[0].target == "checkout"
        assert "Connect an actor to a use case." in model.user_prompts[4]
        assert (
            sum(
                "Reflector in an Adaptive Context Engine" in prompt
                for prompt in model.system_prompts
            )
            == 2
        )
        persisted = await store.get("use_case")
        bullets = {bullet.id: bullet for bullet in persisted.bullets}
        assert bullets["sem-00002"].helpful == 1
        assert bullets["sem-00002"].harmful == 1
        assert any(bullet.content == learned_rule for bullet in persisted.bullets)

    asyncio.run(scenario())


def test_sparse_request_interrupts_then_resumes_with_clarification(
    tmp_path: Path,
) -> None:
    diagram = {
        "type": "use_case",
        "title": "E-commerce checkout",
        "actors": [{"id": "customer", "name": "Customer"}],
        "use_cases": [{"id": "checkout", "name": "Checkout"}],
        "relationships": [
            {"type": "association", "source": "customer", "target": "checkout"}
        ],
        "assumptions": [],
    }
    insufficient = {
        "intent_summary": "Create an e-commerce use-case diagram.",
        "domain": "e-commerce",
        "requested_view": "Unspecified e-commerce scope",
        "actors": [],
        "goals": [],
        "constraints": [],
        "assumptions": [],
        "missing_information": ["target actors", "business journeys"],
        "sufficient": False,
        "clarification_question": "Which actors and e-commerce journeys should the diagram cover?",
        "normalized_requirements": [],
    }

    async def scenario() -> None:
        model = QueueCompletion(
            [
                insufficient,
                sufficient_analysis(),
                {
                    "reasoning_summary": "Used the clarified customer checkout scope.",
                    "bullet_ids": ["sem-00002"],
                    "final_answer": diagram,
                },
                diagram,
                {
                    "correct_approach": "Keep the actor-goal association.",
                    "key_insight": "Clarified scope is sufficient.",
                    "bullet_tags": [{"id": "sem-00002", "tag": "helpful"}],
                },
                {"operations": []},
            ]
        )
        store = MarkdownPlaybookStore(tmp_path / "playbooks")
        workflow = DiagramWorkflow(
            model,
            PlantUMLCompiler(),
            ACEEngine(model, store),
            RequirementsAnalyst(model),
        )
        request = DiagramRequest(
            prompt="Vẽ use case cho e-commerce",
            thread_id="clarification-thread",
            diagram_type="use_case",
        )

        interrupted = await workflow.run(request)
        assert isinstance(interrupted, ClarificationRequest)
        assert interrupted.missing_information == ["target actors", "business journeys"]
        assert len(model.system_prompts) == 1

        completed = await workflow.run(
            request.model_copy(
                update={
                    "clarification_answer": (
                        "Actor chính là khách hàng; phạm vi gồm tìm sản phẩm và thanh toán."
                    )
                }
            )
        )
        assert not isinstance(completed, ClarificationRequest)
        assert completed.ir.title == "E-commerce checkout"
        assert "clarification_answer" in model.user_prompts[1]
        assert "Customer checkout use cases" in model.user_prompts[2]

    asyncio.run(scenario())
