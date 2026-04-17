"""
Poster provider config — mirrors logo_settings but for full-poster generation.

Single SystemSetting row (key = `poster_provider_config`) holding JSON:
    provider          primary image-gen provider
    fallback          fallback provider (always ends in "openai")
    openai_api_key    OpenAI DALL-E / gpt-image-1 key
    openai_model      "dall-e-3" | "gpt-image-1"
    flux_api_key      Replicate / FAL key for FLUX
    flux_model        "black-forest-labs/flux-1.1-pro" etc.
    jimeng_api_key    ByteDance 即梦 key (中文场景优)
    jimeng_model      model id
    ideogram_api_key  for the calligraphy text layer (future)
    removebg_api_key  for product cutout (future)
    default_size      "portrait" (2160×3840) | "square" (2048×2048) | ...
    default_style     "natural" | "luxury" | "modern" | "playful"
    add_footer        True → render brand footer with QR placeholder + logo
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

SETTING_KEY = "poster_provider_config"

DEFAULTS: Dict[str, Any] = {
    "provider":         os.getenv("POSTER_PROVIDER", "openai"),
    "fallback":         os.getenv("POSTER_FALLBACK", "openai"),
    "openai_api_key":   os.getenv("OPENAI_API_KEY", ""),
    "openai_model":     os.getenv("POSTER_OPENAI_MODEL", "dall-e-3"),
    "openai_base_url":  os.getenv("POSTER_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "flux_api_key":     os.getenv("FLUX_API_KEY", ""),
    "flux_model":       os.getenv("FLUX_MODEL", "black-forest-labs/flux-1.1-pro"),
    "jimeng_api_key":   os.getenv("JIMENG_API_KEY", ""),
    "jimeng_model":     os.getenv("JIMENG_MODEL", "jimeng-3.0"),
    "ideogram_api_key": os.getenv("IDEOGRAM_API_KEY", ""),
    "removebg_api_key": os.getenv("REMOVEBG_API_KEY", ""),
    "default_size":     "portrait",
    "default_style":    "natural",
    "add_footer":       True,
}


def load_config(db: Optional[Session]) -> Dict[str, Any]:
    cfg = dict(DEFAULTS)
    if db is None:
        return cfg
    try:
        from models import SystemSetting
        row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
        if row and row.value:
            cfg.update(json.loads(row.value))
    except Exception as exc:                                          # noqa: BLE001
        print(f"[poster_settings] load failed, using defaults: {exc}")
    return cfg


def save_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    from models import SystemSetting
    current = load_config(db)
    current.update({k: v for k, v in patch.items() if v is not None})
    row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
    if row:
        row.value = json.dumps(current)
    else:
        row = SystemSetting(key=SETTING_KEY, value=json.dumps(current))
        db.add(row)
    db.commit()
    return current


def redact(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    for field in ("openai_api_key", "flux_api_key", "jimeng_api_key",
                  "ideogram_api_key", "removebg_api_key"):
        v = out.get(field, "") or ""
        out[f"{field}_set"] = bool(v)
        out[field] = f"{v[:4]}...{v[-4:]}" if len(v) > 8 else ("****" if v else "")
    return out


# Size dimensions in pixels — keeps aspect per platform
SIZE_PRESETS = {
    "portrait":  (2160, 3840),   # 9:16 — the HBIS standard
    "story":     (1080, 1920),   # Instagram / WeChat story
    "square":    (2048, 2048),   # Xiaohongshu / IG feed
    "landscape": (1920, 1080),   # banner / web hero
    "a3":        (2480, 3508),   # A3 print
}


def get_size(cfg: Dict[str, Any], size: Optional[str] = None) -> tuple[int, int]:
    key = size or cfg.get("default_size", "portrait")
    return SIZE_PRESETS.get(key, SIZE_PRESETS["portrait"])
