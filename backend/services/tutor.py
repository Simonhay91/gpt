"""Tutor learning-memory service.

Holds the logic that turns a finished Tutor conversation into a compact,
teacher-style "progress note" stored per book in ``users.tutor_memory``.

Memory shape (in the ``users`` collection)::

    tutor_memory: {
        "<book_source_id>": {
            "summary": "Прошёл гл. 1-3. Понял A, B. Затруднился с C. Следующее: D",
            "progressPercent": 60,
            "lastSession": "2026-06-19",
            "updatedAt": "ISO datetime"
        }
    }

Each book's summary is capped to keep the eventual system-prompt injection small
(Risk 1.2). When the cumulative note would grow past the cap, the model is asked
to re-summarise old + new together (compaction), so the note stays bounded.
"""
import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import anthropic

logger = logging.getLogger(__name__)

# Keep each per-book note small so injecting it never crowds the RAG budget.
TUTOR_SUMMARY_CHAR_CAP = 500

_SUMMARY_SYSTEM = (
    "Ты — наставник. Прочитай предыдущие заметки о прогрессе ученика и новый диалог урока, "
    "и напиши ОДНУ обновлённую кумулятивную заметку В СТИЛЕ УЧИТЕЛЯ: какую тему/главу разобрали, "
    "что ученик понял хорошо, с чем затруднился, что изучать следующим. Максимум 80 слов. "
    "Также оцени общий прогресс по книге в процентах (0-100). "
    "Верни СТРОГО JSON: {\"summary\": \"...\", \"progressPercent\": N}. "
    "Пиши на языке диалога. Без markdown, без преамбулы."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_summary_json(text: str) -> Tuple[Optional[str], Optional[int]]:
    """Best-effort extraction of {summary, progressPercent} from a model reply."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        text = match.group(0) if match else ""
    if not text:
        return None, None
    try:
        data = json.loads(text)
        summary = (data.get("summary") or "").strip()
        progress = data.get("progressPercent")
        if isinstance(progress, str):
            progress = int(re.sub(r"[^0-9]", "", progress) or 0)
        if isinstance(progress, (int, float)):
            progress = max(0, min(100, int(progress)))
        else:
            progress = None
        return (summary or None), progress
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, None


async def _summarize_one(
    claude_client,
    old_summary: str,
    dialog_text: str,
) -> Tuple[Optional[str], Optional[int]]:
    """Produce a cumulative teacher-style note + progress for a single book."""
    user_content = (
        f"Предыдущие заметки о прогрессе:\n{old_summary or '(пока пусто)'}\n\n"
        f"Новый диалог урока:\n{dialog_text[:8000]}"
    )
    try:
        resp = await claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=_SUMMARY_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        summary, progress = _parse_summary_json(resp.content[0].text)
        if summary and len(summary) > TUTOR_SUMMARY_CHAR_CAP:
            summary = summary[:TUTOR_SUMMARY_CHAR_CAP].rsplit(" ", 1)[0] + "…"
        return summary, progress
    except Exception as exc:  # noqa: BLE001 - summarization is best-effort
        logger.error(f"Tutor summarize error: {exc}")
        return None, None


async def _active_library_book_ids(db, chat: dict) -> List[str]:
    """Library source ids that are active in this chat (the books being studied)."""
    active = chat.get("activeSourceIds") or []
    if not active:
        return []
    rows = await db.sources.find(
        {"id": {"$in": active}, "level": "library"},
        {"_id": 0, "id": 1},
    ).to_list(len(active))
    return [r["id"] for r in rows]


async def _build_dialog_text(db, chat_id: str) -> str:
    """Concatenate the chat transcript into a single text blob for summarization."""
    msgs = await db.messages.find(
        {"chatId": chat_id},
        {"_id": 0, "role": 1, "content": 1, "createdAt": 1},
    ).sort("createdAt", 1).to_list(200)
    lines = []
    for m in msgs:
        role = "Ученик" if m.get("role") == "user" else "Наставник"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def summarize_tutor_chat(db, chat: dict, user_id: str) -> dict:
    """Summarize a finished tutor chat into per-book progress notes.

    Returns ``{"updated": [book_ids], "skipped": reason?}``. Safe to call on any
    chat — silently no-ops when the chat isn't a tutor chat, has no active books,
    or has too little content to summarize.
    """
    if not chat or chat.get("mode") != "tutor":
        return {"updated": [], "skipped": "not_tutor"}

    book_ids = await _active_library_book_ids(db, chat)
    if not book_ids:
        return {"updated": [], "skipped": "no_books"}

    dialog_text = await _build_dialog_text(db, chat["id"])
    if len(dialog_text.strip()) < 40:
        return {"updated": [], "skipped": "too_short"}

    api_key = os.environ.get("CLAUDE_API_KEY", "")
    if not api_key:
        return {"updated": [], "skipped": "no_api_key"}

    claude_client = anthropic.AsyncAnthropic(api_key=api_key)

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "tutor_memory": 1})
    tutor_memory = (user or {}).get("tutor_memory") or {}

    updated = []
    for book_id in book_ids:
        old = (tutor_memory.get(book_id) or {}).get("summary", "")
        summary, progress = await _summarize_one(claude_client, old, dialog_text)
        if not summary:
            continue
        entry = {
            "summary": summary,
            "progressPercent": progress if progress is not None
            else (tutor_memory.get(book_id) or {}).get("progressPercent", 0),
            "lastSession": _now_iso(),
            "updatedAt": _now_iso(),
        }
        await db.users.update_one(
            {"id": user_id},
            {"$set": {f"tutor_memory.{book_id}": entry}},
        )
        updated.append(book_id)

    return {"updated": updated}
