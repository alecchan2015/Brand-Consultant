"""
One-time password (OTP) generation, storage and verification.

OTPs are 6-digit numeric codes valid for 10 minutes. Re-issuing a code for
the same (channel, target, purpose) invalidates any unused prior code, so
only the most recent code is ever valid.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

OTP_LENGTH = 6
OTP_TTL_MINUTES = 10


def generate_code() -> str:
    """Generate a fresh 6-digit numeric code (zero-padded)."""
    n = secrets.randbelow(10 ** OTP_LENGTH)
    return str(n).zfill(OTP_LENGTH)


def create_otp(
    db: Session,
    channel: str,
    target: str,
    purpose: str = "register",
    ip: Optional[str] = None,
) -> str:
    """Create and persist a new OTP, invalidating prior unused codes for the
    same (channel, target, purpose). Returns the plaintext code for delivery.
    """
    from models import OtpCode

    # Invalidate prior unused codes
    db.query(OtpCode).filter(
        OtpCode.channel == channel,
        OtpCode.target == target,
        OtpCode.purpose == purpose,
        OtpCode.used_at.is_(None),
    ).delete(synchronize_session=False)

    code = generate_code()
    row = OtpCode(
        channel=channel,
        target=target,
        code=code,
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        ip=ip,
    )
    db.add(row)
    db.commit()
    return code


def verify_otp(
    db: Session,
    channel: str,
    target: str,
    code: str,
    purpose: str = "register",
) -> bool:
    """Verify an OTP. On success marks used_at and returns True. Expired /
    used / wrong codes return False without side effects on unrelated rows.
    """
    from models import OtpCode

    row = (
        db.query(OtpCode)
        .filter(
            OtpCode.channel == channel,
            OtpCode.target == target,
            OtpCode.purpose == purpose,
            OtpCode.used_at.is_(None),
        )
        .order_by(OtpCode.id.desc())
        .first()
    )

    if row is None:
        return False
    if row.expires_at < datetime.utcnow():
        return False
    if row.code != code:
        return False

    row.used_at = datetime.utcnow()
    db.commit()
    return True
