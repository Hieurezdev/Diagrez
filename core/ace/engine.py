import asyncio
import json

from core.ace.models import (
    ACEContext,
    ACEGeneration,
    ACEGenerationRequest,
    ACEObservation,
    ACEUpdate,
    CuratorResponse,
    GeneratorResponse,
    Playbook,
    PlaybookBullet,
    Reflection,
)
from core.ace.prompts import (
    CURATOR_PROMPT,
    CURATOR_PROMPT_NO_GT,
    GENERATOR_PROMPT,
    REFLECTOR_PROMPT,
    REFLECTOR_PROMPT_NO_GT,
)
from core.ace.store import PlaybookStore
from core.adapters.model import CompletionPort

SECTION_TITLES = {
    "notation_rules": "NOTATION RULES",
    "semantic_checks": "SEMANTIC CHECKS",
    "layout_guidance": "LAYOUT GUIDANCE",
    "common_mistakes": "COMMON MISTAKES TO AVOID",
    "prompt_clues": "PROMPT CLUES & INDICATORS",
}

SECTION_PREFIXES = {
    "notation_rules": "not",
    "semantic_checks": "sem",
    "layout_guidance": "lay",
    "common_mistakes": "mis",
    "prompt_clues": "clu",
}

MAX_BULLETS = 40


class ACEEngine:
    """Adaptive Context Engine facade used by the diagram workflow."""

    def __init__(self, model: CompletionPort, store: PlaybookStore) -> None:
        self._model = model
        self._store = store
        self._scope_locks: dict[str, asyncio.Lock] = {}

    async def generation_context(self, scope: str) -> ACEContext:
        playbook = await self._store.get(scope)
        await self._store.save(playbook)
        return ACEContext(
            scope=scope,
            prompt=self._format_playbook(playbook),
            bullet_ids=[bullet.id for bullet in playbook.bullets],
        )

    async def generate(self, request: ACEGenerationRequest) -> ACEGeneration:
        context = await self.generation_context(request.scope)
        raw = await self._model.complete_json(
            system=GENERATOR_PROMPT,
            user=json.dumps(
                {
                    "task_contract": request.task_contract,
                    "question": request.question,
                    "context": request.context,
                    "playbook": context.prompt,
                    "reflection": (
                        request.reflection.model_dump()
                        if request.reflection is not None
                        else "(empty)"
                    ),
                },
                ensure_ascii=False,
            ),
        )
        response = GeneratorResponse.model_validate(raw)
        known_ids = set(context.bullet_ids)
        selected_ids = list(
            dict.fromkeys(
                bullet_id for bullet_id in response.bullet_ids if bullet_id in known_ids
            )
        )
        return ACEGeneration(
            reasoning_summary=response.reasoning_summary,
            bullet_ids=selected_ids,
            payload=response.final_answer,
        )

    async def learn(self, observation: ACEObservation) -> ACEUpdate:
        reflection = await self.reflect(observation)
        return await self.curate(observation, reflection)

    async def reflect(self, observation: ACEObservation) -> Reflection:
        lock = self._scope_locks.setdefault(observation.scope, asyncio.Lock())
        async with lock:
            playbook = await self._store.get(observation.scope)
            reflection = await self._reflect_with_playbook(observation, playbook)
            self._apply_tags(playbook, reflection)
            await self._store.save(playbook)
            return reflection

    async def curate(
        self,
        observation: ACEObservation,
        reflection: Reflection,
    ) -> ACEUpdate:
        lock = self._scope_locks.setdefault(observation.scope, asyncio.Lock())
        async with lock:
            playbook = await self._store.get(observation.scope)
            curator_response = await self._curate_with_playbook(
                observation, reflection, playbook
            )
            added_ids = self._apply_operations(playbook, curator_response)
            await self._store.save(playbook)
            return ACEUpdate(reflection=reflection, added_bullet_ids=added_ids)

    async def _reflect_with_playbook(
        self,
        observation: ACEObservation,
        playbook: Playbook,
    ) -> Reflection:
        raw = await self._model.complete_json(
            system=REFLECTOR_PROMPT
            if observation.ground_truth
            else REFLECTOR_PROMPT_NO_GT,
            user=json.dumps(
                {
                    "question": observation.request,
                    "reasoning_trace": observation.reasoning_trace,
                    "generated_ir": observation.generated_ir,
                    "ground_truth": observation.ground_truth,
                    "valid": observation.valid,
                    "environment_feedback": observation.diagnostics,
                    "playbook_bullets": [
                        bullet.model_dump()
                        for bullet in playbook.bullets
                        if bullet.id in observation.bullet_ids
                    ],
                },
                ensure_ascii=False,
            ),
        )
        reflection = Reflection.model_validate(raw)
        known_ids = {bullet.id for bullet in playbook.bullets}
        reflection.bullet_tags = [
            tag for tag in reflection.bullet_tags if tag.id in known_ids
        ]
        return reflection

    async def _curate_with_playbook(
        self,
        observation: ACEObservation,
        reflection: Reflection,
        playbook: Playbook,
    ) -> CuratorResponse:
        raw = await self._model.complete_json(
            system=CURATOR_PROMPT if observation.ground_truth else CURATOR_PROMPT_NO_GT,
            user=json.dumps(
                {
                    "scope": observation.scope,
                    "question_context": observation.request,
                    "ground_truth": observation.ground_truth,
                    "valid": observation.valid,
                    "environment_feedback": observation.diagnostics,
                    "recent_reflection": reflection.model_dump(),
                    "current_playbook": [
                        bullet.model_dump() for bullet in playbook.bullets
                    ],
                    "playbook_stats": {
                        "bullet_count": len(playbook.bullets),
                        "max_bullets": MAX_BULLETS,
                    },
                },
                ensure_ascii=False,
            ),
        )
        return CuratorResponse.model_validate(raw)

    @staticmethod
    def _format_playbook(playbook: Playbook) -> str:
        lines = [
            "Apply relevant rules from this ACE playbook. The playbook is guidance, not output data.",
        ]
        for section, title in SECTION_TITLES.items():
            section_bullets = [
                bullet for bullet in playbook.bullets if bullet.section == section
            ]
            if not section_bullets:
                continue
            lines.append(f"\n## {title}")
            for bullet in section_bullets:
                lines.append(
                    f"[{bullet.id}] helpful={bullet.helpful} harmful={bullet.harmful} :: {bullet.content}"
                )
        return "\n".join(lines)

    @staticmethod
    def _apply_tags(playbook: Playbook, reflection: Reflection) -> None:
        tags = {tag.id: tag.tag for tag in reflection.bullet_tags}
        for bullet in playbook.bullets:
            tag = tags.get(bullet.id)
            if tag == "helpful":
                bullet.helpful += 1
            elif tag == "harmful":
                bullet.harmful += 1

    @staticmethod
    def _apply_operations(playbook: Playbook, response: CuratorResponse) -> list[str]:
        existing = {ACEEngine._canonical(bullet.content) for bullet in playbook.bullets}
        added_ids: list[str] = []
        for operation in response.operations:
            if len(playbook.bullets) >= MAX_BULLETS:
                break
            canonical_content = ACEEngine._canonical(operation.content)
            if canonical_content in existing:
                continue
            bullet_id = f"{SECTION_PREFIXES[operation.section]}-{playbook.next_id:05d}"
            playbook.next_id += 1
            playbook.bullets.append(
                PlaybookBullet(
                    id=bullet_id,
                    section=operation.section,
                    content=" ".join(operation.content.split()),
                )
            )
            existing.add(canonical_content)
            added_ids.append(bullet_id)
        return added_ids

    @staticmethod
    def _canonical(content: str) -> str:
        return " ".join(content.casefold().split()).rstrip(".")
