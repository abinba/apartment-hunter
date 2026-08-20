"""Database schema.

Everything is scoped by `uid` — the Firebase subject of whoever signed in. One
person's criteria never touch another's, and there is no notion of an admin who
sees everything.

A note on `candidate.answers`: criteria are user-editable at runtime, so a column
per criterion is impossible and a fully normalised candidate_value table would
turn every read into a join and every rename into a migration. The criteria
themselves are properly relational — that is where integrity matters, because
that is what the admin panel edits. The per-candidate answers are a sparse bag
of key/value pairs against those criteria, which is exactly what jsonb is for.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "app_user"
    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    seeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)


class Category(Base, TimestampMixin):
    """A UI grouping on the candidate form. Ordering is explicit, not implied."""
    __tablename__ = "category"
    __table_args__ = (UniqueConstraint("uid", "key", name="uq_category_uid_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(
        ForeignKey("app_user.uid", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(32), default="#4d4d4d", nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="category", order_by="Criterion.sort")


class Criterion(Base, TimestampMixin):
    """One question about a flat, and how it turns into points.

    `importance` is the friendly control — must / important / nice / none. It
    maps to a default weight. `weight_override` is the escape hatch for when a
    number is wanted directly; null means "derive it from importance".
    """
    __tablename__ = "criterion"
    __table_args__ = (
        UniqueConstraint("uid", "key", name="uq_criterion_uid_key"),
        Index("ix_criterion_uid_archived", "uid", "archived"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(
        ForeignKey("app_user.uid", ondelete="CASCADE"), index=True, nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"))

    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    hint: Mapped[str | None] = mapped_column(Text)

    # num | yesno | r3 | enum | date | text | calc | distance
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # must | important | nice | none   ("none" = collected but not scored)
    importance: Mapped[str] = mapped_column(String(16), default="important", nullable=False)
    weight_override: Mapped[float | None] = mapped_column(Numeric(6, 2))

    options: Mapped[list | None] = mapped_column(JSONB)   # enum: [{value, points}]
    config: Mapped[dict | None] = mapped_column(JSONB)    # distance: {full, zero}

    scored: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Whether the vision pass is allowed to answer this. Asking a photograph
    # about the deposit produces confident nonsense.
    photo_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Whether the scraper asks about it at all.
    scrapable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Archived criteria vanish from the form and stop scoring, but every value
    # already recorded against them stays on the candidate. Nothing is lost.
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Built-in criteria can be edited and archived but not hard-deleted, so the
    # scraper prompt cannot lose the fields it was written around.
    builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped[Category | None] = relationship(back_populates="criteria")

    IMPORTANCE_WEIGHT = {"must": 5.0, "important": 3.0, "nice": 1.0, "none": 0.0}

    @property
    def weight(self) -> float:
        if not self.scored:
            return 0.0
        if self.weight_override is not None:
            return float(self.weight_override)
        return self.IMPORTANCE_WEIGHT.get(self.importance, 0.0)


class Place(Base, TimestampMixin):
    """A destination whose travel time is scored, e.g. work or the gym."""
    __tablename__ = "place"
    __table_args__ = (UniqueConstraint("uid", "key", name="uq_place_uid_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(
        ForeignKey("app_user.uid", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Numeric(6, 2), default=2, nullable=False)
    depart_hour: Mapped[float | None] = mapped_column(Numeric(4, 2))
    # [{mode, share, full, zero}]
    modes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Setting(Base, TimestampMixin):
    """Scoring parameters: budget, thresholds, distance curves, city."""
    __tablename__ = "setting"
    uid: Mapped[str] = mapped_column(
        ForeignKey("app_user.uid", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidate"
    __table_args__ = (
        UniqueConstraint("uid", "ext_id", name="uq_candidate_uid_ext"),
        Index("ix_candidate_uid_archived", "uid", "archived"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(
        ForeignKey("app_user.uid", ondelete="CASCADE"), index=True, nullable=False)
    # The id the browser already uses, so existing local data migrates cleanly.
    ext_id: Mapped[str] = mapped_column(String(64), nullable=False)

    address: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    photos: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # criterion key -> value, as strings, exactly as the form holds them.
    # Named `answers`, not `values`: VALUES is a reserved word in Postgres and
    # SQLAlchemy does not quote it, so the CREATE TABLE would be a syntax error.
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # place key -> {mode: minutes}
    travel: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # what the last scrape reported, kept for the confidence and evidence view
    scrape: Mapped[dict | None] = mapped_column(JSONB)

    status_override: Mapped[str | None] = mapped_column(String(32))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Client wall-clock stamp, used for last-write-wins on a single field.
    client_updated_at: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
