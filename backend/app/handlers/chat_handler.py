"""Orchestrate the job URL, draft review, revision, and PDF chat flow."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent

from app.cards.review_card import build_review_card
from app.handlers.card_actions import is_json_like_message, parse_action
from app.models import DraftState, DraftStatus, Resume
from app.services.cover_letter_generator import CoverLetterError, CoverLetterGenerator
from app.services.job_scraper import JinaJobScraper, JobScrapeError
from app.services.pdf_generator import PdfGenerator
from app.services.storage_service import PdfStorage
from app.session import SessionStore
from app.utils.url_validator import InvalidJobUrl, validate_public_job_url


_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
_DESCRIPTION_PREFIX_RE = re.compile(r"^\s*(?:job\s+description|job\s+posting|description)\s*:\s*", re.IGNORECASE)


@dataclass(slots=True)
class InternAssistServices:
    resume: Resume
    scraper: JinaJobScraper
    generator: CoverLetterGenerator
    pdf_generator: PdfGenerator
    storage: PdfStorage
    sessions: SessionStore


async def handle_chat_message(ctx: Any, sender: str, msg: ChatMessage, services: InternAssistServices) -> None:
    """Handle one message without logging scraped text, resume contents, or letters."""
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))
    action = parse_action(msg)
    if action:
        await _handle_action(ctx, sender, action, services)
        return
    if is_json_like_message(msg):
        await _send_text(ctx, sender, "I received an unsupported action. Please use Generate PDF or Revise in Chat.")
        return
    text = msg.text().strip()
    url = _find_public_url(text)
    if url:
        await _start_draft(ctx, sender, url, services)
        return
    if "://" in text:
        await _send_text(ctx, sender, "I need a public http(s) job-posting URL.")
        return
    description = _extract_pasted_description(text)
    if description:
        await _start_draft_from_description(ctx, sender, description, services)
        return

    current = services.sessions.latest(sender)
    if current and current.status in {DraftStatus.DRAFTED, DraftStatus.REVISE_PENDING} and text:
        await _revise_draft(ctx, sender, current, text, services)
        return

    await _send_text(
        ctx, sender,
        "Send a specific public job-posting URL, or paste the full job description prefixed with "
        "'Job description:'. A portal homepage (for example, naukri.com) is not a job listing."
    )


async def _handle_action(ctx: Any, sender: str, action: dict[str, str], services: InternAssistServices) -> None:
    draft = services.sessions.get(sender, action["draft_id"]) if action.get("draft_id") else services.sessions.latest(sender)
    if not draft:
        await _send_text(ctx, sender, "I couldn’t find a current draft. Please send the job-posting URL again.")
        return
    if action["action"] == "revise":
        services.sessions.update_status(draft, DraftStatus.REVISE_PENDING)
        await _send_text(ctx, sender, "Tell me what to change. I’ll keep the same job and resume facts.")
        return
    if not services.sessions.begin_pdf_generation(sender, draft.draft_id):
        await _send_text(ctx, sender, "Your PDF is already being generated. Please wait a moment.")
        return
    try:
        services.sessions.update_status(draft, DraftStatus.GENERATING_PDF)
        await _send_text(ctx, sender, "Generating your PDF…")
        pdf_bytes = await asyncio.to_thread(services.pdf_generator.render, draft.letter_text)
        asset_id = await services.storage.deliver(ctx, sender, draft.draft_id, pdf_bytes)
        services.sessions.update_status(draft, DraftStatus.PDF_READY, pdf_asset_id=asset_id)
    except Exception:
        services.sessions.update_status(draft, DraftStatus.FAILED)
        getattr(ctx, "logger").exception("PDF generation failed")
        await _send_text(ctx, sender, "I couldn’t generate the PDF. Please try Generate PDF again.")
    finally:
        services.sessions.finish_pdf_generation(sender, draft.draft_id)


async def _start_draft(ctx: Any, sender: str, url: str, services: InternAssistServices) -> None:
    await _send_text(ctx, sender, "Got it. Fetching the posting…")
    try:
        job = await asyncio.to_thread(services.scraper.fetch, url)
        letter = await asyncio.to_thread(services.generator.draft, services.resume, job)
    except (JobScrapeError, CoverLetterError) as exc:
        getattr(ctx, "logger").warning("Draft pipeline failed: %s", type(exc).__name__)
        await _send_text(ctx, sender, str(exc))
        return
    draft = DraftState(draft_id=str(uuid4()), sender=sender, job=job, letter_text=letter)
    services.sessions.save(draft)
    await _send_draft(ctx, sender, draft)


async def _revise_draft(ctx: Any, sender: str, previous: DraftState, revision: str, services: InternAssistServices) -> None:
    await _send_text(ctx, sender, "Updating your draft…")
    try:
        letter = await asyncio.to_thread(services.generator.draft, services.resume, previous.job, revision)
    except CoverLetterError as exc:
        getattr(ctx, "logger").warning("Revision failed: %s", type(exc).__name__)
        await _send_text(ctx, sender, str(exc))
        return
    draft = DraftState(draft_id=str(uuid4()), sender=sender, job=previous.job, letter_text=letter)
    services.sessions.save(draft)
    await _send_draft(ctx, sender, draft)


async def _send_draft(ctx: Any, sender: str, draft: DraftState) -> None:
    title = draft.job.title or "this role"
    await _send_message(
        ctx,
        sender,
        [
            TextContent(text=f"Here’s your tailored draft for {title}:\n\n{draft.letter_text}\n\nReply with changes, or click Generate PDF when it’s ready."),
            build_review_card(draft),
        ],
    )




async def _start_draft_from_description(
    ctx: Any, sender: str, description: str, services: InternAssistServices
) -> None:
    """Draft from user-pasted job text when the site blocks automated retrieval."""
    from app.models import JobData

    await _send_text(ctx, sender, "Using the job description you pasted…")
    job = JobData(
        url="user-provided-description",
        title=_extract_title_from_description(description),
        raw_text=description,
    )
    try:
        letter = await asyncio.to_thread(services.generator.draft, services.resume, job)
    except CoverLetterError as exc:
        getattr(ctx, "logger").warning("Pasted-description draft failed: %s", type(exc).__name__)
        await _send_text(ctx, sender, str(exc))
        return
    draft = DraftState(draft_id=str(uuid4()), sender=sender, job=job, letter_text=letter)
    services.sessions.save(draft)
    await _send_draft(ctx, sender, draft)


def _extract_pasted_description(text: str) -> str | None:
    """Accept labelled descriptions, or substantial text clearly resembling a posting."""
    match = _DESCRIPTION_PREFIX_RE.match(text)
    if match:
        body = text[match.end():].strip()
        return body if len(body) >= 80 else None
    lower = text.casefold()
    indicators = ("responsibilities", "requirements", "qualifications", "job description", "what you'll do")
    if len(text) >= 500 and sum(term in lower for term in indicators) >= 2:
        return text
    return None


def _extract_title_from_description(text: str) -> str | None:
    for line in text.splitlines()[:12]:
        cleaned = re.sub(r"^[#*\\s-]+", "", line).strip()
        if cleaned and len(cleaned) <= 120 and not cleaned.endswith(":"):
            return cleaned
    return None

def _find_public_url(text: str) -> str | None:
    for match in _URL_RE.findall(text):
        candidate = match.rstrip(".,;:!?)]}")
        try:
            return validate_public_job_url(candidate)
        except InvalidJobUrl:
            continue
    return None


async def _send_text(ctx: Any, sender: str, text: str) -> None:
    await _send_message(ctx, sender, [TextContent(text=text)])


async def _send_message(ctx: Any, sender: str, content: list[Any]) -> None:
    await ctx.send(sender, ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content))
