"""
SMTP email delivery for OTP codes and system notifications.

Uses stdlib `smtplib` + `email.message.EmailMessage`. The heavy lifting is
wrapped in a background thread so FastAPI's event loop isn't blocked by
network I/O to the SMTP server.
"""
from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from typing import Dict, Optional

from sqlalchemy.orm import Session

from services.auth_settings import load_email_config


def _otp_html(code: str, brand_name: str = "Your Brand Consultant") -> str:
    """Inline HTML template for OTP emails."""
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f5f7fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
    <div style="background:linear-gradient(135deg,#6366f1,#a855f7);padding:32px 24px;text-align:center;">
      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700;letter-spacing:-0.3px;">{brand_name}</h1>
    </div>
    <div style="padding:40px 32px 32px;">
      <h2 style="margin:0 0 12px;font-size:18px;color:#18181b;">您的验证码</h2>
      <p style="margin:0 0 28px;color:#71717a;font-size:14px;line-height:1.6;">请在注册/登录页面输入以下 6 位验证码完成身份验证：</p>
      <div style="background:#f4f4f5;border-radius:12px;padding:24px;text-align:center;letter-spacing:8px;font-size:32px;font-weight:700;color:#6366f1;font-family:'SF Mono',Menlo,Consolas,monospace;">{code}</div>
      <p style="margin:24px 0 0;color:#a1a1aa;font-size:12px;line-height:1.6;">验证码 10 分钟内有效。如非本人操作，请忽略此邮件。</p>
    </div>
    <div style="padding:16px 32px;border-top:1px solid #f4f4f5;text-align:center;color:#a1a1aa;font-size:11px;">
      © {brand_name} · AI-Powered Brand Strategy
    </div>
  </div>
</body>
</html>"""


def _send_sync(cfg: Dict, to_email: str, subject: str, html: str, text: str) -> None:
    """Blocking SMTP send. Call via asyncio.to_thread."""
    host = cfg.get("smtp_host", "")
    port = int(cfg.get("smtp_port", 465))
    user = cfg.get("smtp_user", "")
    password = cfg.get("smtp_password", "")
    from_name = cfg.get("from_name", "Your Brand Consultant")
    from_email = cfg.get("from_email") or user
    use_ssl = cfg.get("use_ssl", True)

    if not host or not user or not password:
        raise RuntimeError("SMTP 未配置 (host/user/password 缺失)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()

    if use_ssl or port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)


async def send_otp_email(db: Session, to_email: str, code: str,
                         brand_name: str = "Your Brand Consultant") -> None:
    """Send a 6-digit OTP code to the given email address."""
    cfg = load_email_config(db)
    html = _otp_html(code, brand_name)
    text = f"您的验证码是 {code}，10 分钟内有效。如非本人操作，请忽略此邮件。"
    subject = f"【{brand_name}】验证码 {code}"
    await asyncio.to_thread(_send_sync, cfg, to_email, subject, html, text)


async def send_test_email(db: Session, to_email: str) -> None:
    """Trigger a test email (used by admin config page to verify SMTP)."""
    cfg = load_email_config(db)
    html = _otp_html("000000", cfg.get("from_name", "Your Brand Consultant"))
    text = "这是一封测试邮件。如果您收到，说明 SMTP 配置正确。"
    subject = "【测试】SMTP 连通性验证"
    await asyncio.to_thread(_send_sync, cfg, to_email, subject, html, text)
