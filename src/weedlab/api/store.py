"""Reading and writing detection records. Every read and write is scoped to one visitor."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from weedlab.api.db import ClassCount, DetectionImage, DetectionRecord
from weedlab.api.schemas import (
    DailySeries,
    DailyStats,
    DetectionDetail,
    DetectionOut,
    DetectionPage,
    DetectionSummary,
    Stats,
)

PURGE_CHUNK = 500


def as_utc(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite, user input) as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def save_detection(
    session: Session,
    *,
    visitor_id: str,
    model_name: str,
    width: int,
    height: int,
    conf: float,
    coverage: float,
    detections: list[DetectionOut],
    thumbnail: bytes | None = None,
) -> int:
    counts = Counter(d.class_name for d in detections)
    record = DetectionRecord(
        visitor_id=visitor_id,
        model_name=model_name,
        image_width=width,
        image_height=height,
        conf_used=conf,
        count=len(detections),
        box_coverage=coverage,
        boxes=[d.model_dump() for d in detections],
        counts=[ClassCount(class_name=name, n=n) for name, n in counts.items()],
    )
    session.add(record)
    session.flush()
    if thumbnail is not None:
        session.add(DetectionImage(detection_id=record.id, jpeg=thumbnail))
    session.commit()
    return record.id


def to_summary(record: DetectionRecord) -> DetectionSummary:
    return DetectionSummary(
        id=record.id,
        created_at=as_utc(record.created_at),
        model_name=record.model_name,
        image_width=record.image_width,
        image_height=record.image_height,
        conf_used=record.conf_used,
        count=record.count,
        box_coverage=record.box_coverage,
        counts_by_class={c.class_name: c.n for c in record.counts},
    )


def _own_record(session: Session, visitor_id: str, detection_id: int) -> DetectionRecord | None:
    """The record, but only if it belongs to this visitor."""
    return session.scalar(
        select(DetectionRecord).where(
            DetectionRecord.id == detection_id,
            DetectionRecord.visitor_id == visitor_id,
        )
    )


def list_detections(session: Session, visitor_id: str, limit: int, offset: int) -> DetectionPage:
    total = (
        session.scalar(
            select(func.count(DetectionRecord.id)).where(DetectionRecord.visitor_id == visitor_id)
        )
        or 0
    )
    rows = session.scalars(
        select(DetectionRecord)
        .where(DetectionRecord.visitor_id == visitor_id)
        .options(selectinload(DetectionRecord.counts))
        .order_by(DetectionRecord.created_at.desc(), DetectionRecord.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return DetectionPage(
        items=[to_summary(r) for r in rows], total=total, limit=limit, offset=offset
    )


def get_detection(session: Session, visitor_id: str, detection_id: int) -> DetectionDetail | None:
    record = _own_record(session, visitor_id, detection_id)
    if record is None:
        return None
    summary = to_summary(record)
    return DetectionDetail(
        **summary.model_dump(),
        detections=[DetectionOut.model_validate(b) for b in record.boxes],
    )


def get_thumbnail(session: Session, visitor_id: str, detection_id: int) -> bytes | None:
    return session.scalar(
        select(DetectionImage.jpeg)
        .join(DetectionRecord, DetectionRecord.id == DetectionImage.detection_id)
        .where(
            DetectionImage.detection_id == detection_id,
            DetectionRecord.visitor_id == visitor_id,
        )
    )


def delete_detection(session: Session, visitor_id: str, detection_id: int) -> bool:
    record = _own_record(session, visitor_id, detection_id)
    if record is None:
        return False
    session.execute(delete(DetectionImage).where(DetectionImage.detection_id == detection_id))
    session.delete(record)
    session.commit()
    return True


def purge_older_than(session: Session, cutoff: datetime) -> int:
    """Delete every detection created before the cutoff, for all visitors.

    Child rows are removed explicitly so this behaves the same on SQLite, which does not
    enforce foreign keys by default, and on Postgres. Returns how many detections went.
    """
    cutoff = as_utc(cutoff)
    ids = list(
        session.scalars(select(DetectionRecord.id).where(DetectionRecord.created_at < cutoff))
    )
    for start in range(0, len(ids), PURGE_CHUNK):
        chunk = ids[start : start + PURGE_CHUNK]
        session.execute(delete(DetectionImage).where(DetectionImage.detection_id.in_(chunk)))
        session.execute(delete(ClassCount).where(ClassCount.detection_id.in_(chunk)))
        session.execute(delete(DetectionRecord).where(DetectionRecord.id.in_(chunk)))
    session.commit()
    return len(ids)


def compute_stats(
    session: Session, visitor_id: str, start: datetime | None, end: datetime | None
) -> Stats:
    lo = as_utc(start) if start is not None else None
    hi = as_utc(end) if end is not None else None
    totals = select(
        func.count(DetectionRecord.id),
        func.coalesce(func.sum(DetectionRecord.count), 0),
        func.avg(DetectionRecord.box_coverage),
    ).where(DetectionRecord.visitor_id == visitor_id)
    per_class = (
        select(ClassCount.class_name, func.sum(ClassCount.n))
        .join(DetectionRecord, DetectionRecord.id == ClassCount.detection_id)
        .where(DetectionRecord.visitor_id == visitor_id)
        .group_by(ClassCount.class_name)
    )
    if lo is not None:
        totals = totals.where(DetectionRecord.created_at >= lo)
        per_class = per_class.where(DetectionRecord.created_at >= lo)
    if hi is not None:
        totals = totals.where(DetectionRecord.created_at <= hi)
        per_class = per_class.where(DetectionRecord.created_at <= hi)
    n_detections, weeds, mean_cov = session.execute(totals).one()
    rows = session.execute(per_class).all()
    return Stats(
        start=lo,
        end=hi,
        detections=int(n_detections),
        weeds_found=int(weeds),
        mean_box_coverage=None if mean_cov is None else float(mean_cov),
        counts_by_class={name: int(n) for name, n in rows},
    )


def compute_daily(
    session: Session, visitor_id: str, start: datetime | None, end: datetime | None
) -> DailySeries:
    """Per-day totals, with days taken in UTC. Only days that have detections appear."""
    lo = as_utc(start) if start is not None else None
    hi = as_utc(end) if end is not None else None
    totals = select(
        DetectionRecord.created_at, DetectionRecord.count, DetectionRecord.box_coverage
    ).where(DetectionRecord.visitor_id == visitor_id)
    per_class = (
        select(DetectionRecord.created_at, ClassCount.class_name, ClassCount.n)
        .join(ClassCount, ClassCount.detection_id == DetectionRecord.id)
        .where(DetectionRecord.visitor_id == visitor_id)
    )
    if lo is not None:
        totals = totals.where(DetectionRecord.created_at >= lo)
        per_class = per_class.where(DetectionRecord.created_at >= lo)
    if hi is not None:
        totals = totals.where(DetectionRecord.created_at <= hi)
        per_class = per_class.where(DetectionRecord.created_at <= hi)

    n_det: dict[str, int] = {}
    weeds: dict[str, int] = {}
    cover: dict[str, float] = {}
    by_class: dict[str, dict[str, int]] = {}
    for created, count, coverage in session.execute(totals):
        day = as_utc(created).date().isoformat()
        n_det[day] = n_det.get(day, 0) + 1
        weeds[day] = weeds.get(day, 0) + int(count)
        cover[day] = cover.get(day, 0.0) + float(coverage)
    for created, name, n in session.execute(per_class):
        counts = by_class.setdefault(as_utc(created).date().isoformat(), {})
        counts[name] = counts.get(name, 0) + int(n)

    days = [
        DailyStats(
            day=day,
            detections=n_det[day],
            weeds_found=weeds[day],
            mean_box_coverage=cover[day] / n_det[day],
            counts_by_class=by_class.get(day, {}),
        )
        for day in sorted(n_det)
    ]
    return DailySeries(start=lo, end=hi, days=days)
