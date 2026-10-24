"""Fetch and extract public job postings through Jina Reader."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from app.models import JobData
from app.utils.url_validator import InvalidJobUrl, validate_public_job_url


class JobScrapeError(RuntimeError):
    """A public posting could not be fetched or did not contain usable content."""


class JinaJobScraper:
    """Synchronous HTTP client; callers must invoke it with ``asyncio.to_thread``."""

    def __init__(self, *, api_key: str | None = None, timeout_seconds: float = 20.0) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str) -> JobData:
        try:
            public_url = validate_public_job_url(url)
        except InvalidJobUrl as exc:
            raise JobScrapeError(str(exc)) from exc
        from urllib.parse import urlparse

        parsed_url = urlparse(public_url)
        host = (parsed_url.hostname or "").lower().removeprefix("www.")
        if host == "naukri.com" and parsed_url.path.strip("/") == "":
            raise JobScrapeError(
                "That is Naukri's homepage, not a specific job listing. Open the job you want and "
                "copy its full job-posting URL, or send `Job description:` followed by the job text."
            )
        headers = {"Accept": "text/markdown"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds, connect=min(8.0, self.timeout_seconds)), follow_redirects=True) as client:
                response = client.get(f"https://r.jina.ai/{public_url}", headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise JobScrapeError(
                "The job site took too long to respond. This can happen when a site blocks automated readers. "
                "Try the exact job-posting URL again, or paste the description using `Job description:`."
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise JobScrapeError(
                f"The job page could not be retrieved (HTTP {status}). The site may block automated access. "
                "Paste the description using `Job description:` to continue."
            ) from exc
        except httpx.HTTPError as exc:
            raise JobScrapeError(
                "I could not retrieve that posting. Try its exact public job URL or paste the description "
                "using `Job description:`."
            ) from exc
        raw_text = response.text.strip()
        lowered = raw_text.casefold()
        if len(raw_text) < 200 or any(marker in lowered[:1200] for marker in (
            "enable javascript", "verify you are human", "access denied", "captcha", "robot check"
        )):
            raise JobScrapeError(
                "That page did not return a usable job description (it may require JavaScript or block automated access). "
                "Paste the description using `Job description:` and I can continue."
            )
        return JobData(
            url=public_url,
            title=_extract_title(raw_text),
            company=_extract_company(raw_text),
            raw_text=raw_text,
            fetched_at=datetime.now(timezone.utc),
        )


def _extract_title(text: str) -> str | None:
    for line in text.splitlines()[:20]:
        cleaned = line.lstrip("# ").strip()
        if cleaned and len(cleaned) < 160 and not cleaned.lower().startswith(("http", "image")):
            return cleaned
    return None


def _extract_company(text: str) -> str | None:
    match = re.search(r"(?:company|organization)\s*:\s*([^\n]{2,100})", text, re.IGNORECASE)
    return match.group(1).strip() if match else None
