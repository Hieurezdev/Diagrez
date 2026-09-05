from typing import Protocol

from core.domain.revision import DiagramRevision


class RevisionStore(Protocol):
    async def save(self, revision: DiagramRevision) -> None: ...
    async def get(self, revision_id: str) -> DiagramRevision: ...


class MemoryRevisionStore:
    def __init__(self) -> None:
        self._items: dict[str, DiagramRevision] = {}

    async def save(self, revision: DiagramRevision) -> None:
        self._items[revision.id] = revision

    async def get(self, revision_id: str) -> DiagramRevision:
        try:
            return self._items[revision_id]
        except KeyError as exc:
            raise KeyError(f"Revision not found: {revision_id}") from exc
