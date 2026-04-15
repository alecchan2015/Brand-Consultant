"""
Thin helper around the `system_settings` table for PPT provider config.

We store ONE row with key='ppt_provider_config' whose value is a JSON blob:

    {
      "provider":           "local" | "gamma" | "presenton",
      "fallback":           "local",
      "gamma_api_key":      "sk-...",
      "gamma_theme_id":     "",
      "presenton_endpoint": "http://localhost:5000"
    }
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

SETTING_KEY = "ppt_provider_config"

# Defaults used when the row doesn't exist yet. Env vars still act as a
# deployment-time override so existing installs keep working.
DEFAULTS: Dict[str, Any] = {
    "provider":           os.getenv("PPT_PROVIDER", "local"),
    "fallback":           os.getenv("PPT_FALLBACK", "local"),
    "gamma_api_key":      os.getenv("GAMMA_API_KEY", ""),
    "gamma_theme_name":   os.getenv("GAMMA_THEME_NAME", ""),
    "gamma_num_cards":    int(os.getenv("GAMMA_NUM_CARDS", "16")),
    "presenton_endpoint": os.getenv("PRESENTON_ENDPOINT", "http://localhost:5000"),
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
    except Exception as exc:                           # noqa: BLE001
        print(f"[ppt_settings] load failed, using defaults: {exc}")
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
    """Return a copy safe to expose to the frontend (masks API keys)."""
    out = dict(cfg)
    k = out.get("gamma_api_key") or ""
    if k:
        out["gamma_api_key"] = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "****"
        out["gamma_api_key_set"] = True
    else:
        out["gamma_api_key"] = ""
        out["gamma_api_key_set"] = False
    return out
