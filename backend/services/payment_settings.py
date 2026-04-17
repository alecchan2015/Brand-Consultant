"""
Membership + payment configuration.

Two SystemSetting keys:
    membership_config           → tier labels, feature labels, support info, tier→features map
    payment_providers_config    → per-channel credentials (Stripe/Alipay/Wechat/Manual)
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


# ──────────────────────────────────────────────────────────────────────────────
# Membership config
# ──────────────────────────────────────────────────────────────────────────────
MEMBERSHIP_KEY = "membership_config"

MEMBERSHIP_DEFAULTS: Dict[str, Any] = {
    "grace_period_days": 0,
    "tier_labels": {
        "regular": "普通用户",
        "vip":     "VIP",
        "vvip":    "VVIP",
        "vvvip":   "VVVIP",
    },
    "tier_features": {
        "regular": [],
        "vip":     ["gamma_ppt", "hires_logo", "poster_basic"],
        "vvip":    ["gamma_ppt", "hires_logo", "google_image", "poster_basic", "poster_premium"],
        "vvvip":   ["gamma_ppt", "hires_logo", "google_image", "poster_basic", "poster_premium", "priority_queue", "priority_support"],
    },
    "feature_labels": {
        "gamma_ppt":        "Gamma 商业级 PPT 生成",
        "hires_logo":       "高分辨率 Logo 设计",
        "google_image":     "Google AI 图片生成",
        "poster_basic":     "商业海报 · 基础 (OpenAI)",
        "poster_premium":   "商业海报 · 高级 (FLUX/即梦)",
        "priority_support": "专属客服",
        "priority_queue":   "任务优先队列",
    },
    "support_info": {
        "vip":   {"name": "会员助手", "wechat": "", "phone": "", "email": ""},
        "vvip":  {"name": "资深顾问", "wechat": "", "phone": "", "email": ""},
        "vvvip": {"name": "VIP 经理", "wechat": "", "phone": "", "email": ""},
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Payment providers config
# ──────────────────────────────────────────────────────────────────────────────
PAYMENT_KEY = "payment_providers_config"

PAYMENT_DEFAULTS: Dict[str, Any] = {
    "stripe": {
        "enabled":         False,
        "mode":            "test",                # test | live
        "secret_key":      "",
        "publishable_key": "",
        "webhook_secret":  "",
        "success_url":     "",                    # where Stripe redirects after payment
        "cancel_url":      "",
    },
    "alipay": {
        "enabled":           False,
        "mode":              "sandbox",           # sandbox | production
        "app_id":            "",
        "private_key":       "",
        "alipay_public_key": "",
        "notify_url":        "",                  # our webhook URL
        "return_url":        "",
    },
    "wechat": {
        "enabled":       False,
        "mode":          "sandbox",
        "mchid":         "",
        "app_id":        "",
        "api_v3_key":    "",
        "cert_serial":   "",
        "cert_private":  "",                      # PEM-encoded
        "notify_url":    "",
    },
    "manual": {
        "enabled":     True,
        "description": "测试模式 · 下单后请联系管理员人工确认收款",
        "hint":        "扫码转账后点击「我已完成支付」，管理员将在 24 小时内确认。",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────
def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def _load(db: Optional[Session], key: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(defaults))
    if db is None:
        return cfg
    try:
        from models import SystemSetting
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row and row.value:
            _deep_merge(cfg, json.loads(row.value))
    except Exception as exc:                                               # noqa: BLE001
        print(f"[payment_settings] load {key} failed: {exc}")
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


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────
def load_membership_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, MEMBERSHIP_KEY, MEMBERSHIP_DEFAULTS)


def save_membership_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, MEMBERSHIP_KEY, MEMBERSHIP_DEFAULTS, patch)


def load_payment_config(db: Optional[Session]) -> Dict[str, Any]:
    return _load(db, PAYMENT_KEY, PAYMENT_DEFAULTS)


def save_payment_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    return _save(db, PAYMENT_KEY, PAYMENT_DEFAULTS, patch)


# ──────────────────────────────────────────────────────────────────────────────
# Redaction (mask sensitive fields)
# ──────────────────────────────────────────────────────────────────────────────
_SENSITIVE_PER_CHANNEL = {
    "stripe":  ("secret_key", "webhook_secret"),
    "alipay":  ("private_key", "alipay_public_key"),
    "wechat":  ("api_v3_key", "cert_private"),
    "manual":  (),
}


def _mask(v: str) -> str:
    if not v:
        return ""
    if len(v) <= 8:
        return "****"
    return f"{v[:4]}...{v[-4:]}"


def redact_payment(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(cfg))
    for ch, fields in _SENSITIVE_PER_CHANNEL.items():
        sub = out.get(ch, {})
        for f in fields:
            val = sub.get(f, "")
            sub[f"{f}_set"] = bool(val)
            sub[f] = _mask(val)
    return out


def enabled_channels(cfg: Dict[str, Any]) -> list[str]:
    """Return list of currently enabled channel names (for public listing)."""
    return [ch for ch, conf in cfg.items() if conf.get("enabled")]
