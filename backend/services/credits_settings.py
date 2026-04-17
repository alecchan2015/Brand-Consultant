"""
Per-file-type download credit cost configuration.

Stored as a single `credits_config` row in SystemSetting. Admin can tune
any value without redeploy. Used by both task result generation (to stamp
`TaskResult.download_credits`) and by the download endpoint (already reads
from `TaskResult.download_credits`).
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


SETTING_KEY = "credits_config"

# Default costs (admin-tunable). Free items stay 0 unless admin changes them.
DEFAULTS: Dict[str, Any] = {
    "download_credits": {
        # Task result downloads (per file type)
        "md":   0,     # markdown text — free
        "pdf":  10,
        "pptx": 30,    # biggest files, highest cost
        "png":  5,     # brand VI image
        "psd":  20,
        "zip":  15,    # any bundled archive
        # Logo generation outputs
        "logo_png": 3,
        "logo_psd": 10,
        "logo_zip": 15,
        # Poster generation outputs
        "poster_png": 5,
    },
    "task_generation": {
        # Currently tasks are free to create (only downloads cost credits);
        # kept here for future per-agent gating without code changes.
        "per_agent": 0,
    },
    "logo_generation": {
        # Upfront cost deducted when a logo generation job is started.
        "per_generation": 3,
    },
    "poster_generation": {
        # Upfront cost for standalone poster generation
        "per_generation": 5,
    },
}


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def load_config(db: Optional[Session]) -> Dict[str, Any]:
    cfg = json.loads(json.dumps(DEFAULTS))
    if db is None:
        return cfg
    try:
        from models import SystemSetting
        row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
        if row and row.value:
            _deep_merge(cfg, json.loads(row.value))
    except Exception as exc:                                               # noqa: BLE001
        print(f"[credits_settings] load failed: {exc}")
    return cfg


def save_config(db: Session, patch: Dict[str, Any]) -> Dict[str, Any]:
    from models import SystemSetting
    current = load_config(db)
    _deep_merge(current, {k: v for k, v in patch.items() if v is not None})
    row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
    if row:
        row.value = json.dumps(current)
    else:
        row = SystemSetting(key=SETTING_KEY, value=json.dumps(current))
        db.add(row)
    db.commit()
    return current


def get_download_credits(db: Optional[Session], file_type: str) -> int:
    """Return download cost for a given file type (file_type e.g. 'pptx', 'logo_png')."""
    cfg = load_config(db)
    costs = cfg.get("download_credits", {})
    return int(costs.get(file_type, 0))


def get_logo_generation_cost(db: Optional[Session]) -> int:
    cfg = load_config(db)
    return int(cfg.get("logo_generation", {}).get("per_generation", 3))
