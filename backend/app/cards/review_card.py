"""Build the ASI:One review card for an already-visible cover letter."""

from __future__ import annotations

from uuid import uuid4

from uagents_core.contrib.protocols.chat import MetadataContent
from uagents_core.contrib.protocols.chat.cards import (
    CtaAction,
    ReviewCardPayload,
    ReviewSummaryRow,
    create_card_content,
)

from app.models import DraftState


def build_review_card(draft: DraftState) -> MetadataContent:
    """Return action-only card; letter content deliberately remains in chat text."""
    job = draft.job
    word_count = len(draft.letter_text.split())
    card = ReviewCardPayload(
        title="Review cover letter",
        summary_rows=[
            ReviewSummaryRow(label="Role", value=job.title or "Job posting"),
            ReviewSummaryRow(label="Company", value=job.company or "Not specified"),
            ReviewSummaryRow(label="Word count", value=str(word_count)),
        ],
        approve_cta=CtaAction(
            label="Generate PDF",
            selection={"action": "generate_pdf", "draft_id": draft.draft_id},
            primary=True,
        ),
        reject_cta=CtaAction(
            label="Revise in Chat",
            selection={"action": "revise", "draft_id": draft.draft_id},
        ),
    )
    return create_card_content(card, card_id=uuid4())
