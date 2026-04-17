"""
Configuration helpers for the multi-channel auth/registration system.

Uses the same SystemSetting key/value pattern as ppt_settings.py, but manages
four separate keys (one per concern):

    auth_registration_config   - method toggles, approval flow, credits, domain allow/block, rate limits
    auth_sms_provider          - Tencent Cloud SMS credentials
    auth_email_provider        - SMTP credentials + sender info
    auth_google_oauth          - Google OAuth 2.0 client credentials

Env vars act as a deployment-time override so existing installs keep working
on first boot; admin-saved values in the DB take precedence after that.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


# ──────────────────────────────────────────────────────────────────────────────
# Registration policy (method toggles, approval, credits, rate limits)
# ──────────────────────────────────────────────────────────────────────────────
REGISTRATION_KEY = "auth_registration_config"

REGISTRATION_DEFAULTS: Dict[str, Any] = {
    "methods": {
        "username_password": True,
        "email_otp":         True,
        "phone_sms":         False,
        "google_oauth":      False,
    },
    "approval_required": False,
    "email_whitelist_domains": [],   # e.g. ["pbmba.com"] — empty = allow all
    "email_blacklist_domains": [],
    "credits_by_channel": {
        "username_password": 100,
        "email_otp":         500,
        "phone_sms":         200,
        "google_oauth":      1000,
    },
    "rate_limit": {
        "register_per_ip_per_day":   10,
        "otp_per_target_per_hour":   5,
        "otp_cooldown_seconds":      60,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Tencent Cloud SMS provider
# ──────────────────────────────────────────────────────────────────────────────
SMS_KEY = "auth_sms_provider"

SMS_DEFAULTS: Dict[str, Any] = {
    "provider":     "tencent",
    "secret_id":    os.getenv("TENCENT_SMS_SECRET_ID", ""),
    "secret_key":   os.getenv("TENCENT_SMS_SECRET_KEY", ""),
    "region":       os.getenv("TENCENT_SMS_REGION", "ap-guangzhou"),
    "sdk_app_id":   os.getenv("TENCENT_SMS_SDK_APP_ID", ""),
    "sign_name":    os.getenv("TENCENT_SMS_SIGN_NAME", ""),
    "template_id":  os.getenv("TENCENT_SMS_TEMPLATE_ID", ""),
}


# ──────────────────────────────────────────────────────────────────────────────
# SMTP email provider
# ──────────────────────────────────────────────────────────────────────────────
EMAIL_KEY = "auth_email_provider"

EMAIL_DEFAULTS: Dict[str, Any] = {
    "smtp_host":      os.getenv("SMTP_HOST", ""),
    "smtp_port":      int(os.getenv("SMTP_PORT", "465")),
    "smtp_user":      os.getenv("SMTP_USER", ""),
    "smtp_password":  os.getenv("SMTP_PASSWORD", ""),
    "from_name":      os.getenv("SMTP_FROM_NAME", "Your Brand Consultant"),
    "from_email":     os.getenv("SMTP_FROM_EMAIL", ""),
    "use_ssl":        True,
}


# ──────────────────────────────────────────────────────────────────────────────
# Google OAuth 2.0
# ──────────────────────────────────────────────────────────────────────────────
GOOGLE_KEY = "auth_google_oauth"

GOOGLE_DEFAULTS: Dict[str, Any] = {
    "client_id":     os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
    "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
    "redirect_uri":  os.getenv("GOOGLE_OAUTH_REDIRECT_URI", ""),
}


# ──────────────────────────────────────────────────────────────────────────────
# Generic read/write helpers
# ──────────────────────────────────────────────────────────────────────────────
def _load(db: Optional[Session], key: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(defaults))  # deep copy to avoid mutation
    if db is None:
        return cfg
    try:
        from models import SystemSetting
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row and row.value:
            saved = json.loads(row.value)
            _deep_merge(cfg, saved)
    except Exception as exc:                                                # noqa: BLE001
        print(f"[auth_settings] load {key} failed, using defaults: {exc}")
    return cfg


def _save(db: Session, key: str, defaults: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    from models import SystemSetting
    current = _load(db, key, defaults)
    _deep_merge(current, {k: v for k, v in patch.items() if v is not None})
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = json.dumps(current)
    else:
        row = SystemSetting(key=key, value=json.dumps(current))
        db.add(row)
    db.commit()
    return current


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    """Recursive dict merge (in-place)."""
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def load_registration_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, REGISTRATION_KEY, REGISTRATION_DEFAULTS)


def save_registration_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, REGISTRATION_KEY, REGISTRATION_DEFAULTS, patch)


def load_sms_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, SMS_KEY, SMS_DEFAULTS)


def save_sms_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, SMS_KEY, SMS_DEFAULTS, patch)


def load_email_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, EMAIL_KEY, EMAIL_DEFAULTS)


def save_email_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, EMAIL_KEY, EMAIL_DEFAULTS, patch)


def load_google_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, GOOGLE_KEY, GOOGLE_DEFAULTS)


def save_google_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, GOOGLE_KEY, GOOGLE_DEFAULTS, patch)


# ──────────────────────────────────────────────────────────────────────────────
# Redaction (for safe exposure to frontend)
# ──────────────────────────────────────────────────────────────────────────────
def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def redact_sms(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out["secret_key_set"] = bool(out.get("secret_key"))
    out["secret_key"] = _mask(out.get("secret_key", ""))
    out["secret_id_set"] = bool(out.get("secret_id"))
    out["secret_id"] = _mask(out.get("secret_id", ""))
    return out


def redact_email(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out["smtp_password_set"] = bool(out.get("smtp_password"))
    out["smtp_password"] = _mask(out.get("smtp_password", ""))
    return out


def redact_google(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    out["client_secret_set"] = bool(out.get("client_secret"))
    out["client_secret"] = _mask(out.get("client_secret", ""))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Public config snapshot (for frontend tab visibility)
# ──────────────────────────────────────────────────────────────────────────────
def public_config(db: Optional[Session]) -> Dict[str, Any]:
    """Non-sensitive subset for the public login/register page."""
    reg = load_registration_config(db)
    google = load_google_config(db)
    sms = load_sms_config(db)
    email = load_email_config(db)
    methods = dict(reg.get("methods", {}))

    # Auto-hide a method if its provider is not configured
    if not (google.get("client_id") and google.get("client_secret")):
        methods["google_oauth"] = False
    if not (sms.get("secret_id") and sms.get("secret_key") and sms.get("sdk_app_id")):
        methods["phone_sms"] = False
    if not (email.get("smtp_host") and email.get("smtp_user")):
        methods["email_otp"] = False

    return {
        "methods": methods,
        "approval_required": reg.get("approval_required", False),
    }
