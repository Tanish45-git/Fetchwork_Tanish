"""Parse the narrowly allowed ASI:One review-card actions."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from uagents_core.contrib.protocols.chat import MetadataContent, TextContent
from uagents_core.contrib.protocols.chat.cards import extract_card_response


_MENTION_RE = re.compile(r"^@[\w-]+:?\s*")
_ZERO_WIDTH = "\u200b\u200c\u200d\ufeff\u2060"


def _normalise(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", text).translate(str.maketrans("", "", _ZERO_WIDTH))
    return re.sub(r"\s+", " ", cleaned.strip().casefold())


def _without_mention(text: str) -> str:
    return _MENTION_RE.sub("", text, count=1).strip()


def parse_action(msg: Any) -> dict[str, str] | None:
    """Return a supported action from metadata or ASI:One's plain-text fallback."""
    for block in msg.content:
        if isinstance(block, MetadataContent):
            response = extract_card_response(block)
            selection = response.selection if response and response.selection else None
            if not selection:
                raw = block.metadata.get("selection")
                if isinstance(raw, str):
                    try:
                        selection = json.loads(raw)
                    except json.JSONDecodeError:
                        selection = None
            parsed = _safe_selection(selection)
            if parsed:
                return parsed
    for block in msg.content:
        if not isinstance(block, TextContent):
            continue
        candidate = _without_mention(block.text)
        if candidate.startswith("{"):
            try:
                parsed = _safe_selection(json.loads(candidate))
            except json.JSONDecodeError:
                parsed = None
            if parsed:
                return parsed
        action = _plain_text_action(candidate)
        if action:
            return {"action": action}
    return None


def is_json_like_message(msg: Any) -> bool:
    return any(
        isinstance(block, TextContent) and _without_mention(block.text).lstrip().startswith("{")
        for block in msg.content
    )


def _safe_selection(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    action = value.get("action")
    if action not in {"generate_pdf", "revise"}:
        return None
    result = {"action": action}
    draft_id = value.get("draft_id")
    if isinstance(draft_id, str) and draft_id:
        result["draft_id"] = draft_id
    return result


def _plain_text_action(text: str) -> str | None:
    normalized = _normalise(text)
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if normalized in {"generate pdf", "generate_pdf", "create pdf", "download pdf"} or compact in {"generatepdf", "createpdf", "downloadpdf"}:
        return "generate_pdf"
    if normalized in {"revise", "revise in chat", "revise_in_chat"} or compact == "reviseinchat":
        return "revise"
    return None
