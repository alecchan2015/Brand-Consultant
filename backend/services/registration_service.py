"""
Unified registration service.

All registration paths (username/password, email OTP, phone SMS, Google OAuth)
funnel through `create_user` so policy enforcement (method toggles, domain
filtering, approval flow, per-channel credits, IP rate limits) lives in ONE
place.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from services.auth_settings import load_registration_config
from services import rate_limit_service


CHANNEL_LABELS = {
    "username_password": "用户名密码",
    "email_otp":         "邮箱验证码",
    "phone_sms":         "手机验证码",
    "google_oauth":      "Google 账号",
}


def _check_method_enabled(cfg: Dict[str, Any], channel: str) -> None:
    methods = cfg.get("methods", {})
    if not methods.get(channel, False):
        raise HTTPException(
            403,
            f"{CHANNEL_LABELS.get(channel, channel)} 注册方式当前已关闭",
        )


def _check_email_domain(cfg: Dict[str, Any], email: str) -> None:
    domain = email.split("@")[-1].lower() if "@" in email else ""
    whitelist = [d.lower() for d in cfg.get("email_whitelist_domains", []) if d]
    blacklist = [d.lower() for d in cfg.get("email_blacklist_domains", []) if d]

    if whitelist and domain not in whitelist:
        raise HTTPException(
            403,
            f"仅允许使用以下邮箱域名注册: {', '.join(whitelist)}",
        )
    if domain in blacklist:
        raise HTTPException(403, f"邮箱域名 {domain} 不允许注册")


def _check_ip_rate_limit(db: Session, cfg: Dict[str, Any], ip: Optional[str]) -> None:
    if not ip:
        return
    limit = int(cfg.get("rate_limit", {}).get("register_per_ip_per_day", 10))
    if not rate_limit_service.check_and_increment(
        db, f"register:ip:{ip}", window_seconds=24 * 3600, limit=limit,
    ):
        raise HTTPException(429, f"该 IP 今日注册次数已达上限 ({limit} 次)，请明天再试")


def _check_unique_identity(db: Session, *, username: Optional[str],
                           email: Optional[str], phone: Optional[str],
                           google_id: Optional[str]) -> None:
    from models import User
    if username:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(409, "用户名已被注册")
    if email:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(409, "邮箱已被注册")
    if phone:
        if db.query(User).filter(User.phone == phone).first():
            raise HTTPException(409, "手机号已被注册")
    if google_id:
        if db.query(User).filter(User.google_id == google_id).first():
            raise HTTPException(409, "该 Google 账号已绑定其他用户")


def create_user(
    db: Session,
    channel: str,
    *,
    username: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    password_hash: Optional[str] = None,
    google_id: Optional[str] = None,
    google_email: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
):
    """Create a new User under channel-specific rules.

    Returns (user, requires_approval). Caller decides whether to issue JWT.
    """
    from models import User

    cfg = load_registration_config(db)

    # Policy gates
    _check_method_enabled(cfg, channel)
    if channel == "email_otp" and email:
        _check_email_domain(cfg, email)
    _check_ip_rate_limit(db, cfg, ip)
    _check_unique_identity(db, username=username, email=email,
                           phone=phone, google_id=google_id)

    # Auto-generate username if caller didn't supply one
    if not username:
        if email:
            base = email.split("@")[0]
        elif phone:
            base = f"u{phone[-8:]}"
        elif google_email:
            base = google_email.split("@")[0]
        else:
            base = "user"
        username = _unique_username(db, base)

    # Per-channel default credits
    credits = int(cfg.get("credits_by_channel", {}).get(channel, 100))

    # Approval workflow
    approval_required = bool(cfg.get("approval_required", False))

    user = User(
        username=username,
        email=email or f"{username}@placeholder.local",
        password_hash=password_hash,
        role="user",
        credits=credits,
        is_active=not approval_required,          # inactive until approved
        phone=phone,
        auth_provider=channel,
        google_id=google_id,
        google_email=google_email,
        pending_approval=approval_required,
        company_name=(profile or {}).get("company_name"),
        industry=(profile or {}).get("industry"),
        position=(profile or {}).get("position"),
        company_size=(profile or {}).get("company_size"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, approval_required


def _unique_username(db: Session, base: str) -> str:
    from models import User
    # Sanitize: keep only alnum, underscore, dot, dash
    clean = "".join(c for c in base if c.isalnum() or c in "_.-")[:30] or "user"
    candidate = clean
    suffix = 0
    while db.query(User).filter(User.username == candidate).first():
        suffix += 1
        candidate = f"{clean}{suffix}"
        if suffix > 99:
            import secrets
            candidate = f"{clean}_{secrets.token_hex(3)}"
            break
    return candidate
