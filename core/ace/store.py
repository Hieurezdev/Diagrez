import asyncio
import re
from pathlib import Path
from typing import Protocol

from core.ace.models import Playbook, PlaybookBullet, PlaybookSection


SECTION_TITLES: dict[PlaybookSection, str] = {
    "notation_rules": "NOTATION RULES",
    "semantic_checks": "SEMANTIC CHECKS",
    "layout_guidance": "LAYOUT GUIDANCE",
    "common_mistakes": "COMMON MISTAKES TO AVOID",
    "prompt_clues": "PROMPT CLUES & INDICATORS",
}

TITLE_SECTIONS = {title: section for section, title in SECTION_TITLES.items()}
BULLET_PATTERN = re.compile(
    r"^- \[([a-z]{3}-\d{5})\] helpful=(\d+) harmful=(\d+) :: (.+)$"
)


class PlaybookStore(Protocol):
    async def get(self, scope: str) -> Playbook: ...

    async def save(self, playbook: Playbook) -> None: ...


class MarkdownPlaybookStore:
    """Persist one human-readable ACE Markdown playbook per diagram scope."""

    def __init__(self, directory: Path, templates: Path | None = None) -> None:
        self._directory = directory
        self._templates = templates or Path(__file__).with_name("playbooks")
        self._lock = asyncio.Lock()

    async def get(self, scope: str) -> Playbook:
        async with self._lock:
            runtime_path = self._path(self._directory, scope)
            if runtime_path.exists():
                return self._parse(scope, runtime_path)
            template_path = self._path(self._templates, scope)
            if template_path.exists():
                return self._parse(scope, template_path)
            return Playbook(scope=scope)

    async def save(self, playbook: Playbook) -> None:
        async with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            path = self._path(self._directory, playbook.scope)
            temporary_path = path.with_suffix(".md.tmp")
            temporary_path.write_text(self._format(playbook), encoding="utf-8")
            temporary_path.replace(path)

    @staticmethod
    def _path(directory: Path, scope: str) -> Path:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", scope):
            raise ValueError(f"Invalid ACE playbook scope: {scope}")
        return directory / f"{scope}.md"

    @staticmethod
    def _parse(scope: str, path: Path) -> Playbook:
        bullets: list[PlaybookBullet] = []
        current_section: PlaybookSection | None = None
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            line = raw_line.strip()
            if line.startswith("## "):
                title = line[3:].strip()
                current_section = TITLE_SECTIONS.get(title)
                if current_section is None:
                    raise RuntimeError(
                        f"Unknown ACE playbook section '{title}' at {path}:{line_number}"
                    )
                continue
            if not line.startswith("- ["):
                continue
            match = BULLET_PATTERN.fullmatch(line)
            if match is None or current_section is None:
                raise RuntimeError(
                    f"Invalid ACE playbook bullet at {path}:{line_number}"
                )
            bullet_id, helpful, harmful, content = match.groups()
            bullets.append(
                PlaybookBullet(
                    id=bullet_id,
                    section=current_section,
                    content=content,
                    helpful=int(helpful),
                    harmful=int(harmful),
                )
            )
        next_id = (
            max(
                (int(bullet.id.rsplit("-", 1)[1]) for bullet in bullets),
                default=0,
            )
            + 1
        )
        return Playbook(scope=scope, next_id=next_id, bullets=bullets)

    @staticmethod
    def _format(playbook: Playbook) -> str:
        lines = [f"# ACE Playbook: {playbook.scope.replace('_', ' ').title()}"]
        for section, title in SECTION_TITLES.items():
            lines.extend(["", f"## {title}", ""])
            lines.extend(
                (
                    f"- [{bullet.id}] helpful={bullet.helpful} harmful={bullet.harmful} :: "
                    f"{' '.join(bullet.content.split())}"
                )
                for bullet in playbook.bullets
                if bullet.section == section
            )
        return "\n".join(lines).rstrip() + "\n"
