from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from weedlab.api.db import Base, ClassCount, DetectionRecord, make_engine, make_session_factory
from weedlab.api.store import compute_daily

VISITOR = "visitor-aaaaaaaaaaaaaaaa"
OTHER_VISITOR = "visitor-bbbbbbbbbbbbbbbb"


def record(
    when: datetime,
    count: int,
    coverage: float,
    counts: dict[str, int],
    visitor: str = VISITOR,
) -> DetectionRecord:
    return DetectionRecord(
        visitor_id=visitor,
        created_at=when,
        model_name="m",
        image_width=10,
        image_height=10,
        conf_used=0.15,
        count=count,
        box_coverage=coverage,
        boxes=[],
        counts=[ClassCount(class_name=name, n=n) for name, n in counts.items()],
    )


def utc(day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, second, tzinfo=UTC)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        yield s


def seed(session: Session) -> None:
    session.add_all(
        [
            record(utc(20, 23, 59, 59), 2, 0.2, {"a": 2}),
            record(utc(21, 0, 0, 1), 1, 0.4, {"a": 1}),
            record(utc(21, 12), 3, 0.6, {"a": 1, "b": 2}),
        ]
    )
    session.commit()


def test_groups_by_utc_day(session: Session) -> None:
    seed(session)
    series = compute_daily(session, VISITOR, None, None)
    assert [d.day for d in series.days] == ["2026-10-20", "2026-10-21"]
    first, second = series.days
    assert (first.detections, first.weeds_found) == (1, 2)
    assert first.mean_box_coverage == pytest.approx(0.2)
    assert first.counts_by_class == {"a": 2}
    assert (second.detections, second.weeds_found) == (2, 4)
    assert second.mean_box_coverage == pytest.approx(0.5)
    assert second.counts_by_class == {"a": 2, "b": 2}


def test_date_range_limits_the_days(session: Session) -> None:
    seed(session)
    later = compute_daily(session, VISITOR, utc(21), None)
    assert [d.day for d in later.days] == ["2026-10-21"]
    earlier = compute_daily(session, VISITOR, None, utc(20, 23, 59, 59))
    assert [d.day for d in earlier.days] == ["2026-10-20"]
    naive = compute_daily(session, VISITOR, datetime(2026, 10, 21), None)  # no timezone means UTC
    assert [d.day for d in naive.days] == ["2026-10-21"]


def test_a_detection_without_weeds_still_counts_for_its_day(session: Session) -> None:
    session.add(record(utc(22, 8), 0, 0.0, {}))
    session.commit()
    (day,) = compute_daily(session, VISITOR, None, None).days
    assert (day.day, day.detections, day.weeds_found) == ("2026-10-22", 1, 0)
    assert day.mean_box_coverage == 0.0
    assert day.counts_by_class == {}


def test_empty_history_gives_no_days(session: Session) -> None:
    series = compute_daily(session, VISITOR, None, None)
    assert series.days == []
    assert series.start is None
    assert series.end is None


def test_other_visitors_rows_are_left_out(session: Session) -> None:
    seed(session)
    session.add(record(utc(21, 18), 9, 0.9, {"z": 9}, visitor=OTHER_VISITOR))
    session.commit()
    mine = compute_daily(session, VISITOR, None, None)
    assert [d.day for d in mine.days] == ["2026-10-20", "2026-10-21"]
    assert mine.days[1].detections == 2
    assert "z" not in mine.days[1].counts_by_class
    theirs = compute_daily(session, OTHER_VISITOR, None, None)
    assert [(d.day, d.detections, d.weeds_found) for d in theirs.days] == [("2026-10-21", 1, 9)]
    assert theirs.days[0].counts_by_class == {"z": 9}


def test_a_visitor_with_no_rows_gets_no_days_even_with_a_range(session: Session) -> None:
    seed(session)
    nobody = "visitor-cccccccccccccccc"
    assert compute_daily(session, nobody, utc(1), utc(30)).days == []
