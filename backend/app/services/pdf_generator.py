"""Render a cover letter into a compact, portal-ready PDF document."""

from __future__ import annotations

import unicodedata


class PdfGenerator:
    """fpdf2 renderer using its built-in Helvetica font."""

    def render(self, letter_text: str) -> bytes:
        if not letter_text.strip():
            raise ValueError("Cannot render an empty cover letter.")
        # Built-in Helvetica is Latin-1. Normalize rather than silently failing on
        # curly punctuation copied from a job description.
        safe_text = unicodedata.normalize("NFKD", letter_text).encode("latin-1", "replace").decode("latin-1")
        from fpdf import FPDF

        pdf = FPDF(format="letter")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()
        pdf.set_margins(20, 20, 20)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, safe_text)
        return bytes(pdf.output())
