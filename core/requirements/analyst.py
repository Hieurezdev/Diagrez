import json

from core.adapters.model import CompletionPort
from core.requirements.models import IntentAnalysis
from core.requirements.prompts import ANALYST_PROMPT


class RequirementsAnalyst:
    """Analyze sparse diagram requests and refine them with human clarification."""

    def __init__(self, model: CompletionPort) -> None:
        self._model = model

    async def analyze(
        self,
        *,
        prompt: str,
        diagram_type: str,
        previous: IntentAnalysis | None = None,
        clarification_answer: str | None = None,
    ) -> IntentAnalysis:
        raw = await self._model.complete_json(
            system=ANALYST_PROMPT,
            user=json.dumps(
                {
                    "diagram_type": diagram_type,
                    "original_request": prompt,
                    "previous_analysis": previous.model_dump() if previous else None,
                    "clarification_answer": clarification_answer,
                },
                ensure_ascii=False,
            ),
        )
        return IntentAnalysis.model_validate(raw)
