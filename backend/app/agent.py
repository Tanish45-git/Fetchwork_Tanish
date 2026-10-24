"""uAgent entrypoint for the complete InternAssist conversation flow."""

from __future__ import annotations

import os

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, chat_protocol_spec

from app.config import load_settings
from app.data.resume import load_resume
from app.handlers.chat_handler import InternAssistServices, handle_chat_message
from app.services.cover_letter_generator import CoverLetterGenerator
from app.services.job_scraper import JinaJobScraper
from app.services.pdf_generator import PdfGenerator
from app.services.storage_service import PdfStorage
from app.session import SessionStore


def create_agent() -> Agent:
    settings = load_settings()
    services = InternAssistServices(
        resume=load_resume(),
        scraper=JinaJobScraper(api_key=settings.jina_api_key),
        generator=CoverLetterGenerator(base_url=settings.llm_base_url, api_key=settings.llm_api_key, model=settings.llm_model),
        pdf_generator=PdfGenerator(),
        storage=PdfStorage(mode=settings.pdf_storage, output_dir=settings.output_dir, agentverse_api_key=settings.agentverse_api_key),
        sessions=SessionStore(),
    )
    mailbox = os.getenv("USE_MAILBOX", "false").lower() in {"1", "true", "yes"}
    agent = Agent(name=settings.agent_name, seed=settings.agent_seed or None, port=settings.agent_port, mailbox=mailbox)
    protocol = Protocol(spec=chat_protocol_spec)

    @protocol.on_message(ChatMessage)
    async def on_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
        await handle_chat_message(ctx, sender, msg, services)

    @protocol.on_message(ChatAcknowledgement)
    async def on_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
        ctx.logger.debug("Chat acknowledgement received")

    agent.include(protocol, publish_manifest=True)
    return agent


def main() -> None:
    create_agent().run()


if __name__ == "__main__":
    main()
