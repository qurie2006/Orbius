"""Simulated clock used by the scheduler and Ops Agent."""

from datetime import datetime, timedelta, timezone

_offset = timedelta(0)


def get_now() -> datetime:
    return datetime.now(timezone.utc) + _offset


def fast_forward(days: int = 30) -> datetime:
    global _offset
    _offset += timedelta(days=days)
    return get_now()


def reset_clock() -> datetime:
    global _offset
    _offset = timedelta(0)
    return get_now()


def offset_days() -> float:
    return _offset.total_seconds() / 86400
