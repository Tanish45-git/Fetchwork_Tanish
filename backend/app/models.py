"""Shared data models for job postings, cover letters, and session state."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class EducationItem(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start: str | None = None
    end: str | None = None
    details: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str
    title: str
    start: str | None = None
    end: str | None = None
    location: str | None = None
    bullets: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    """Applicant resume. Only facts present in the loaded JSON may be used downstream."""

    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None
    github: str | None = None
    summary: str | None = None
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class JobData(BaseModel):
    """A validated and extracted public job posting."""

    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    raw_text: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DraftStatus(StrEnum):
    IDLE = "idle"
    DRAFTED = "drafted"
    REVISE_PENDING = "revise_pending"
    GENERATING_PDF = "generating_pdf"
    PDF_READY = "pdf_ready"
    FAILED = "failed"


class DraftState(BaseModel):
    """The current cover-letter draft for one chat participant."""

    draft_id: str
    sender: str
    job: JobData
    letter_text: str
    status: DraftStatus = DraftStatus.DRAFTED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pdf_asset_id: str | None = None
