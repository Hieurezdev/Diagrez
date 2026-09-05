import re
import unicodedata
from typing import Any


def _stable_id(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_") or "node"


def _display_name(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _reference(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        candidate = value.get("id") or value.get("name") or value.get("display_name")
        return (
            candidate.strip()
            if isinstance(candidate, str) and candidate.strip()
            else None
        )
    return None


def normalize_use_case_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common model aliases before strict Pydantic validation."""
    normalized = dict(payload)
    normalized["type"] = "use_case"
    if "use_cases" not in normalized and "useCases" in normalized:
        normalized["use_cases"] = normalized.pop("useCases")

    node_names: dict[str, str] = {}
    actors = []
    for actor in normalized.get("actors", []):
        item = (
            {"id": _stable_id(actor), "name": actor}
            if isinstance(actor, str)
            else dict(actor)
        )
        item.setdefault("id", _stable_id(str(item.get("name", "actor"))))
        item.setdefault("name", item["id"].replace("_", " ").title())
        if item.get("display_name") is None and item.get("name") == item.get("id"):
            item["display_name"] = _display_name(str(item["name"]))
        actors.append(item)
        node_names[str(item["name"]).casefold()] = str(item["id"])
    normalized["actors"] = actors

    scopes = []
    for scope in normalized.get("scopes", []):
        item = (
            {"id": _stable_id(scope), "name": scope}
            if isinstance(scope, str)
            else dict(scope)
        )
        item.setdefault("id", _stable_id(str(item.get("name", "system"))))
        item.setdefault("name", item["id"].replace("_", " ").title())
        scopes.append(item)
    if not scopes:
        scopes = [{"id": "system", "name": str(normalized.get("title", "System"))}]
    normalized["scopes"] = scopes
    default_scope_id = str(scopes[0]["id"])

    use_cases = []
    for use_case in normalized.get("use_cases", []):
        item = (
            {"id": _stable_id(use_case), "name": use_case}
            if isinstance(use_case, str)
            else dict(use_case)
        )
        item.setdefault("id", _stable_id(str(item.get("name", "use_case"))))
        item.setdefault("name", item["id"].replace("_", " ").title())
        item.setdefault("scope_id", default_scope_id)
        if item.get("display_name") is None and item.get("name") == item.get("id"):
            item["display_name"] = _display_name(str(item["name"]))
        use_cases.append(item)
        node_names[str(item["name"]).casefold()] = str(item["id"])
    normalized["use_cases"] = use_cases

    relationships = []
    for relationship in normalized.get("relationships", []):
        if isinstance(relationship, str):
            continue
        item = dict(relationship)
        aliases = {
            "associates": "association",
            "associations": "association",
            "extends": "extend",
            "includes": "include",
        }
        relationship_type = item.get("type")
        if isinstance(relationship_type, str):
            item["type"] = aliases.get(relationship_type.lower(), relationship_type)
        raw_source = (
            item.get("source")
            or item.get("from")
            or item.get("source_id")
            or item.get("sourceId")
            or item.get("actor")
        )
        raw_target = (
            item.get("target")
            or item.get("to")
            or item.get("target_id")
            or item.get("targetId")
            or item.get("use_case")
            or item.get("useCase")
        )
        source = _reference(raw_source)
        target = _reference(raw_target)
        if source is None or target is None:
            continue
        item["source"] = node_names.get(source.casefold(), source)
        item["target"] = node_names.get(target.casefold(), target)
        relationships.append(item)
    normalized["relationships"] = relationships

    assumptions = []
    for assumption in normalized.get("assumptions", []):
        if isinstance(assumption, str):
            assumptions.append({"text": assumption, "confidence": "medium"})
        else:
            assumptions.append(assumption)
    normalized["assumptions"] = assumptions
    return normalized
