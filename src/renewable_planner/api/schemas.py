"""Pydantic request/response models for the web API.

Kept separate from the domain: these are wire-format shapes for one
interface, not the models ``ScreenSite`` operates on.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class FindingSummary(BaseModel):
    """One constraint finding, shaped for JSON responses."""

    id: UUID
    constraint_id: UUID
    level: str
    status: str
    data_source: str
    data_version: str
    message: str


class ScreeningSummary(BaseModel):
    """Everything a client needs after creating or looking up a screening.

    Area/warning/finding fields are ``None`` until the run has a result
    (e.g. while ``status`` is ``pending``/``running``, or if it ``failed``
    before producing one) — mirrors the CLI's own summary, just as JSON.
    """

    id: UUID
    project_id: UUID
    site_id: UUID
    technology: str
    country: str
    status: str
    error_message: str | None = None
    initial_area_square_meters: float | None = None
    excluded_area_square_meters: float | None = None
    available_area_square_meters: float | None = None
    warnings: int | None = None
    findings: list[FindingSummary] = Field(default_factory=list)
