"""Deterministic tests for the production InternAssist chat flow."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.handlers.chat_handler import InternAssistServices, handle_chat_message
from app.models import DraftState, JobData, Resume
from app.session import SessionStore
from app.utils.url_validator import InvalidJobUrl, validate_public_job_url


LETTER = " ".join(["Alex builds Python APIs and writes tests."] * 40)


def _services() -> InternAssistServices:
    scraper = MagicMock()
    scraper.fetch.return_value = JobData(
        url="https://careers.example.com/jobs/1",
        title="Software Engineering Intern",
        company="Example Co",
        raw_text="Example job posting " * 30,
    )
    generator = MagicMock()
    generator.draft.return_value = LETTER
    pdf_generator = MagicMock()
    pdf_generator.render.return_value = b"%PDF-1.7 test"
    storage = MagicMock()
    storage.deliver = AsyncMock(return_value=None)
    return InternAssistServices(
        resume=Resume(name="Alex Example", skills=["Python"]),
        scraper=scraper,
        generator=generator,
        pdf_generator=pdf_generator,
        storage=storage,
        sessions=SessionStore(),
    )


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.send = AsyncMock()
    return ctx


def test_public_url_validation_rejects_private_targets() -> None:
    assert validate_public_job_url("https://careers.example.com/role") == "https://careers.example.com/role"
    for value in ["file:///tmp/job", "http://localhost/job", "http://127.0.0.1/job", "https://192.168.1.8/job"]:
        try:
            validate_public_job_url(value)
        except InvalidJobUrl:
            pass
        else:
            raise AssertionError(f"expected rejection for {value}")


def test_url_creates_draft_and_review_card() -> None:
    services, ctx = _services(), _ctx()
    asyncio.run(handle_chat_message(ctx, "user-1", ChatMessage(content=[TextContent(text="https://careers.example.com/jobs/1")]), services))
    draft = services.sessions.latest("user-1")
    assert draft is not None
    assert services.scraper.fetch.call_count == 1
    assert services.generator.draft.call_count == 1
    sent = ctx.send.call_args_list[-1].args[1]
    assert any(isinstance(block, MetadataContent) for block in sent.content)


def test_revision_uses_current_job_and_returns_a_new_draft() -> None:
    services, ctx = _services(), _ctx()
    first = DraftState(draft_id="first", sender="user-1", job=services.scraper.fetch.return_value, letter_text=LETTER)
    services.sessions.save(first)
    asyncio.run(handle_chat_message(ctx, "user-1", ChatMessage(content=[TextContent(text="Make it shorter and focus on APIs")]), services))
    latest = services.sessions.latest("user-1")
    assert latest is not None and latest.draft_id != "first"
    services.generator.draft.assert_called_once_with(services.resume, first.job, "Make it shorter and focus on APIs")


def test_plain_text_generate_pdf_uses_latest_draft_without_review_card() -> None:
    services, ctx = _services(), _ctx()
    services.sessions.save(DraftState(draft_id="current", sender="user-1", job=services.scraper.fetch.return_value, letter_text=LETTER))
    asyncio.run(handle_chat_message(ctx, "user-1", ChatMessage(content=[TextContent(text="Generate PDF")]), services))
    services.pdf_generator.render.assert_called_once_with(LETTER)
    services.storage.deliver.assert_awaited_once()
    assert not any(
        any(isinstance(block, MetadataContent) for block in call.args[1].content)
        for call in ctx.send.call_args_list
        if isinstance(call.args[1], ChatMessage)
    )


def test_invalid_action_payload_does_not_create_a_card() -> None:
    services, ctx = _services(), _ctx()
    asyncio.run(handle_chat_message(ctx, "user-1", ChatMessage(content=[TextContent(text='{"action":"delete_everything"}')]), services))
    sent = ctx.send.call_args_list[-1].args[1]
    assert isinstance(sent.content[0], TextContent)
    assert not any(isinstance(block, MetadataContent) for block in sent.content)


def test_invalid_url_does_not_become_a_revision() -> None:
    services, ctx = _services(), _ctx()
    services.sessions.save(DraftState(draft_id="current", sender="user-1", job=services.scraper.fetch.return_value, letter_text=LETTER))
    asyncio.run(handle_chat_message(ctx, "user-1", ChatMessage(content=[TextContent(text="http://localhost/internal-job")]), services))
    services.generator.draft.assert_not_called()
    reply = ctx.send.call_args_list[-1].args[1]
    assert "public http(s)" in reply.content[0].text



def test_pasted_job_description_creates_draft_without_scraping() -> None:
    services, ctx = _services(), _ctx()
    description = (
        "Software Engineering Intern\\nResponsibilities: Build APIs and write tests.\\n"
        "Requirements: Python, Git, teamwork. " * 8
    )
    message = ChatMessage(content=[TextContent(text="Job description: " + description)])
    asyncio.run(handle_chat_message(ctx, "user-pasted", message, services))

    draft = services.sessions.latest("user-pasted")
    assert draft is not None
    assert draft.job.url == "user-provided-description"
    assert "Responsibilities" in draft.job.raw_text
    services.scraper.fetch.assert_not_called()
    services.generator.draft.assert_called_once()
    assert services.generator.draft.call_args.args[1] == draft.job


def test_pasted_description_is_prioritized_over_revision() -> None:
    services, ctx = _services(), _ctx()
    prior = DraftState(
        draft_id="old", sender="user-pasted", job=services.scraper.fetch.return_value, letter_text=LETTER
    )
    services.sessions.save(prior)
    description = "Job description: " + ("Responsibilities: build tools. Requirements: Python. " * 5)
    asyncio.run(
        handle_chat_message(ctx, "user-pasted", ChatMessage(content=[TextContent(text=description)]), services)
    )
    latest = services.sessions.latest("user-pasted")
    assert latest is not None and latest.draft_id != "old"
    assert latest.job.url == "user-provided-description"
    services.scraper.fetch.assert_not_called()
