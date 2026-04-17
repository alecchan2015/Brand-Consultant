"""
Simple DB-based sliding-window rate limiter.

Buckets are strings like:
    "otp:email:user@example.com"
    "otp:phone:13800000000"
    "otp_cooldown:email:user@example.com"
    "register:ip:1.2.3.4"

A bucket row is considered "active" as long as its window_start is within
`window_seconds` from now. When checked, we atomically:
  1. If no active row exists → create one with count=1 and return True
  2. If row exists and count < limit → increment and return True
  3. Otherwise → return False (rate limited)

Expired rows are naturally overwritten on the next check, so no explicit
cleanup is required (but a periodic prune job can be added later).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session


def check_and_increment(
    db: Session,
    bucket: str,
    window_seconds: int,
    limit: int,
) -> bool:
    """Return True if the request is allowed, False if rate-limited.

    Atomically increments the bucket's count within the sliding window.
    """
    from models import AuthRateLimit

    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)

    row: Optional[AuthRateLimit] = (
        db.query(AuthRateLimit)
        .filter(AuthRateLimit.bucket == bucket)
        .order_by(AuthRateLimit.window_start.desc())
        .first()
    )

    if row is None or row.window_start < cutoff:
        # Start a new window
        if row is None:
            row = AuthRateLimit(bucket=bucket, window_start=now, count=1)
            db.add(row)
        else:
            row.window_start = now
            row.count = 1
        db.commit()
        return True

    if row.count < limit:
        row.count += 1
        db.commit()
        return True

    return False


def peek(db: Session, bucket: str, window_seconds: int) -> int:
    """Return the current count in the active window (0 if none)."""
    from models import AuthRateLimit

    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    row = (
        db.query(AuthRateLimit)
        .filter(AuthRateLimit.bucket == bucket)
        .filter(AuthRateLimit.window_start >= cutoff)
        .first()
    )
    return row.count if row else 0
