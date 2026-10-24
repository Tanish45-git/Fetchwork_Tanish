"""Persist generated PDFs locally or deliver them through Agentverse storage."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from uagents_core.config import AgentverseConfig
from uagents_core.contrib.protocols.chat import (
    ChatMessage,
    EndSessionContent,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.storage import ExternalStorage


class PdfStorage:
    def __init__(self, *, mode: str, output_dir: Path, agentverse_api_key: str | None = None) -> None:
        self.mode = mode
        self.output_dir = output_dir
        self.agentverse_api_key = agentverse_api_key

    async def deliver(self, ctx: object, sender: str, draft_id: str, pdf_bytes: bytes) -> str | None:
        """Deliver bytes and return remote asset id, if one was created."""
        if self.mode == "agentverse" and self.agentverse_api_key:
            try:
                asset_id = await self._deliver_agentverse(ctx, sender, draft_id, pdf_bytes)
                return asset_id
            except Exception:
                # Keep the fallback usable without logging document contents or tokens.
                getattr(ctx, "logger").warning("Agentverse PDF delivery failed; using local fallback")
        await self._deliver_local(ctx, sender, draft_id, pdf_bytes)
        return None

    async def _deliver_agentverse(self, ctx: object, sender: str, draft_id: str, pdf_bytes: bytes) -> str:
        storage = ExternalStorage(
            api_token=self.agentverse_api_key,
            storage_url=AgentverseConfig().storage_api,
        )
        safe_id = re.sub(r"[^A-Za-z0-9-]", "-", draft_id)[:32]
        name = f"cover_letter_{safe_id}_{uuid4().hex[:8]}.pdf"
        asset_id = await asyncio.to_thread(
            storage.create_asset, name=name, content=pdf_bytes, mime_type="application/pdf", lifetime_hours=24
        )
        await asyncio.to_thread(storage.set_permissions, asset_id=asset_id, agent_address=sender, read=True, write=False)
        try:
            resource_id = UUID(asset_id)
        except ValueError:
            resource_id = uuid4()
        await getattr(ctx, "send")(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[
                    TextContent(text="Your cover letter PDF is ready below."),
                    ResourceContent(
                        resource_id=resource_id,
                        resource=Resource(
                            uri=f"agent-storage://{storage.storage_url}/{asset_id}",
                            metadata={"mime_type": "application/pdf", "role": "document", "filename": "cover_letter.pdf"},
                        ),
                    ),
                    EndSessionContent(),
                ],
            ),
        )
        return asset_id

    async def _deliver_local(self, ctx: object, sender: str, draft_id: str, pdf_bytes: bytes) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r"[^A-Za-z0-9-]", "-", draft_id)[:32]
        path = self.output_dir / f"cover_letter_{safe_id}.pdf"
        await asyncio.to_thread(path.write_bytes, pdf_bytes)
        await getattr(ctx, "send")(
            sender,
            ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(text=f"Your PDF is ready and saved locally to {path} (not a chat attachment)."), EndSessionContent()],
            ),
        )
