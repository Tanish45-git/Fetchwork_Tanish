"""In-memory session state keyed by sender for the review-to-PDF flow."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import DraftState, DraftStatus


class SessionStore:
    """Small process-local store; deliberately not a database."""

    def __init__(self) -> None:
        self._drafts: dict[tuple[str, str], DraftState] = {}
        self._latest_draft_id: dict[str, str] = {}
        self._generating: set[tuple[str, str]] = set()

    def save(self, draft: DraftState) -> DraftState:
        self._drafts[(draft.sender, draft.draft_id)] = draft
        self._latest_draft_id[draft.sender] = draft.draft_id
        return draft

    def get(self, sender: str, draft_id: str) -> DraftState | None:
        return self._drafts.get((sender, draft_id))

    def latest(self, sender: str) -> DraftState | None:
        draft_id = self._latest_draft_id.get(sender)
        return self.get(sender, draft_id) if draft_id else None

    def update_status(
        self, draft: DraftState, status: DraftStatus, *, pdf_asset_id: str | None = None
    ) -> DraftState:
        draft.status = status
        draft.updated_at = datetime.now(timezone.utc)
        if pdf_asset_id is not None:
            draft.pdf_asset_id = pdf_asset_id
        return self.save(draft)

    def begin_pdf_generation(self, sender: str, draft_id: str) -> bool:
        key = (sender, draft_id)
        if key in self._generating:
            return False
        self._generating.add(key)
        return True

    def finish_pdf_generation(self, sender: str, draft_id: str) -> None:
        self._generating.discard((sender, draft_id))


session_store = SessionStore()
