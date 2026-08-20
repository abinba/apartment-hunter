"""Runtime configuration, read from the environment (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _csv(name: str) -> list[str]:
    raw = os.getenv(name, "") or ""
    return [x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()]


@dataclass
class Config:
    scrapingbee_key: str = field(default_factory=lambda: os.getenv("SCRAPINGBEE_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"))

    firebase_project_id: str = field(
        default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", "apartment-hunter-41fd6"))
    allowed_emails: list[str] = field(default_factory=lambda: _csv("ALLOWED_EMAILS"))
    cors_origins: list[str] = field(default_factory=lambda: _csv("CORS_ORIGINS"))

    max_photos: int = field(default_factory=lambda: int(os.getenv("MAX_PHOTOS", "12")))
    photo_max_px: int = field(default_factory=lambda: int(os.getenv("PHOTO_MAX_PX", "1024")))
    job_ttl_s: int = field(default_factory=lambda: int(os.getenv("JOB_TTL_SECONDS", "1800")))
    max_jobs_per_user: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_JOBS_PER_USER", "3")))
    daily_job_cap: int = field(default_factory=lambda: int(os.getenv("DAILY_JOB_CAP", "60")))

    def problems(self) -> list[str]:
        out = []
        if not self.scrapingbee_key:
            out.append("SCRAPINGBEE_API_KEY is not set")
        if not self.anthropic_key:
            out.append("ANTHROPIC_API_KEY is not set")
        if not self.firebase_project_id:
            out.append("FIREBASE_PROJECT_ID is not set")
        if not self.allowed_emails:
            out.append("ALLOWED_EMAILS is empty — any signed-in Google account could "
                       "spend your ScrapingBee and Anthropic credit")
        if not self.cors_origins:
            out.append("CORS_ORIGINS is empty — the browser will refuse to call this API")
        return out
