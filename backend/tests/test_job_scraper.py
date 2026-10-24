from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.services.job_scraper import JobScrapeError, JinaJobScraper


def test_naukri_homepage_explains_specific_listing_or_paste_fallback() -> None:
    with pytest.raises(JobScrapeError, match="homepage"):
        JinaJobScraper().fetch("https://www.naukri.com")


def test_timeout_has_paste_description_fallback() -> None:
    with patch("app.services.job_scraper.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = httpx.ReadTimeout("slow")
        with pytest.raises(JobScrapeError, match="paste the description"):
            JinaJobScraper(timeout_seconds=0.1).fetch("https://careers.example.com/jobs/1")


def test_http_408_is_reported_as_blocked_or_unavailable_with_fallback() -> None:
    response = httpx.Response(408, request=httpx.Request("GET", "https://r.jina.ai/example"))
    with patch("app.services.job_scraper.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        with pytest.raises(JobScrapeError, match="HTTP 408"):
            JinaJobScraper().fetch("https://careers.example.com/jobs/1")


def test_anti_bot_page_is_rejected_without_returning_as_job_text() -> None:
    response = httpx.Response(
        200,
        text="Verify you are human " + ("access denied " * 30),
        request=httpx.Request("GET", "https://r.jina.ai/example"),
    )
    with patch("app.services.job_scraper.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        with pytest.raises(JobScrapeError, match="automated access"):
            JinaJobScraper().fetch("https://careers.example.com/jobs/1")
