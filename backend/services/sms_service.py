"""
Tencent Cloud SMS — direct HTTPS calls with TC3-HMAC-SHA256 signing.

We avoid pulling in the full `tencentcloud-sdk-python` dependency (~5 MB)
by implementing the signing algorithm inline. The request is always
POST https://sms.tencentcloudapi.com/ with action=SendSms.

Reference: https://cloud.tencent.com/document/product/382/52077
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import httpx
from sqlalchemy.orm import Session

from services.auth_settings import load_sms_config

ENDPOINT = "sms.tencentcloudapi.com"
SERVICE = "sms"
VERSION = "2021-01-11"
ACTION = "SendSms"


def _build_auth_header(
    secret_id: str,
    secret_key: str,
    region: str,
    payload: str,
    timestamp: int,
) -> str:
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    # ── Step 1: canonical request ──────────────────────────────────────────
    http_method = "POST"
    canonical_uri = "/"
    canonical_query_string = ""
    canonical_headers = (
        "content-type:application/json; charset=utf-8\n"
        f"host:{ENDPOINT}\n"
        f"x-tc-action:{ACTION.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{http_method}\n"
        f"{canonical_uri}\n"
        f"{canonical_query_string}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{hashed_payload}"
    )

    # ── Step 2: string to sign ─────────────────────────────────────────────
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    # ── Step 3: signature (HMAC chain over date → service → request) ─────
    secret_date = hmac.new(f"TC3{secret_key}".encode("utf-8"), date.encode("utf-8"), hashlib.sha256).digest()
    secret_service = hmac.new(secret_date, SERVICE.encode("utf-8"), hashlib.sha256).digest()
    secret_signing = hmac.new(secret_service, b"tc3_request", hashlib.sha256).digest()
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    return authorization


async def _send_request(cfg: Dict, phones: Iterable[str], template_params: Iterable[str]) -> Dict:
    secret_id = cfg.get("secret_id", "")
    secret_key = cfg.get("secret_key", "")
    region = cfg.get("region", "ap-guangzhou")
    sdk_app_id = cfg.get("sdk_app_id", "")
    sign_name = cfg.get("sign_name", "")
    template_id = cfg.get("template_id", "")

    if not all([secret_id, secret_key, sdk_app_id, sign_name, template_id]):
        raise RuntimeError("腾讯云 SMS 未配置完整（需 secret_id / secret_key / sdk_app_id / sign_name / template_id）")

    # Normalize phone numbers to +86 prefix if they look like 11-digit CN mobiles
    phone_set = [f"+86{p}" if p.isdigit() and len(p) == 11 else p for p in phones]

    body = {
        "PhoneNumberSet":   phone_set,
        "SmsSdkAppId":      sdk_app_id,
        "SignName":         sign_name,
        "TemplateId":       template_id,
        "TemplateParamSet": list(template_params),
    }
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    ts = int(time.time())
    auth = _build_auth_header(secret_id, secret_key, region, payload, ts)

    headers = {
        "Authorization":   auth,
        "Content-Type":    "application/json; charset=utf-8",
        "Host":            ENDPOINT,
        "X-TC-Action":     ACTION,
        "X-TC-Timestamp":  str(ts),
        "X-TC-Version":    VERSION,
        "X-TC-Region":     region,
    }

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    async with httpx.AsyncClient(timeout=15, proxy=proxy) as client:
        r = await client.post(f"https://{ENDPOINT}/", headers=headers, content=payload.encode("utf-8"))
        data = r.json()

    # Tencent wraps results in {"Response": {...}}
    resp = data.get("Response", {})
    if "Error" in resp:
        raise RuntimeError(f"腾讯云 SMS 失败: {resp['Error'].get('Code')} / {resp['Error'].get('Message')}")
    send_status = resp.get("SendStatusSet", [])
    if send_status and send_status[0].get("Code") != "Ok":
        raise RuntimeError(f"短信发送失败: {send_status[0]}")
    return resp


async def send_otp_sms(db: Session, phone: str, code: str) -> None:
    """Send a 6-digit verification code to a phone number via Tencent Cloud SMS."""
    cfg = load_sms_config(db)
    # Template typically has {1}=code, {2}=validity_minutes — adapt per template
    await _send_request(cfg, [phone], [code])


async def send_test_sms(db: Session, phone: str) -> None:
    """Admin test entry — sends '000000' via the configured template."""
    cfg = load_sms_config(db)
    await _send_request(cfg, [phone], ["000000"])
