"""Database tables and engine helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class DetectionRecord(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    model_name: Mapped[str] = mapped_column(String(100))
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    conf_used: Mapped[float] = mapped_column(Float)
    count: Mapped[int] = mapped_column(Integer)
    box_coverage: Mapped[float] = mapped_column(Float)
    boxes: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    counts: Mapped[list[ClassCount]] = relationship(
        back_populates="detection", cascade="all, delete-orphan"
    )


class ClassCount(Base):
    __tablename__ = "class_counts"

    detection_id: Mapped[int] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), primary_key=True
    )
    class_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    n: Mapped[int] = mapped_column(Integer)
    detection: Mapped[DetectionRecord] = relationship(back_populates="counts")


def make_engine(url: str) -> Engine:
    """Create an engine. In-memory SQLite needs one shared connection to keep its tables."""
    if url.startswith("sqlite"):
        if url in ("sqlite://", "sqlite:///:memory:"):
            return create_engine(
                url, connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
