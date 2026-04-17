import os
import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from database import Base, engine, get_db
from models import (
    User, LLMConfig, AgentKnowledge, Task, TaskResult, CreditTransaction,
    TokenUsage, LogoGeneration, PosterGeneration, MembershipPlan, PaymentOrder,
)
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_current_admin
)
from schemas import (
    UserRegister, UserLogin, UserOut, TokenResponse,
    LLMConfigCreate, LLMConfigOut,
    KnowledgeCreate, KnowledgeOut,
    TaskCreate, TaskOut, TaskResultOut,
    UserCreditsUpdate, UserStatusUpdate, UserProfilePatch,
    OtpSendReq, EmailRegisterReq, EmailOtpLoginReq,
    PhoneRegisterReq, PhoneOtpLoginReq, GoogleCallbackReq,
    AuthPublicConfig, AuthRegistrationConfigPatch,
    SmsProviderPatch, EmailProviderPatch, GoogleOAuthPatch,
    ProviderTestReq, RegistrationResponse,
    MembershipPlanOut, MembershipPlanCreate, MembershipPlanUpdate,
    MembershipMeOut, AdminTierAdjustReq,
    PaymentOrderCreate, PaymentOrderOut, PaymentOrderCreateResponse,
    PaymentRefundReq, PaymentProvidersPatch, MembershipConfigPatch,
)
from services.agent_service import run_multi_agent, AGENT_META
from services.file_service import (
    generate_markdown_file, generate_pdf_file,
    generate_brand_png, generate_brand_psd, generate_pptx_file,
)
from services.image_service import generate_logo_image

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    Base.metadata.create_all(bind=engine)
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    # Migrate: add new columns to agent_knowledge if missing (SQLite has no ALTER IF NOT EXISTS)
    from sqlalchemy import text, inspect as sa_inspect
    with engine.connect() as conn:
        inspector = sa_inspect(engine)
        if "agent_knowledge" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("agent_knowledge")}
            migrations = {
                "knowledge_type": "VARCHAR(50) DEFAULT 'general'",
                "source": "VARCHAR(100)",
                "source_file": "VARCHAR(300)",
                "quality_score": "INTEGER DEFAULT 7",
                "tags": "VARCHAR(500)",
            }
            for col, dtype in migrations.items():
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE agent_knowledge ADD COLUMN {col} {dtype}"))
            conn.commit()

        # Multi-channel auth migration on existing users table
        if "users" in inspector.get_table_names():
            user_cols = {c["name"] for c in inspector.get_columns("users")}
            user_migrations = {
                "phone":             "VARCHAR(20)",
                "auth_provider":     "VARCHAR(30) DEFAULT 'local'",
                "google_id":         "VARCHAR(100)",
                "google_email":      "VARCHAR(200)",
                "company_name":      "VARCHAR(200)",
                "industry":          "VARCHAR(100)",
                "position":          "VARCHAR(100)",
                "company_size":      "VARCHAR(50)",
                "pending_approval":  "BOOLEAN DEFAULT 0",
                # Membership columns
                "tier":                   "VARCHAR(20) DEFAULT 'regular'",
                "tier_expires_at":        "DATETIME",
                "last_monthly_grant_at":  "DATETIME",
            }
            for col, dtype in user_migrations.items():
                if col not in user_cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {dtype}"))
            conn.commit()

    # Seed default membership plans if the table is empty
    db = next(get_db())
    try:
        if db.query(MembershipPlan).count() == 0:
            DEFAULT_PLANS = [
                # (tier, name, days, price_cents, activation_credits, monthly_credits, features, sort_order)
                ("vip",   "VIP 月度",   30,   9900,  1000,  3000, ["gamma_ppt","hires_logo"], 10),
                ("vip",   "VIP 年度",   365,  99900, 3000,  3000, ["gamma_ppt","hires_logo"], 11),
                ("vvip",  "VVIP 月度",  30,   29900, 3000, 10000, ["gamma_ppt","hires_logo","google_image"], 20),
                ("vvip",  "VVIP 年度",  365, 299900, 10000,10000, ["gamma_ppt","hires_logo","google_image"], 21),
                ("vvvip", "VVVIP 月度", 30,   99900, 10000,30000, ["gamma_ppt","hires_logo","google_image","priority_queue","priority_support"], 30),
                ("vvvip", "VVVIP 年度", 365, 999900, 30000,30000, ["gamma_ppt","hires_logo","google_image","priority_queue","priority_support"], 31),
            ]
            for tier, name, days, price, act_c, mon_c, feats, order in DEFAULT_PLANS:
                db.add(MembershipPlan(
                    tier=tier, name=name, duration_days=days,
                    price_cents=price, price_currency="CNY",
                    activation_credits=act_c, monthly_credits=mon_c,
                    features=feats, is_active=True, sort_order=order,
                ))
            db.commit()
            print(f"[seed] Inserted {len(DEFAULT_PLANS)} default membership plans")
    except Exception as exc:
        print(f"[seed] plan seed error: {exc}")
    finally:
        db.close()

    # Seed default admin (update existing or create new)
    db = next(get_db())
    try:
        existing_admin = db.query(User).filter(
            (User.username == "adminccl") | (User.email == "admin@blankweb.com")
        ).first()
        if existing_admin:
            existing_admin.username = "adminccl"
            existing_admin.password_hash = get_password_hash("ccl@123")
            existing_admin.role = "admin"
            db.commit()
        else:
            admin = User(
                username="adminccl",
                email="admin@blankweb.com",
                password_hash=get_password_hash("ccl@123"),
                role="admin",
                credits=99999,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Your Brand Consultant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Auth Routes
# ─────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For when present."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _finalize_registration(user: User, approval_required: bool):
    """Build the RegistrationResponse — omit token when awaiting approval."""
    if approval_required:
        return {
            "pending_approval": True,
            "message": "注册成功，等待管理员审核后方可登录",
            "user": user,
        }
    token = create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
        "pending_approval": False,
    }


@app.post("/api/auth/register", response_model=RegistrationResponse, tags=["auth"])
def register(
    body: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
):
    """Username + password registration (backward-compatible)."""
    from services.registration_service import create_user
    user, approval_required = create_user(
        db,
        "username_password",
        username=body.username,
        email=body.email,
        password_hash=get_password_hash(body.password),
        ip=_client_ip(request),
    )
    return _finalize_registration(user, approval_required)


@app.post("/api/auth/login", response_model=TokenResponse, tags=["auth"])
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if user.pending_approval:
        raise HTTPException(403, "账号等待管理员审核")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/me", response_model=UserOut, tags=["auth"])
def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.put("/api/auth/me/profile", response_model=UserOut, tags=["auth"])
def update_my_profile(
    body: UserProfilePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Let users self-edit enterprise info + phone."""
    for field in ("company_name", "industry", "position", "company_size"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(current_user, field, val)
    if body.phone is not None and body.phone != current_user.phone:
        # Uniqueness check
        if body.phone:
            existing = db.query(User).filter(User.phone == body.phone, User.id != current_user.id).first()
            if existing:
                raise HTTPException(409, "该手机号已绑定其他账号")
        current_user.phone = body.phone or None
    db.commit()
    db.refresh(current_user)
    return current_user


# ─────────────────────────────────────────────
# Multi-channel auth: OTP send + channel-specific register/login
# ─────────────────────────────────────────────

@app.get("/api/auth/config/public", response_model=AuthPublicConfig, tags=["auth"])
def public_auth_config(db: Session = Depends(get_db)):
    """Which registration methods are currently enabled (for frontend tabs)."""
    from services.auth_settings import public_config
    return public_config(db)


@app.post("/api/auth/otp/send", tags=["auth"])
async def send_otp(
    body: OtpSendReq,
    request: Request,
    db: Session = Depends(get_db),
):
    """Issue and deliver a 6-digit OTP to the given email/phone."""
    from services import otp_service, rate_limit_service
    from services.auth_settings import load_registration_config

    channel = body.channel.lower()
    if channel not in ("email", "phone"):
        raise HTTPException(400, "channel 必须是 email 或 phone")
    target = body.target.strip()
    if not target:
        raise HTTPException(400, "target 不能为空")

    # Method must be enabled
    cfg = load_registration_config(db)
    method_key = "email_otp" if channel == "email" else "phone_sms"
    if not cfg.get("methods", {}).get(method_key, False):
        raise HTTPException(403, "该注册/登录方式当前已关闭")

    rate = cfg.get("rate_limit", {})
    cooldown = int(rate.get("otp_cooldown_seconds", 60))
    hourly = int(rate.get("otp_per_target_per_hour", 5))

    # 1) Cooldown (per-target, 1 code per 60s by default)
    if not rate_limit_service.check_and_increment(
        db, f"otp_cooldown:{channel}:{target}", window_seconds=cooldown, limit=1,
    ):
        raise HTTPException(429, f"请等待 {cooldown} 秒后再重新获取验证码")

    # 2) Hourly limit per target
    if not rate_limit_service.check_and_increment(
        db, f"otp:{channel}:{target}", window_seconds=3600, limit=hourly,
    ):
        raise HTTPException(429, "验证码发送频率过高，请 1 小时后再试")

    # 3) Generate and deliver
    ip = _client_ip(request)
    code = otp_service.create_otp(db, channel, target, purpose=body.purpose or "register", ip=ip)

    try:
        if channel == "email":
            from services.email_service import send_otp_email
            await send_otp_email(db, target, code)
        else:
            from services.sms_service import send_otp_sms
            await send_otp_sms(db, target, code)
    except Exception as exc:                                            # noqa: BLE001
        raise HTTPException(500, f"验证码发送失败: {exc}")

    return {"ok": True, "message": f"验证码已发送至 {target}"}


@app.post("/api/auth/register/email", response_model=RegistrationResponse, tags=["auth"])
def register_email(
    body: EmailRegisterReq,
    request: Request,
    db: Session = Depends(get_db),
):
    from services import otp_service
    from services.registration_service import create_user

    if not otp_service.verify_otp(db, "email", body.email, body.otp, purpose="register"):
        raise HTTPException(400, "验证码无效或已过期")

    pwd_hash = get_password_hash(body.password) if body.password else None
    user, approval_required = create_user(
        db,
        "email_otp",
        username=body.username,
        email=body.email,
        password_hash=pwd_hash,
        profile=body.profile.dict() if body.profile else None,
        ip=_client_ip(request),
    )
    return _finalize_registration(user, approval_required)


@app.post("/api/auth/login/email-otp", response_model=TokenResponse, tags=["auth"])
def login_email_otp(body: EmailOtpLoginReq, db: Session = Depends(get_db)):
    from services import otp_service
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(404, "账号不存在，请先注册")
    if not otp_service.verify_otp(db, "email", body.email, body.otp, purpose="login"):
        # Also accept a register-purpose OTP if user typed wrong tab
        if not otp_service.verify_otp(db, "email", body.email, body.otp, purpose="register"):
            raise HTTPException(400, "验证码无效或已过期")
    if user.pending_approval:
        raise HTTPException(403, "账号等待管理员审核")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/register/phone", response_model=RegistrationResponse, tags=["auth"])
def register_phone(
    body: PhoneRegisterReq,
    request: Request,
    db: Session = Depends(get_db),
):
    from services import otp_service
    from services.registration_service import create_user

    if not otp_service.verify_otp(db, "phone", body.phone, body.otp, purpose="register"):
        raise HTTPException(400, "验证码无效或已过期")

    pwd_hash = get_password_hash(body.password) if body.password else None
    user, approval_required = create_user(
        db,
        "phone_sms",
        username=body.username,
        phone=body.phone,
        password_hash=pwd_hash,
        profile=body.profile.dict() if body.profile else None,
        ip=_client_ip(request),
    )
    return _finalize_registration(user, approval_required)


@app.post("/api/auth/login/phone-otp", response_model=TokenResponse, tags=["auth"])
def login_phone_otp(body: PhoneOtpLoginReq, db: Session = Depends(get_db)):
    from services import otp_service
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user:
        raise HTTPException(404, "账号不存在，请先注册")
    if not otp_service.verify_otp(db, "phone", body.phone, body.otp, purpose="login"):
        if not otp_service.verify_otp(db, "phone", body.phone, body.otp, purpose="register"):
            raise HTTPException(400, "验证码无效或已过期")
    if user.pending_approval:
        raise HTTPException(403, "账号等待管理员审核")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.get("/api/auth/google/url", tags=["auth"])
def google_auth_url(db: Session = Depends(get_db)):
    from services.oauth_google import generate_auth_url
    try:
        url, state = generate_auth_url(db)
    except Exception as exc:                                            # noqa: BLE001
        raise HTTPException(400, str(exc))
    return {"url": url, "state": state}


@app.post("/api/auth/google/callback", response_model=RegistrationResponse, tags=["auth"])
async def google_callback(
    body: GoogleCallbackReq,
    request: Request,
    db: Session = Depends(get_db),
):
    from services import oauth_google
    from services.registration_service import create_user

    if not oauth_google.consume_state(body.state):
        raise HTTPException(400, "无效或已过期的 state")

    try:
        token_data = await oauth_google.exchange_code_for_token(db, body.code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(400, "Google 未返回 access_token")
        info = await oauth_google.fetch_userinfo(access_token)
    except Exception as exc:                                            # noqa: BLE001
        raise HTTPException(400, f"Google 认证失败: {exc}")

    google_id = info.get("sub")
    google_email = info.get("email", "")
    if not google_id:
        raise HTTPException(400, "Google 用户信息不完整")

    # Match existing user: by google_id → by email → else create
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user and google_email:
        user = db.query(User).filter(User.email == google_email).first()
        if user:
            # Link google_id onto existing account
            user.google_id = google_id
            user.google_email = google_email
            db.commit()

    approval_required = False
    if not user:
        user, approval_required = create_user(
            db,
            "google_oauth",
            email=google_email or f"google_{google_id}@placeholder.local",
            google_id=google_id,
            google_email=google_email,
            profile=body.profile.dict() if body.profile else None,
            ip=_client_ip(request),
        )

    if user.pending_approval:
        return {
            "pending_approval": True,
            "message": "账号等待管理员审核",
            "user": user,
        }
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")

    jwt_token = create_access_token({"sub": user.username})
    return {
        "access_token": jwt_token,
        "token_type":   "bearer",
        "user":         user,
        "pending_approval": False,
    }


# ─────────────────────────────────────────────
# Membership (user-facing)
# ─────────────────────────────────────────────

def _days_remaining(expires_at):
    if not expires_at:
        return None
    delta = expires_at - datetime.utcnow()
    return max(0, delta.days + (1 if delta.seconds > 0 else 0))


@app.get("/api/membership/plans", response_model=List[MembershipPlanOut], tags=["membership"])
def list_active_plans(db: Session = Depends(get_db)):
    """Return all active plans (public, sorted)."""
    return (
        db.query(MembershipPlan)
        .filter(MembershipPlan.is_active == True)
        .order_by(MembershipPlan.sort_order.asc(), MembershipPlan.price_cents.asc())
        .all()
    )


@app.get("/api/membership/me", response_model=MembershipMeOut, tags=["membership"])
def my_membership(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from services.payment_settings import load_membership_config
    cfg = load_membership_config(db)
    tier = current_user.tier or "regular"
    features = cfg.get("tier_features", {}).get(tier, [])
    support = cfg.get("support_info", {}).get(tier) if tier != "regular" else None
    return {
        "tier":            tier,
        "tier_label":      cfg.get("tier_labels", {}).get(tier, tier),
        "tier_expires_at": current_user.tier_expires_at,
        "days_remaining":  _days_remaining(current_user.tier_expires_at),
        "features":        features,
        "feature_labels":  cfg.get("feature_labels", {}),
        "support_info":    support,
    }


@app.get("/api/membership/config/public", tags=["membership"])
def public_membership_config(db: Session = Depends(get_db)):
    """Non-sensitive tier/feature labels for frontend display."""
    from services.payment_settings import load_membership_config
    cfg = load_membership_config(db)
    return {
        "tier_labels":    cfg.get("tier_labels", {}),
        "tier_features":  cfg.get("tier_features", {}),
        "feature_labels": cfg.get("feature_labels", {}),
    }


# ─────────────────────────────────────────────
# Payment (user-facing)
# ─────────────────────────────────────────────

@app.post("/api/payment/orders", response_model=PaymentOrderCreateResponse, tags=["payment"])
def create_payment_order(
    body: PaymentOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from services.payment_service import create_order
    res = create_order(db, current_user, body.plan_id, body.channel)
    order = res["order"]
    return {
        "order":       order,
        "payment_url": res.get("payment_url"),
        "qr_code_url": res.get("qr_code_url"),
        "message":     res.get("message", ""),
    }


@app.get("/api/payment/orders", response_model=List[PaymentOrderOut], tags=["payment"])
def list_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(PaymentOrder)
        .filter(PaymentOrder.user_id == current_user.id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(100)
        .all()
    )


@app.get("/api/payment/orders/{order_no}", response_model=PaymentOrderOut, tags=["payment"])
def get_my_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(PaymentOrder).filter(
        PaymentOrder.order_no == order_no,
        PaymentOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    return order


@app.post("/api/payment/orders/{order_no}/cancel", response_model=PaymentOrderOut, tags=["payment"])
def cancel_my_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from services.payment_service import cancel
    return cancel(db, current_user, order_no)


@app.post("/api/payment/orders/{order_no}/mark-paying", response_model=PaymentOrderOut, tags=["payment"])
def mark_my_order_paying(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """User clicked 'I paid' (manual channel). Order moves to awaiting_confirm."""
    from services.payment_service import mark_paying
    return mark_paying(db, current_user, order_no)


@app.get("/api/payment/channels/public", tags=["payment"])
def public_payment_channels(db: Session = Depends(get_db)):
    """List of available payment channels for the frontend."""
    from services.payment_settings import load_payment_config
    from services import payment_providers
    cfg = load_payment_config(db)
    enabled = payment_providers.available_channels(cfg)
    return {
        "enabled":      enabled,
        "descriptions": {ch: (cfg.get(ch, {}).get("description") or "") for ch in ("stripe", "alipay", "wechat", "manual")},
    }


# ─────────────────────────────────────────────
# Task Routes
# ─────────────────────────────────────────────

@app.post("/api/tasks", response_model=TaskOut, tags=["tasks"])
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_agents = {"strategy", "brand", "logo_design", "poster_design", "operations"}
    agents = [a for a in body.agents_selected if a in valid_agents]
    if not agents:
        raise HTTPException(400, "请至少选择一个Agent专家")
    task = Task(
        user_id=current_user.id,
        query=body.query,
        agents_selected=agents,
        brand_name=body.brand_name,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@app.get("/api/tasks", response_model=List[TaskOut], tags=["tasks"])
def list_tasks(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return tasks


@app.get("/api/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "无权访问")

    # Only return the LATEST generation run per agent_type.
    # Each run starts with a content record (file_path IS NULL). Find the latest
    # such record per agent, then include all result IDs >= that anchor.
    latest_results = []
    for agent_type in task.agents_selected:
        # Latest content record for this agent
        anchor = (
            db.query(TaskResult)
            .filter(
                TaskResult.task_id == task_id,
                TaskResult.agent_type == agent_type,
                TaskResult.file_path == None,
                TaskResult.content != None,
            )
            .order_by(TaskResult.id.desc())
            .first()
        )
        if anchor:
            # All records from this run: same agent_type, id >= anchor
            run_results = (
                db.query(TaskResult)
                .filter(
                    TaskResult.task_id == task_id,
                    TaskResult.agent_type == agent_type,
                    TaskResult.id >= anchor.id,
                )
                .order_by(TaskResult.id)
                .all()
            )
            latest_results.extend(run_results)

    # Override the ORM relationship with only the filtered results
    task.results = latest_results
    return task


@app.get("/api/tasks/{task_id}/stream", tags=["tasks"])
async def stream_task(
    task_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """SSE endpoint for streaming task processing"""
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(401, "Unauthorized")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.user_id != user.id:
        raise HTTPException(404, "Task not found")

    # Auto-fix: pending task with saved results means a previous run completed but
    # status was never updated (e.g. client disconnected before all_done). Mark completed.
    if task.status == "pending":
        has_results = db.query(TaskResult).filter(TaskResult.task_id == task.id).first()
        if has_results:
            task.status = "completed"
            db.commit()

    if task.status in ("completed", "failed", "processing"):
        async def replay():
            yield {"data": json.dumps({"type": "already_done", "status": task.status})}
        return EventSourceResponse(replay())

    async def event_generator():
        agent_contents = {}
        task.status = "processing"
        db.commit()

        try:
            async for event in run_multi_agent(
                agents=task.agents_selected,
                query=task.query,
                brand_name=task.brand_name or "",
                db=db,
                user_id=user.id,
                task_id=task.id,
            ):
                etype = event.get("type")
                if etype == "agent_start":
                    yield {"data": json.dumps(event)}

                elif etype == "chunk":
                    yield {"data": json.dumps({
                        "type": "chunk",
                        "agent": event["agent"],
                        "content": event["content"],
                    })}

                elif etype == "agent_done":
                    agent_type = event["agent"]
                    full_content = event["full_content"]
                    agent_contents[agent_type] = full_content

                    # Pull download-cost config once per agent_done event
                    from services.credits_settings import get_download_credits

                    # Save TaskResult (text record, no file)
                    tr = TaskResult(
                        task_id=task.id,
                        agent_type=agent_type,
                        content=full_content,
                        download_credits=0,
                    )
                    db.add(tr)
                    db.commit()
                    db.refresh(tr)

                    # Generate files
                    files_generated = []
                    try:
                        md_path, md_name = generate_markdown_file(
                            task.id, agent_type, task.brand_name or "品牌", full_content
                        )
                        md_result = TaskResult(
                            task_id=task.id,
                            agent_type=agent_type,
                            content=None,
                            file_path=md_path,
                            file_type="md",
                            file_name=md_name,
                            download_credits=get_download_credits(db, "md"),
                        )
                        db.add(md_result)
                        db.commit()
                        db.refresh(md_result)
                        files_generated.append({"id": md_result.id, "type": "md", "name": md_name})
                    except Exception as e:
                        print(f"MD gen error: {e}")

                    try:
                        pdf_path, pdf_name = generate_pdf_file(
                            task.id, agent_type, task.brand_name or "品牌", full_content
                        )
                        pdf_result = TaskResult(
                            task_id=task.id,
                            agent_type=agent_type,
                            content=None,
                            file_path=pdf_path,
                            file_type="pdf",
                            file_name=pdf_name,
                            download_credits=get_download_credits(db, "pdf"),
                        )
                        db.add(pdf_result)
                        db.commit()
                        db.refresh(pdf_result)
                        files_generated.append({"id": pdf_result.id, "type": "pdf", "name": pdf_name})
                    except Exception as e:
                        print(f"PDF gen error: {e}")

                    # PPTX: for all agent types (AI-powered, async)
                    try:
                        pptx_path, pptx_name = await generate_pptx_file(
                            task.id, agent_type, task.brand_name or "品牌", full_content, db=db, user=user,
                        )
                        pptx_result = TaskResult(
                            task_id=task.id,
                            agent_type=agent_type,
                            content=None,
                            file_path=pptx_path,
                            file_type="pptx",
                            file_name=pptx_name,
                            download_credits=get_download_credits(db, "pptx"),
                        )
                        db.add(pptx_result)
                        db.commit()
                        db.refresh(pptx_result)
                        files_generated.append({"id": pptx_result.id, "type": "pptx", "name": pptx_name})
                    except Exception as e:
                        print(f"PPTX gen error: {e}")

                    if agent_type == "brand":
                        # Try AI logo generation (non-blocking, falls back to placeholder)
                        ai_logo = None
                        try:
                            ai_logo = await generate_logo_image(
                                task.brand_name or "品牌", full_content, db
                            )
                        except Exception as e:
                            print(f"Logo generation skipped: {e}")

                        try:
                            png_path, png_name = generate_brand_png(
                                task.id, task.brand_name or "品牌", full_content,
                                logo_image=ai_logo,
                            )
                            png_result = TaskResult(
                                task_id=task.id,
                                agent_type=agent_type,
                                content=None,
                                file_path=png_path,
                                file_type="png",
                                file_name=png_name,
                                download_credits=get_download_credits(db, "png"),
                            )
                            db.add(png_result)
                            db.commit()
                            db.refresh(png_result)
                            files_generated.append({"id": png_result.id, "type": "png", "name": png_name})
                        except Exception as e:
                            print(f"PNG gen error: {e}")

                        try:
                            psd_path, psd_name = generate_brand_psd(
                                task.id, task.brand_name or "品牌", full_content,
                                logo_image=ai_logo,
                            )
                            psd_result = TaskResult(
                                task_id=task.id,
                                agent_type=agent_type,
                                content=None,
                                file_path=psd_path,
                                file_type="psd",
                                file_name=psd_name,
                                download_credits=get_download_credits(db, "psd"),
                            )
                            db.add(psd_result)
                            db.commit()
                            db.refresh(psd_result)
                            files_generated.append({"id": psd_result.id, "type": "psd", "name": psd_name})
                        except Exception as e:
                            print(f"PSD gen error: {e}")

                    yield {"data": json.dumps({
                        "type": "agent_done",
                        "agent": agent_type,
                        "result_id": tr.id,
                        "files": files_generated,
                    })}

            # ── Logo Design Agent (runs after LLM agents) ─────────────
            if "logo_design" in (task.agents_selected or []):
                yield {"data": json.dumps({
                    "type": "agent_start",
                    "agent": "logo_design",
                    "name": "Logo设计专家",
                })}
                yield {"data": json.dumps({
                    "type": "chunk",
                    "agent": "logo_design",
                    "content": "🎨 正在为您的品牌智能生成 Logo...\n\n",
                })}

                logo_files = []
                logo_content_parts = []
                try:
                    from services.logo_providers import generate_via_providers, build_logo_prompt
                    from services.logo_settings import load_config as load_logo_config
                    from services.credits_settings import get_download_credits

                    logo_cfg = load_logo_config(db)
                    brand_name = task.brand_name or "品牌"

                    # Use brand agent output for style hints if available
                    brand_content = agent_contents.get("brand", "")
                    # Detect style from content
                    style = logo_cfg.get("style", "modern")
                    primary_color = ""
                    import re as _re
                    hex_matches = _re.findall(r'#([A-Fa-f0-9]{6})', brand_content)
                    if hex_matches:
                        primary_color = f"#{hex_matches[0]}"

                    # Detect industry from query
                    industry = ""
                    for kw, ind in [("家具", "家居家具"), ("美妆", "美妆护肤"),
                                    ("科技", "科技智能"), ("食品", "食品饮料"),
                                    ("服装", "服装时尚"), ("教育", "教育培训")]:
                        if kw in (task.query or ""):
                            industry = ind
                            break

                    prompt = build_logo_prompt(
                        brand_name=brand_name,
                        style=style,
                        primary_color=primary_color,
                        include_text=logo_cfg.get("include_text", True),
                        industry=industry,
                    )

                    yield {"data": json.dumps({
                        "type": "chunk",
                        "agent": "logo_design",
                        "content": f"**提示词**: {prompt}\n\n⏳ 正在调用 AI 生成引擎...\n\n",
                    })}

                    result, provider_name = await generate_via_providers(
                        brand_name=brand_name,
                        prompt=prompt,
                        style=style,
                        include_text=logo_cfg.get("include_text", True),
                        variant_count=min(3, logo_cfg.get("variant_count", 3)),
                        primary_color=primary_color,
                        db=db,
                    )

                    if result.success and result.variants:
                        logo_content_parts.append(
                            f"✅ Logo 生成成功！\n\n"
                            f"- **生成引擎**: {provider_name}\n"
                            f"- **变体数量**: {len(result.variants)}\n"
                            f"- **风格**: {style}\n\n"
                        )
                        yield {"data": json.dumps({
                            "type": "chunk",
                            "agent": "logo_design",
                            "content": logo_content_parts[-1],
                        })}

                        # Download and save logo variants
                        import httpx
                        from services.file_service import ensure_upload_dir, sanitize_filename
                        ensure_upload_dir()
                        safe_brand = sanitize_filename(brand_name)
                        ts = datetime.now().strftime("%Y%m%d%H%M%S")

                        for v in result.variants:
                            png_url = v.get("png_url", "")
                            if not png_url:
                                continue
                            try:
                                async with httpx.AsyncClient(timeout=60) as hc:
                                    resp = await hc.get(png_url)
                                    resp.raise_for_status()
                                    fname = f"{safe_brand}_logo_v{v['index']+1}_{ts}.png"
                                    fpath = os.path.join(UPLOAD_DIR, fname)
                                    with open(fpath, "wb") as f:
                                        f.write(resp.content)

                                    logo_result = TaskResult(
                                        task_id=task.id,
                                        agent_type="logo_design",
                                        content=None,
                                        file_path=fpath,
                                        file_type="png",
                                        file_name=fname,
                                        download_credits=get_download_credits(db, "logo_png"),
                                    )
                                    db.add(logo_result)
                                    db.commit()
                                    db.refresh(logo_result)
                                    logo_files.append({
                                        "id": logo_result.id,
                                        "type": "png",
                                        "name": fname,
                                    })
                                    logo_content_parts.append(
                                        f"- 方案 {v['index']+1}: `{fname}` ✅\n"
                                    )
                                    yield {"data": json.dumps({
                                        "type": "chunk",
                                        "agent": "logo_design",
                                        "content": logo_content_parts[-1],
                                    })}
                            except Exception as e:
                                print(f"[Logo] variant {v['index']} download error: {e}")
                                logo_content_parts.append(f"- 方案 {v['index']+1}: 下载失败 ❌\n")
                                yield {"data": json.dumps({
                                    "type": "chunk",
                                    "agent": "logo_design",
                                    "content": logo_content_parts[-1],
                                })}

                        # Also generate PSD with first logo
                        if logo_files:
                            try:
                                first_path = os.path.join(
                                    UPLOAD_DIR,
                                    logo_files[0]["name"],
                                )
                                from PIL import Image as PILImage
                                from psd_tools import PSDImage
                                logo_img = PILImage.open(first_path).convert("RGBA")
                                W, H = 1024, 1024
                                psd = PSDImage.new("RGBA", (W, H))
                                white_bg = PILImage.new("RGBA", (W, H), (255, 255, 255, 255))
                                psd.append(psd.create_pixel_layer(white_bg, name="Background White"))
                                logo_resized = logo_img.resize((W, H), PILImage.LANCZOS)
                                psd.append(psd.create_pixel_layer(logo_resized, name="Logo"))
                                black_bg = PILImage.new("RGBA", (W, H), (0, 0, 0, 255))
                                bl = psd.create_pixel_layer(black_bg, name="Background Black")
                                bl.visible = False
                                psd.append(bl)

                                psd_fname = f"{safe_brand}_logo_{ts}.psd"
                                psd_fpath = os.path.join(UPLOAD_DIR, psd_fname)
                                psd.save(psd_fpath)

                                psd_result = TaskResult(
                                    task_id=task.id,
                                    agent_type="logo_design",
                                    content=None,
                                    file_path=psd_fpath,
                                    file_type="psd",
                                    file_name=psd_fname,
                                    download_credits=get_download_credits(db, "logo_psd"),
                                )
                                db.add(psd_result)
                                db.commit()
                                db.refresh(psd_result)
                                logo_files.append({
                                    "id": psd_result.id,
                                    "type": "psd",
                                    "name": psd_fname,
                                })
                                logo_content_parts.append(f"\n📎 PSD 分层文件: `{psd_fname}` ✅\n")
                                yield {"data": json.dumps({
                                    "type": "chunk",
                                    "agent": "logo_design",
                                    "content": logo_content_parts[-1],
                                })}
                            except Exception as e:
                                print(f"[Logo] PSD gen error: {e}")
                    else:
                        err_msg = f"❌ Logo 生成失败: {result.error}\n"
                        logo_content_parts.append(err_msg)
                        yield {"data": json.dumps({
                            "type": "chunk",
                            "agent": "logo_design",
                            "content": err_msg,
                        })}

                except Exception as e:
                    err_msg = f"❌ Logo 生成出错: {str(e)}\n"
                    logo_content_parts.append(err_msg)
                    yield {"data": json.dumps({
                        "type": "chunk",
                        "agent": "logo_design",
                        "content": err_msg,
                    })}
                    print(f"[Logo] Task agent error: {e}")

                # Save content result
                full_logo_content = "".join(logo_content_parts)
                logo_tr = TaskResult(
                    task_id=task.id,
                    agent_type="logo_design",
                    content=full_logo_content,
                    download_credits=0,
                )
                db.add(logo_tr)
                db.commit()
                db.refresh(logo_tr)

                yield {"data": json.dumps({
                    "type": "agent_done",
                    "agent": "logo_design",
                    "result_id": logo_tr.id,
                    "files": logo_files,
                })}

            # ── Poster Design Agent (runs after LLM + logo agents) ────
            if "poster_design" in (task.agents_selected or []):
                yield {"data": json.dumps({
                    "type": "agent_start",
                    "agent": "poster_design",
                    "name": "海报设计专家",
                })}
                yield {"data": json.dumps({
                    "type": "chunk",
                    "agent": "poster_design",
                    "content": "🖼️ 正在为您的品牌生成商业海报...\n\n",
                })}

                poster_files = []
                poster_parts = []
                try:
                    from services.poster_providers import generate_via_providers as run_poster
                    from services.poster_settings import load_config as load_poster_cfg, get_size
                    from services.poster_service import compose_poster, _download_image, _image_from_b64
                    from services.credits_settings import get_download_credits
                    from services.file_service import sanitize_filename, ensure_upload_dir

                    ensure_upload_dir()
                    poster_cfg = load_poster_cfg(db)
                    brand_name = task.brand_name or "品牌"

                    # Infer event keyword from the query — simple heuristic
                    event_keyword = ""
                    for kw in ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
                               "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
                               "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
                               "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
                               "春节", "元宵", "端午", "中秋", "重阳", "七夕"]:
                        if kw in (task.query or ""):
                            event_keyword = kw
                            break
                    if not event_keyword:
                        event_keyword = "新品"  # generic fallback

                    # Reuse strategy/brand output for color hint
                    brand_content = agent_contents.get("brand", "")
                    primary_color = ""
                    import re as _re
                    hex_match = _re.findall(r'#([A-Fa-f0-9]{6})', brand_content)
                    if hex_match:
                        primary_color = f"#{hex_match[0]}"

                    industry = ""
                    for kw, ind in [("家具", "家居家具"), ("美妆", "美妆护肤"),
                                    ("科技", "科技智能"), ("食品", "食品饮料"),
                                    ("服装", "服装时尚")]:
                        if kw in (task.query or ""):
                            industry = ind
                            break

                    style = poster_cfg.get("default_style", "natural")
                    target_size = get_size(poster_cfg, "portrait")

                    yield {"data": json.dumps({
                        "type": "chunk",
                        "agent": "poster_design",
                        "content": f"**主题**: {event_keyword}\n**风格**: {style}\n**尺寸**: {target_size[0]}×{target_size[1]} (9:16)\n\n⏳ 正在生成海报背景...\n\n",
                    })}

                    result, provider_name = await run_poster(
                        brand_name=brand_name,
                        event_keyword=event_keyword,
                        style=style,
                        variant_count=1,
                        size=target_size,
                        industry=industry,
                        primary_color=primary_color,
                        db=db,
                    )

                    if result.success and result.variants:
                        poster_parts.append(
                            f"✅ 海报背景生成完成！\n\n"
                            f"- **生成引擎**: {provider_name}\n\n"
                            f"⏳ 正在合成品牌图层...\n\n"
                        )
                        yield {"data": json.dumps({"type": "chunk", "agent": "poster_design", "content": poster_parts[-1]})}

                        from datetime import datetime as _dt
                        ts = _dt.now().strftime("%Y%m%d%H%M%S")
                        safe_brand = sanitize_filename(brand_name)
                        for v in result.variants:
                            bg = None
                            if v.get("png_url"):
                                bg = await _download_image(v["png_url"])
                            elif v.get("png_b64"):
                                bg = _image_from_b64(v["png_b64"])
                            if bg is None:
                                continue
                            poster_img = compose_poster(
                                background=bg, target_size=target_size,
                                brand_name=brand_name,
                                headline=event_keyword,
                                subline=f"{brand_name} · 节气呈现",
                                event_date=_dt.now().strftime("%Y.%m.%d"),
                                logo=None,
                                primary_color=primary_color or None,
                                add_footer=poster_cfg.get("add_footer", True),
                            )
                            fname = f"{safe_brand}_poster_{event_keyword}_{ts}.png"
                            fpath = os.path.join(UPLOAD_DIR, fname)
                            poster_img.save(fpath, format="PNG", optimize=True)

                            pr = TaskResult(
                                task_id=task.id,
                                agent_type="poster_design",
                                content=None,
                                file_path=fpath,
                                file_type="png",
                                file_name=fname,
                                download_credits=get_download_credits(db, "poster_png"),
                            )
                            db.add(pr)
                            db.commit()
                            db.refresh(pr)
                            poster_files.append({"id": pr.id, "type": "png", "name": fname})
                            poster_parts.append(f"- 海报: `{fname}` ✅\n")
                            yield {"data": json.dumps({"type": "chunk", "agent": "poster_design", "content": poster_parts[-1]})}
                    else:
                        err = f"❌ 海报生成失败: {result.error}\n"
                        poster_parts.append(err)
                        yield {"data": json.dumps({"type": "chunk", "agent": "poster_design", "content": err})}

                except Exception as e:
                    err = f"❌ 海报生成出错: {e}\n"
                    poster_parts.append(err)
                    yield {"data": json.dumps({"type": "chunk", "agent": "poster_design", "content": err})}
                    print(f"[Poster] Task agent error: {e}")

                # Save a summary TaskResult
                full_poster_content = "".join(poster_parts)
                poster_tr = TaskResult(
                    task_id=task.id,
                    agent_type="poster_design",
                    content=full_poster_content,
                    download_credits=0,
                )
                db.add(poster_tr)
                db.commit()
                db.refresh(poster_tr)

                yield {"data": json.dumps({
                    "type": "agent_done",
                    "agent": "poster_design",
                    "result_id": poster_tr.id,
                    "files": poster_files,
                })}

            task.status = "completed"
            task.completed_at = datetime.utcnow()
            db.commit()
            yield {"data": json.dumps({"type": "all_done"})}

        except Exception as e:
            task.status = "failed"
            db.commit()
            yield {"data": json.dumps({"type": "error", "message": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/api/tasks/{task_id}/regenerate", tags=["tasks"])
def regenerate_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset a completed/failed task so it can be streamed again with fresh AI output."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "无权操作")

    # Remove generated files from disk
    results = db.query(TaskResult).filter(TaskResult.task_id == task_id).all()
    for r in results:
        if r.file_path and os.path.exists(r.file_path):
            try:
                os.remove(r.file_path)
            except Exception:
                pass

    # Delete all result records for this task
    db.query(TaskResult).filter(TaskResult.task_id == task_id).delete()

    # Reset task status
    task.status = "pending"
    task.completed_at = None
    db.commit()
    db.refresh(task)
    return {"message": "任务已重置，可重新生成"}


@app.delete("/api/tasks/{task_id}", tags=["tasks"])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "无权删除")
    db.delete(task)
    db.commit()
    return {"message": "已删除"}


# ─────────────────────────────────────────────
# File Download Routes
# ─────────────────────────────────────────────

@app.get("/api/files/{result_id}/download", tags=["files"])
def download_file(
    result_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """
    File download endpoint.

    Supports two authentication methods:
      1. Authorization header: `Bearer <token>` (standard API calls)
      2. Query parameter: `?token=<token>` (browser-native downloads via <a href>)

    Browser-native downloads are preferred for large files (>10MB) because:
      - No axios/fetch timeout limit
      - Native progress bar in browser
      - Resumable (with Range header)
      - Doesn't block tab / consume memory
    """
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM

    # Resolve token from query param OR Authorization header
    jwt_token = token
    if not jwt_token and request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header[7:]

    if not jwt_token:
        raise HTTPException(401, "未提供身份凭证")

    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        current_user = db.query(User).filter(User.username == username).first()
        if not current_user or not current_user.is_active:
            raise HTTPException(401, "身份验证失败")
    except JWTError:
        raise HTTPException(401, "身份验证失败")

    result = db.query(TaskResult).filter(TaskResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "文件不存在")

    task = db.query(Task).filter(Task.id == result.task_id).first()
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "无权下载")

    if not result.file_path:
        raise HTTPException(400, "此记录无文件")

    credits_needed = result.download_credits
    if current_user.credits < credits_needed:
        raise HTTPException(402, f"积分不足，需要 {credits_needed} 积分，当前 {current_user.credits} 积分")

    # Deduct credits (only on first download to avoid double-billing on browser
    # retry). Simple approach: skip deduction if an earlier transaction exists
    # for this task_result_id by this user.
    prior = db.query(CreditTransaction).filter(
        CreditTransaction.user_id == current_user.id,
        CreditTransaction.task_result_id == result.id,
    ).first()
    if not prior and credits_needed > 0:
        current_user.credits -= credits_needed
        tx = CreditTransaction(
            user_id=current_user.id,
            amount=-credits_needed,
            reason=f"下载文件 {result.file_name}",
            task_result_id=result.id,
        )
        db.add(tx)
        db.commit()

    file_path = result.file_path
    file_name = result.file_name

    if not os.path.exists(file_path):
        raise HTTPException(404, "文件已被清理")

    # Serve original file directly. PPTX/PNG/PDF are already compressed formats;
    # re-zipping adds CPU time and barely reduces size (~10-15%).
    media_types = {
        "md":   "text/markdown",
        "pdf":  "application/pdf",
        "png":  "image/png",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "psd":  "image/vnd.adobe.photoshop",
        "zip":  "application/zip",
    }
    media_type = media_types.get(result.file_type, "application/octet-stream")
    return FileResponse(
        path=file_path,
        filename=file_name,
        media_type=media_type,
    )


@app.get("/api/files/{result_id}/preview", tags=["files"])
def preview_file(
    result_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview MD content without credits"""
    result = db.query(TaskResult).filter(TaskResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "文件不存在")
    task = db.query(Task).filter(Task.id == result.task_id).first()
    if task.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "无权预览")
    return {"content": result.content, "file_type": result.file_type}


# ─────────────────────────────────────────────
# Admin Routes
# ─────────────────────────────────────────────

@app.get("/api/admin/stats", tags=["admin"])
def admin_stats(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from sqlalchemy import func
    token_stats = db.query(
        func.sum(TokenUsage.total_tokens),
        func.count(TokenUsage.id),
    ).first()
    return {
        "total_users": db.query(User).filter(User.role == "user").count(),
        "total_tasks": db.query(Task).count(),
        "completed_tasks": db.query(Task).filter(Task.status == "completed").count(),
        "total_llm_configs": db.query(LLMConfig).filter(LLMConfig.is_active == True).count(),
        "total_knowledge": db.query(AgentKnowledge).filter(AgentKnowledge.is_active == True).count(),
        "total_tokens": token_stats[0] or 0,
        "total_llm_calls": token_stats[1] or 0,
    }


# LLM Config
@app.post("/api/admin/llm-configs", response_model=LLMConfigOut, tags=["admin"])
def create_llm_config(
    body: LLMConfigCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    config = LLMConfig(**body.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@app.get("/api/admin/llm-configs", response_model=List[LLMConfigOut], tags=["admin"])
def list_llm_configs(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(LLMConfig).order_by(LLMConfig.created_at.desc()).all()


@app.put("/api/admin/llm-configs/{config_id}", response_model=LLMConfigOut, tags=["admin"])
def update_llm_config(
    config_id: int,
    body: LLMConfigCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    for k, v in body.model_dump().items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@app.delete("/api/admin/llm-configs/{config_id}", tags=["admin"])
def delete_llm_config(
    config_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    config = db.query(LLMConfig).filter(LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    db.delete(config)
    db.commit()
    return {"message": "已删除"}


# ── PPT Provider configuration ───────────────────────────────────────────────
@app.get("/api/admin/ppt-provider", tags=["admin"])
def get_ppt_provider_config(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.ppt_settings import load_config, redact
    from services.ppt_providers import list_providers
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.put("/api/admin/ppt-provider", tags=["admin"])
def update_ppt_provider_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.ppt_settings import save_config, load_config, redact
    from services.ppt_providers import list_providers
    # Don't clobber the existing key when the frontend sends back a mask
    patch = dict(body or {})
    existing = load_config(db)
    k = patch.get("gamma_api_key")
    if k is not None and ("..." in k or k == ""):
        patch.pop("gamma_api_key", None)       # preserve existing
    # Validate provider names
    allowed = {"local", "gamma", "presenton"}
    if "provider" in patch and patch["provider"] not in allowed:
        raise HTTPException(400, f"Invalid provider, must be one of {allowed}")
    if "fallback" in patch and patch["fallback"] not in allowed:
        raise HTTPException(400, f"Invalid fallback, must be one of {allowed}")
    save_config(db, patch)
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.post("/api/admin/ppt-provider/test", tags=["admin"])
async def test_ppt_provider(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.ppt_providers import test_provider
    name = (body or {}).get("provider", "local")
    return await test_provider(name, db=db)


# Knowledge Base
@app.post("/api/admin/knowledge", response_model=KnowledgeOut, tags=["admin"])
def create_knowledge(
    body: KnowledgeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    item = AgentKnowledge(**body.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/admin/knowledge", response_model=List[KnowledgeOut], tags=["admin"])
def list_knowledge(
    agent_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(AgentKnowledge)
    if agent_type:
        q = q.filter(AgentKnowledge.agent_type == agent_type)
    return q.order_by(AgentKnowledge.created_at.desc()).all()


@app.put("/api/admin/knowledge/{item_id}", response_model=KnowledgeOut, tags=["admin"])
def update_knowledge(
    item_id: int,
    body: KnowledgeCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    item = db.query(AgentKnowledge).filter(AgentKnowledge.id == item_id).first()
    if not item:
        raise HTTPException(404, "知识条目不存在")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/api/admin/knowledge/{item_id}", tags=["admin"])
def delete_knowledge(
    item_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    item = db.query(AgentKnowledge).filter(AgentKnowledge.id == item_id).first()
    if not item:
        raise HTTPException(404, "知识条目不存在")
    db.delete(item)
    db.commit()
    return {"message": "已删除"}


@app.post("/api/admin/knowledge/upload", tags=["admin"])
async def upload_knowledge_document(
    file: UploadFile = File(...),
    agent_type: str = Query("strategy"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Upload a document for AI-powered knowledge extraction."""
    from services.kb_upload_service import process_uploaded_file

    allowed_ext = {".pdf", ".docx", ".txt", ".md", ".zip"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"不支持的文件类型: {ext}，支持: {', '.join(allowed_ext)}")

    # Save uploaded file
    upload_path = os.path.join(UPLOAD_DIR, f"kb_{int(datetime.utcnow().timestamp())}_{file.filename}")
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        result = await process_uploaded_file(
            file_path=upload_path,
            file_name=file.filename,
            agent_type=agent_type,
            db=db,
            user_id=current_user.id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, f"处理文件失败: {str(e)}")


@app.post("/api/admin/knowledge/import-seed", tags=["admin"])
def import_seed(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Import built-in seed knowledge base (comprehensive HBIS + basic)."""
    from services.seed_knowledge import SEED_KNOWLEDGE

    # Check if comprehensive seeds already imported
    existing_titles = {
        row[0]
        for row in db.query(AgentKnowledge.title).filter(
            AgentKnowledge.is_active == True
        ).all()
    }

    count = 0
    for entry in SEED_KNOWLEDGE:
        if entry["title"] in existing_titles:
            continue
        item = AgentKnowledge(
            agent_type=entry["agent_type"],
            title=entry["title"],
            content=entry["content"],
            created_by=current_user.id,
            knowledge_type=entry.get("knowledge_type", "framework"),
            source="seed",
            quality_score=9,
            tags=entry.get("tags", ""),
        )
        db.add(item)
        count += 1

    if count > 0:
        db.commit()

    if count == 0:
        return {"message": "种子知识库已导入过，跳过", "entries_created": 0}
    return {"message": f"成功导入 {count} 条种子知识", "entries_created": count}


@app.get("/api/admin/knowledge/stats", tags=["admin"])
def knowledge_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Knowledge base statistics."""
    from sqlalchemy import func

    total = db.query(AgentKnowledge).filter(AgentKnowledge.is_active == True).count()

    by_agent = dict(
        db.query(AgentKnowledge.agent_type, func.count(AgentKnowledge.id))
        .filter(AgentKnowledge.is_active == True)
        .group_by(AgentKnowledge.agent_type)
        .all()
    )

    by_type = dict(
        db.query(AgentKnowledge.knowledge_type, func.count(AgentKnowledge.id))
        .filter(AgentKnowledge.is_active == True)
        .group_by(AgentKnowledge.knowledge_type)
        .all()
    )

    by_source = dict(
        db.query(AgentKnowledge.source, func.count(AgentKnowledge.id))
        .filter(AgentKnowledge.is_active == True)
        .group_by(AgentKnowledge.source)
        .all()
    )

    return {
        "total": total,
        "by_agent": by_agent,
        "by_type": by_type,
        "by_source": by_source,
    }


# User Management
@app.get("/api/admin/users", response_model=List[UserOut], tags=["admin"])
def list_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()


@app.put("/api/admin/users/{user_id}/credits", response_model=UserOut, tags=["admin"])
def update_user_credits(
    user_id: int,
    body: UserCreditsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    delta = body.credits - user.credits
    user.credits = body.credits
    tx = CreditTransaction(
        user_id=user.id,
        amount=delta,
        reason=body.reason or "管理员调整",
    )
    db.add(tx)
    db.commit()
    db.refresh(user)
    return user


@app.put("/api/admin/users/{user_id}/status", response_model=UserOut, tags=["admin"])
def update_user_status(
    user_id: int,
    body: UserStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────
# Admin: User approval + profile management
# ─────────────────────────────────────────────

@app.get("/api/admin/users/pending", response_model=List[UserOut], tags=["admin"])
def list_pending_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return (
        db.query(User)
        .filter(User.pending_approval == True)
        .order_by(User.created_at.desc())
        .all()
    )


@app.post("/api/admin/users/{user_id}/approve", response_model=UserOut, tags=["admin"])
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.pending_approval = False
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/admin/users/{user_id}/reject", tags=["admin"])
def reject_user(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    # Soft-delete by deactivating
    user.is_active = False
    user.pending_approval = False
    db.commit()
    return {"message": "已拒绝该用户"}


@app.get("/api/admin/users/{user_id}", response_model=UserOut, tags=["admin"])
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    return user


@app.put("/api/admin/users/{user_id}/profile", response_model=UserOut, tags=["admin"])
def admin_update_user_profile(
    user_id: int,
    body: UserProfilePatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    for field in ("company_name", "industry", "position", "company_size"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(user, field, val)
    if body.phone is not None and body.phone != user.phone:
        if body.phone:
            dup = db.query(User).filter(User.phone == body.phone, User.id != user_id).first()
            if dup:
                raise HTTPException(409, "该手机号已绑定其他账号")
        user.phone = body.phone or None
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────
# Admin: Auth / registration policy + provider configs
# ─────────────────────────────────────────────

@app.get("/api/admin/auth/config", tags=["admin"])
def admin_get_auth_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.auth_settings import load_registration_config
    return load_registration_config(db)


@app.put("/api/admin/auth/config", tags=["admin"])
def admin_update_auth_config(
    body: AuthRegistrationConfigPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.auth_settings import save_registration_config
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return save_registration_config(db, patch)


@app.get("/api/admin/auth/sms-provider", tags=["admin"])
def admin_get_sms_provider(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.auth_settings import load_sms_config, redact_sms
    return redact_sms(load_sms_config(db))


@app.put("/api/admin/auth/sms-provider", tags=["admin"])
def admin_update_sms_provider(
    body: SmsProviderPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.auth_settings import save_sms_config, redact_sms
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    # Allow clearing a secret by sending empty string, but ignore redaction placeholders
    for secret_field in ("secret_id", "secret_key"):
        val = patch.get(secret_field)
        if val and "..." in val:
            patch.pop(secret_field)
    return redact_sms(save_sms_config(db, patch))


@app.post("/api/admin/auth/sms-provider/test", tags=["admin"])
async def admin_test_sms_provider(
    body: ProviderTestReq,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.sms_service import send_test_sms
    try:
        await send_test_sms(db, body.target)
    except Exception as exc:                                            # noqa: BLE001
        raise HTTPException(400, f"测试发送失败: {exc}")
    return {"ok": True, "message": f"测试短信已发送至 {body.target}"}


@app.get("/api/admin/auth/email-provider", tags=["admin"])
def admin_get_email_provider(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.auth_settings import load_email_config, redact_email
    return redact_email(load_email_config(db))


@app.put("/api/admin/auth/email-provider", tags=["admin"])
def admin_update_email_provider(
    body: EmailProviderPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.auth_settings import save_email_config, redact_email
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    val = patch.get("smtp_password")
    if val and "..." in val:
        patch.pop("smtp_password")
    return redact_email(save_email_config(db, patch))


@app.post("/api/admin/auth/email-provider/test", tags=["admin"])
async def admin_test_email_provider(
    body: ProviderTestReq,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.email_service import send_test_email
    try:
        await send_test_email(db, body.target)
    except Exception as exc:                                            # noqa: BLE001
        raise HTTPException(400, f"测试发送失败: {exc}")
    return {"ok": True, "message": f"测试邮件已发送至 {body.target}"}


@app.get("/api/admin/auth/google-oauth", tags=["admin"])
def admin_get_google_oauth(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.auth_settings import load_google_config, redact_google
    return redact_google(load_google_config(db))


@app.put("/api/admin/auth/google-oauth", tags=["admin"])
def admin_update_google_oauth(
    body: GoogleOAuthPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.auth_settings import save_google_config, redact_google
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    val = patch.get("client_secret")
    if val and "..." in val:
        patch.pop("client_secret")
    return redact_google(save_google_config(db, patch))


# ─────────────────────────────────────────────
# Admin: Membership plans
# ─────────────────────────────────────────────

@app.get("/api/admin/membership/plans", response_model=List[MembershipPlanOut], tags=["admin"])
def admin_list_plans(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return (
        db.query(MembershipPlan)
        .order_by(MembershipPlan.tier.asc(), MembershipPlan.sort_order.asc(), MembershipPlan.duration_days.asc())
        .all()
    )


@app.post("/api/admin/membership/plans", response_model=MembershipPlanOut, tags=["admin"])
def admin_create_plan(
    body: MembershipPlanCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    if body.tier not in ("vip", "vvip", "vvvip"):
        raise HTTPException(400, "tier 必须是 vip / vvip / vvvip")
    plan = MembershipPlan(**body.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@app.put("/api/admin/membership/plans/{plan_id}", response_model=MembershipPlanOut, tags=["admin"])
def admin_update_plan(
    plan_id: int,
    body: MembershipPlanUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "套餐不存在")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


@app.delete("/api/admin/membership/plans/{plan_id}", tags=["admin"])
def admin_delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Soft-delete by setting is_active=False. Hard delete only if no orders reference it."""
    plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "套餐不存在")
    has_orders = db.query(PaymentOrder).filter(PaymentOrder.plan_id == plan_id).first()
    if has_orders:
        plan.is_active = False
        db.commit()
        return {"message": "套餐已下架（存在历史订单）"}
    db.delete(plan)
    db.commit()
    return {"message": "套餐已删除"}


# ─────────────────────────────────────────────
# Admin: Payment orders + manual confirmation
# ─────────────────────────────────────────────

@app.get("/api/admin/payment/orders", response_model=List[PaymentOrderOut], tags=["admin"])
def admin_list_orders(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(PaymentOrder)
    if status:
        q = q.filter(PaymentOrder.status == status)
    return q.order_by(PaymentOrder.created_at.desc()).limit(500).all()


@app.post("/api/admin/payment/orders/{order_no}/confirm", response_model=PaymentOrderOut, tags=["admin"])
def admin_confirm_order(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    from services.payment_service import admin_confirm
    return admin_confirm(db, order_no, current_user)


@app.post("/api/admin/payment/orders/{order_no}/refund", response_model=PaymentOrderOut, tags=["admin"])
def admin_refund_order(
    order_no: str,
    body: PaymentRefundReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    from services.payment_service import admin_refund
    return admin_refund(db, order_no, current_user, notes=body.notes or "")


@app.post("/api/admin/payment/orders/{order_no}/cancel", response_model=PaymentOrderOut, tags=["admin"])
def admin_cancel_order_route(
    order_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    from services.payment_service import admin_cancel
    return admin_cancel(db, order_no, current_user)


# ─────────────────────────────────────────────
# Admin: Payment provider configs
# ─────────────────────────────────────────────

@app.get("/api/admin/payment/providers", tags=["admin"])
def admin_get_payment_providers(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.payment_settings import load_payment_config, redact_payment
    return redact_payment(load_payment_config(db))


@app.put("/api/admin/payment/providers", tags=["admin"])
def admin_update_payment_providers(
    body: PaymentProvidersPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.payment_settings import save_payment_config, redact_payment, load_payment_config
    # Merge: don't let masked placeholders overwrite real secrets
    current = load_payment_config(db)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    for ch, sub in patch.items():
        if not isinstance(sub, dict):
            continue
        for field in list(sub.keys()):
            v = sub[field]
            if isinstance(v, str) and "..." in v and current.get(ch, {}).get(field):
                sub.pop(field)
    return redact_payment(save_payment_config(db, patch))


# ─────────────────────────────────────────────
# Admin: Membership config (tier labels, features, support info)
# ─────────────────────────────────────────────

@app.get("/api/admin/membership/config", tags=["admin"])
def admin_get_membership_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from services.payment_settings import load_membership_config
    return load_membership_config(db)


@app.put("/api/admin/membership/config", tags=["admin"])
def admin_update_membership_config(
    body: MembershipConfigPatch,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.payment_settings import save_membership_config
    return save_membership_config(db, body.model_dump(exclude_unset=True))


# ─────────────────────────────────────────────
# Admin: Manual tier adjustment
# ─────────────────────────────────────────────

@app.put("/api/admin/users/{user_id}/tier", response_model=UserOut, tags=["admin"])
def admin_adjust_user_tier(
    user_id: int,
    body: AdminTierAdjustReq,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    from services.membership_service import admin_set_tier
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.tier not in ("regular", "vip", "vvip", "vvvip"):
        raise HTTPException(400, "tier 无效")

    expires_at = body.expires_at
    if body.tier != "regular" and not expires_at and body.days:
        expires_at = datetime.utcnow() + timedelta(days=body.days)

    try:
        admin_set_tier(db, user, body.tier, expires_at)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if body.reason:
        db.add(CreditTransaction(
            user_id=user.id,
            amount=0,
            reason=f"[管理员 {current_user.username}] 调整等级为 {body.tier}: {body.reason}",
        ))
        db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────
# Admin: Credits cost configuration
# ─────────────────────────────────────────────

@app.get("/api/admin/credits-config", tags=["admin"])
def admin_get_credits_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Return download-credit costs per file type + logo generation cost."""
    from services.credits_settings import load_config
    return load_config(db)


@app.put("/api/admin/credits-config", tags=["admin"])
def admin_update_credits_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.credits_settings import save_config
    return save_config(db, body or {})


@app.get("/api/admin/tasks", response_model=List[TaskOut], tags=["admin"])
def admin_list_tasks(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return (
        db.query(Task)
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────
# Token Usage Admin Routes
# ─────────────────────────────────────────────

@app.get("/api/admin/token-usage", tags=["admin"])
def get_token_usage(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    user_id: Optional[int] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
    agent_type: Optional[str] = None,
    date_from: Optional[str] = None,   # YYYY-MM-DD
    date_to: Optional[str] = None,     # YYYY-MM-DD
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Paginated + filterable token usage records."""
    from sqlalchemy import func
    q = db.query(TokenUsage)

    if user_id:
        q = q.filter(TokenUsage.user_id == user_id)
    if model_name:
        q = q.filter(TokenUsage.model_name == model_name)
    if provider:
        q = q.filter(TokenUsage.provider == provider)
    if agent_type:
        q = q.filter(TokenUsage.agent_type == agent_type)
    if date_from:
        try:
            q = q.filter(TokenUsage.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(TokenUsage.created_at <= end)
        except ValueError:
            pass

    total = q.count()
    records = (
        q.order_by(TokenUsage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # Resolve usernames
    user_ids = {r.user_id for r in records if r.user_id}
    users_map = {}
    if user_ids:
        users = db.query(User.id, User.username).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.username for u in users}

    items = []
    for r in records:
        items.append({
            "id": r.id,
            "user_id": r.user_id,
            "username": users_map.get(r.user_id, "-"),
            "task_id": r.task_id,
            "agent_type": r.agent_type,
            "provider": r.provider,
            "model_name": r.model_name,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.total_tokens,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@app.get("/api/admin/token-usage/summary", tags=["admin"])
def get_token_usage_summary(
    user_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Aggregated token usage summary grouped by model and by date."""
    from sqlalchemy import func, cast, Date

    q = db.query(TokenUsage)
    if user_id:
        q = q.filter(TokenUsage.user_id == user_id)
    if date_from:
        try:
            q = q.filter(TokenUsage.created_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(TokenUsage.created_at <= end)
        except ValueError:
            pass

    # By model
    by_model = (
        q.with_entities(
            TokenUsage.provider,
            TokenUsage.model_name,
            func.sum(TokenUsage.prompt_tokens).label("prompt_tokens"),
            func.sum(TokenUsage.completion_tokens).label("completion_tokens"),
            func.sum(TokenUsage.total_tokens).label("total_tokens"),
            func.count(TokenUsage.id).label("call_count"),
        )
        .group_by(TokenUsage.provider, TokenUsage.model_name)
        .all()
    )

    # By date (last 30 days)
    by_date = (
        q.with_entities(
            func.date(TokenUsage.created_at).label("date"),
            func.sum(TokenUsage.total_tokens).label("total_tokens"),
            func.count(TokenUsage.id).label("call_count"),
        )
        .group_by(func.date(TokenUsage.created_at))
        .order_by(func.date(TokenUsage.created_at).desc())
        .limit(30)
        .all()
    )

    # Grand totals
    totals = q.with_entities(
        func.sum(TokenUsage.prompt_tokens),
        func.sum(TokenUsage.completion_tokens),
        func.sum(TokenUsage.total_tokens),
        func.count(TokenUsage.id),
    ).first()

    return {
        "totals": {
            "prompt_tokens": totals[0] or 0,
            "completion_tokens": totals[1] or 0,
            "total_tokens": totals[2] or 0,
            "call_count": totals[3] or 0,
        },
        "by_model": [
            {
                "provider": r.provider,
                "model_name": r.model_name,
                "prompt_tokens": r.prompt_tokens or 0,
                "completion_tokens": r.completion_tokens or 0,
                "total_tokens": r.total_tokens or 0,
                "call_count": r.call_count or 0,
            }
            for r in by_model
        ],
        "by_date": [
            {
                "date": str(r.date),
                "total_tokens": r.total_tokens or 0,
                "call_count": r.call_count or 0,
            }
            for r in by_date
        ],
    }


@app.get("/api/admin/token-usage/filters", tags=["admin"])
def get_token_usage_filters(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Return distinct values for filter dropdowns."""
    models = db.query(TokenUsage.model_name).distinct().all()
    providers = db.query(TokenUsage.provider).distinct().all()
    users = (
        db.query(User.id, User.username)
        .filter(User.id.in_(db.query(TokenUsage.user_id).filter(TokenUsage.user_id != None).distinct()))
        .all()
    )
    return {
        "models": [m[0] for m in models],
        "providers": [p[0] for p in providers],
        "users": [{"id": u.id, "username": u.username} for u in users],
    }


# ── Logo Provider Admin Configuration ─────────────────────────────────────────
@app.get("/api/admin/logo-provider", tags=["admin"])
def get_logo_provider_config(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.logo_settings import load_config, redact
    from services.logo_providers import list_providers
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.put("/api/admin/logo-provider", tags=["admin"])
def update_logo_provider_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.logo_settings import save_config, load_config, redact
    from services.logo_providers import list_providers
    patch = dict(body or {})
    # Don't overwrite existing keys when frontend sends back masked values
    for key_field in ("openai_api_key", "ideogram_api_key", "recraft_api_key"):
        val = patch.get(key_field)
        if val is not None and ("..." in val or val == ""):
            patch.pop(key_field, None)
    allowed = {"openai", "ideogram", "recraft"}
    if "provider" in patch and patch["provider"] not in allowed:
        raise HTTPException(400, f"Invalid provider, must be one of {allowed}")
    if "fallback" in patch and patch["fallback"] not in allowed:
        raise HTTPException(400, f"Invalid fallback, must be one of {allowed}")
    save_config(db, patch)
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.post("/api/admin/logo-provider/test", tags=["admin"])
async def test_logo_provider(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.logo_providers import test_provider
    name = (body or {}).get("provider", "openai")
    return await test_provider(name, db=db)


# ── Logo Generation (User-facing) ────────────────────────────────────────────
@app.post("/api/logo/generate", tags=["logo"])
async def generate_logo(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a logo generation job. Returns generation_id for progress polling."""
    brand_name = (body.get("brand_name") or "").strip()
    if not brand_name:
        raise HTTPException(400, "brand_name is required")

    credits_needed = 3
    if current_user.credits < credits_needed:
        raise HTTPException(402, f"积分不足，需要 {credits_needed} 积分，当前余额 {current_user.credits}")

    gen = LogoGeneration(
        user_id=current_user.id,
        brand_name=brand_name,
        industry=body.get("industry", ""),
        style=body.get("style", "modern"),
        primary_color=body.get("primary_color", ""),
        secondary_color=body.get("secondary_color", ""),
        include_text=body.get("include_text", True),
        variant_count=min(4, max(1, body.get("variant_count", 3))),
        status="processing",
        credits_charged=credits_needed,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    # Deduct credits
    current_user.credits -= credits_needed
    db.add(CreditTransaction(
        user_id=current_user.id,
        amount=-credits_needed,
        reason=f"Logo生成: {brand_name}",
    ))
    db.commit()

    # Launch background task
    import threading
    thread = threading.Thread(
        target=_run_logo_generation,
        args=(gen.id,),
        daemon=True,
    )
    thread.start()

    return {"generation_id": gen.id}


def _run_logo_generation(generation_id: int):
    """Run logo generation in a background thread."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_logo_generation(generation_id))
    finally:
        loop.close()


async def _async_logo_generation(generation_id: int):
    """Async logo generation pipeline."""
    from database import SessionLocal
    from services.logo_settings import load_config
    from services.logo_providers import generate_via_providers, build_logo_prompt

    db = SessionLocal()
    try:
        gen = db.get(LogoGeneration, generation_id)
        if not gen:
            return

        cfg = load_config(db)

        # Step 1: Build optimized prompt
        prompt = build_logo_prompt(
            brand_name=gen.brand_name,
            style=gen.style,
            primary_color=gen.primary_color or "",
            include_text=gen.include_text,
            industry=gen.industry or "",
        )
        gen.prompt_optimized = prompt
        db.commit()

        # Step 2: Generate via providers
        result, provider_name = await generate_via_providers(
            brand_name=gen.brand_name,
            prompt=prompt,
            style=gen.style,
            include_text=gen.include_text,
            variant_count=gen.variant_count,
            primary_color=gen.primary_color or "",
            db=db,
        )

        if not result.success:
            gen.status = "failed"
            gen.error_msg = result.error
            db.commit()
            return

        gen.provider = provider_name
        gen.variants = [
            {"index": v["index"], "png_url": v.get("png_url", ""), "svg_url": v.get("svg_url", "")}
            for v in result.variants
        ]

        # Step 3: Download and save locally
        import httpx
        from services.file_service import ensure_upload_dir, sanitize_filename
        from datetime import datetime as dt
        ensure_upload_dir()

        safe_brand = sanitize_filename(gen.brand_name)
        timestamp = dt.now().strftime("%Y%m%d%H%M%S")

        # Download first variant as main PNG
        if result.variants:
            main_url = result.variants[0].get("png_url", "")
            if main_url:
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.get(main_url)
                        resp.raise_for_status()
                        png_name = f"{safe_brand}_logo_{timestamp}.png"
                        png_path = os.path.join(UPLOAD_DIR, png_name)
                        with open(png_path, "wb") as f:
                            f.write(resp.content)
                        gen.png_path = png_path
                except Exception as e:
                    print(f"[Logo] PNG download failed: {e}")

        # Step 4: Generate PSD if we have the PNG
        if gen.png_path and os.path.exists(gen.png_path):
            try:
                from PIL import Image
                from psd_tools import PSDImage

                logo_img = Image.open(gen.png_path).convert("RGBA")
                W, H = 1024, 1024

                psd = PSDImage.new("RGBA", (W, H))

                # White background layer
                white_bg = Image.new("RGBA", (W, H), (255, 255, 255, 255))
                psd.append(psd.create_pixel_layer(white_bg, name="Background White"))

                # Logo layer (centered)
                logo_resized = logo_img.resize((W, H), Image.LANCZOS)
                psd.append(psd.create_pixel_layer(logo_resized, name="Logo"))

                # Black background layer (hidden by default)
                black_bg = Image.new("RGBA", (W, H), (0, 0, 0, 255))
                layer_black = psd.create_pixel_layer(black_bg, name="Background Black")
                layer_black.visible = False
                psd.append(layer_black)

                psd_name = f"{safe_brand}_logo_{timestamp}.psd"
                psd_path = os.path.join(UPLOAD_DIR, psd_name)
                psd.save(psd_path)
                gen.psd_path = psd_path
            except Exception as e:
                print(f"[Logo] PSD generation failed: {e}")

        # Step 5: Create brand kit ZIP
        try:
            import zipfile
            zip_name = f"{safe_brand}_brand_kit_{timestamp}.zip"
            zip_path = os.path.join(UPLOAD_DIR, zip_name)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add PNG variants
                if gen.png_path and os.path.exists(gen.png_path):
                    zf.write(gen.png_path, f"PNG/{os.path.basename(gen.png_path)}")
                # Download and add all variants
                if result.variants:
                    async with httpx.AsyncClient(timeout=60) as client:
                        for v in result.variants:
                            url = v.get("png_url", "")
                            if url:
                                try:
                                    resp = await client.get(url)
                                    resp.raise_for_status()
                                    vname = f"PNG/variant_{v['index'] + 1}.png"
                                    zf.writestr(vname, resp.content)
                                except Exception:
                                    pass
                            svg_url = v.get("svg_url", "")
                            if svg_url:
                                try:
                                    resp = await client.get(svg_url)
                                    resp.raise_for_status()
                                    vname = f"Vector/variant_{v['index'] + 1}.svg"
                                    zf.writestr(vname, resp.content)
                                except Exception:
                                    pass
                # Add PSD
                if gen.psd_path and os.path.exists(gen.psd_path):
                    zf.write(gen.psd_path, f"PSD_Source/{os.path.basename(gen.psd_path)}")
                # Add brand guide
                guide = (
                    f"# {gen.brand_name} Brand Kit\n\n"
                    f"Primary Color: {gen.primary_color or 'N/A'}\n"
                    f"Style: {gen.style}\n"
                    f"Industry: {gen.industry or 'N/A'}\n\n"
                    f"## Files\n"
                    f"- PNG/: Logo variants (transparent background)\n"
                    f"- Vector/: SVG files (if available)\n"
                    f"- PSD_Source/: Layered Photoshop file\n"
                )
                zf.writestr("BRAND_GUIDE.md", guide)
            gen.brand_kit_path = zip_path
        except Exception as e:
            print(f"[Logo] ZIP packaging failed: {e}")

        # Done!
        gen.status = "done"
        gen.completed_at = datetime.utcnow()
        db.commit()
        print(f"[Logo] Generation {generation_id} completed via {provider_name}")

    except Exception as e:
        print(f"[Logo] Generation {generation_id} failed: {e}")
        try:
            gen = db.get(LogoGeneration, generation_id)
            if gen:
                gen.status = "failed"
                gen.error_msg = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.get("/api/logo/progress/{generation_id}", tags=["logo"])
async def logo_progress(
    generation_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """SSE endpoint for logo generation progress."""
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(401, "Unauthorized")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    async def event_stream():
        import asyncio
        from database import SessionLocal
        for attempt in range(120):  # max 10 minutes
            await asyncio.sleep(3)
            # Use a fresh session each poll to see background thread's commits
            poll_db = SessionLocal()
            try:
                gen = poll_db.query(LogoGeneration).filter(
                    LogoGeneration.id == generation_id
                ).first()
                if not gen:
                    yield {"data": json.dumps({"type": "error", "message": "Not found"})}
                    return

                if gen.status == "done":
                    yield {"data": json.dumps({
                        "type": "done",
                        "variants": gen.variants or [],
                        "has_png": bool(gen.png_path),
                        "has_psd": bool(gen.psd_path),
                        "has_zip": bool(gen.brand_kit_path),
                        "provider": gen.provider or "",
                    })}
                    return
                elif gen.status == "failed":
                    yield {"data": json.dumps({
                        "type": "error",
                        "message": gen.error_msg or "Generation failed",
                    })}
                    return
                else:
                    # Estimate progress based on attempt count
                    percent = min(90, 20 + attempt * 2)
                    yield {"data": json.dumps({
                        "type": "progress",
                        "percent": percent,
                    })}
            finally:
                poll_db.close()

    return EventSourceResponse(event_stream())


@app.get("/api/logo/download/{generation_id}", tags=["logo"])
def download_logo(
    generation_id: int,
    format: str = Query("png"),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Download generated logo in specified format.

    Accepts JWT via Authorization header OR ?token= query param (for browser-
    native downloads via <a href>).
    """
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM

    jwt_token = token
    if not jwt_token and request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header[7:]

    if not jwt_token:
        raise HTTPException(401, "未提供身份凭证")

    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        current_user = db.query(User).filter(User.username == username).first()
        if not current_user or not current_user.is_active:
            raise HTTPException(401, "身份验证失败")
    except JWTError:
        raise HTTPException(401, "身份验证失败")

    gen = db.query(LogoGeneration).filter(
        LogoGeneration.id == generation_id,
        LogoGeneration.user_id == current_user.id,
    ).first()
    if not gen:
        raise HTTPException(404, "Logo generation not found")
    if gen.status != "done":
        raise HTTPException(400, "Logo generation not completed")

    if format == "png" and gen.png_path and os.path.exists(gen.png_path):
        return FileResponse(
            path=gen.png_path,
            filename=os.path.basename(gen.png_path),
            media_type="image/png",
        )
    elif format == "psd" and gen.psd_path and os.path.exists(gen.psd_path):
        return FileResponse(
            path=gen.psd_path,
            filename=os.path.basename(gen.psd_path),
            media_type="application/octet-stream",
        )
    elif format == "zip" and gen.brand_kit_path and os.path.exists(gen.brand_kit_path):
        return FileResponse(
            path=gen.brand_kit_path,
            filename=os.path.basename(gen.brand_kit_path),
            media_type="application/zip",
        )
    else:
        raise HTTPException(404, f"File not available for format: {format}")


@app.get("/api/logo/history", tags=["logo"])
def logo_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """List user's logo generation history."""
    q = db.query(LogoGeneration).filter(LogoGeneration.user_id == current_user.id)
    total = q.count()
    items = (
        q.order_by(LogoGeneration.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": g.id,
                "brand_name": g.brand_name,
                "style": g.style,
                "status": g.status,
                "provider": g.provider,
                "variants": g.variants,
                "has_png": bool(g.png_path),
                "has_psd": bool(g.psd_path),
                "has_zip": bool(g.brand_kit_path),
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in items
        ],
    }


# ─────────────────────────────────────────────
# Poster Provider Config (Admin)
# ─────────────────────────────────────────────
@app.get("/api/admin/poster-provider", tags=["admin"])
def get_poster_provider_config(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.poster_settings import load_config, redact
    from services.poster_providers import list_providers
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.put("/api/admin/poster-provider", tags=["admin"])
def update_poster_provider_config(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.poster_settings import save_config, load_config, redact
    from services.poster_providers import list_providers
    patch = dict(body or {})
    for key_field in ("openai_api_key", "flux_api_key", "jimeng_api_key",
                      "ideogram_api_key", "removebg_api_key"):
        val = patch.get(key_field)
        if val is not None and ("..." in val or val == ""):
            patch.pop(key_field, None)
    allowed = {"openai", "flux", "jimeng"}
    if "provider" in patch and patch["provider"] not in allowed:
        raise HTTPException(400, f"Invalid provider, must be one of {allowed}")
    if "fallback" in patch and patch["fallback"] not in allowed:
        raise HTTPException(400, f"Invalid fallback, must be one of {allowed}")
    save_config(db, patch)
    return {
        "config":    redact(load_config(db)),
        "providers": list_providers(db),
    }


@app.post("/api/admin/poster-provider/test", tags=["admin"])
async def test_poster_provider_route(
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from services.poster_providers import test_provider
    name = (body or {}).get("provider", "openai")
    return await test_provider(name, db=db)


# ─────────────────────────────────────────────
# Poster Generation (User-facing)
# ─────────────────────────────────────────────
@app.post("/api/poster/generate", tags=["poster"])
async def generate_poster(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a poster generation job. Returns generation_id for progress polling."""
    from services.credits_settings import load_config as load_credits_config

    brand_name = (body.get("brand_name") or "").strip()
    if not brand_name:
        raise HTTPException(400, "brand_name is required")

    event_keyword = (body.get("event_keyword") or "").strip()
    if not event_keyword:
        raise HTTPException(400, "event_keyword is required (节气/节日关键词)")

    # Credit cost — admin configurable
    cc = load_credits_config(db).get("poster_generation", {}).get("per_generation", 5)
    credits_needed = int(cc)
    if current_user.credits < credits_needed:
        raise HTTPException(402, f"积分不足，需要 {credits_needed} 积分，当前余额 {current_user.credits}")

    gen = PosterGeneration(
        user_id=current_user.id,
        brand_name=brand_name,
        event_keyword=event_keyword,
        headline=(body.get("headline") or "").strip() or None,
        subline=(body.get("subline") or "").strip() or None,
        industry=(body.get("industry") or "").strip() or None,
        style=body.get("style", "natural"),
        size=body.get("size", "portrait"),
        primary_color=(body.get("primary_color") or "").strip() or None,
        product_image_url=(body.get("product_image_url") or "").strip() or None,
        status="processing",
        credits_charged=credits_needed,
    )
    db.add(gen)
    db.commit()
    db.refresh(gen)

    # Deduct credits
    current_user.credits -= credits_needed
    db.add(CreditTransaction(
        user_id=current_user.id,
        amount=-credits_needed,
        reason=f"Poster生成: {brand_name} · {event_keyword}",
    ))
    db.commit()

    # Launch background task
    import threading
    thread = threading.Thread(
        target=_run_poster_generation,
        args=(gen.id,),
        daemon=True,
    )
    thread.start()

    return {"generation_id": gen.id}


def _run_poster_generation(generation_id: int):
    """Background thread runner for poster pipeline."""
    import asyncio
    from database import SessionLocal
    from services.poster_service import generate_poster_full

    db = SessionLocal()
    try:
        gen = db.query(PosterGeneration).filter(PosterGeneration.id == generation_id).first()
        if not gen:
            return
        asyncio.run(generate_poster_full(
            db=db,
            gen_id=gen.id,
            brand_name=gen.brand_name,
            event_keyword=gen.event_keyword or "",
            headline=gen.headline,
            subline=gen.subline,
            industry=gen.industry,
            style=gen.style or "natural",
            size_key=gen.size or "portrait",
            primary_color=gen.primary_color,
            product_description=None,
            variant_count=1,
            user_id=gen.user_id,
        ))
    except Exception as e:                                            # noqa: BLE001
        import traceback
        traceback.print_exc()
        try:
            gen = db.query(PosterGeneration).filter(PosterGeneration.id == generation_id).first()
            if gen:
                gen.status = "failed"
                gen.error_msg = str(e)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.get("/api/poster/progress/{generation_id}", tags=["poster"])
async def poster_progress(
    generation_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """SSE endpoint — polls PosterGeneration row every 3s until done."""
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(401, "Unauthorized")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    gen = db.query(PosterGeneration).filter(PosterGeneration.id == generation_id).first()
    if not gen:
        raise HTTPException(404, "Generation not found")
    if gen.user_id != user.id:
        raise HTTPException(403, "Not authorized")

    async def event_stream():
        import asyncio
        from database import SessionLocal
        for attempt in range(120):  # 10 minutes max
            s = SessionLocal()
            try:
                g = s.query(PosterGeneration).filter(PosterGeneration.id == generation_id).first()
                if not g:
                    yield {"data": json.dumps({"type": "error", "message": "Generation disappeared"})}
                    return
                if g.status == "done":
                    yield {"data": json.dumps({
                        "type": "done",
                        "variants": g.variants or [],
                        "provider": g.provider,
                    })}
                    return
                if g.status == "failed":
                    yield {"data": json.dumps({"type": "error", "message": g.error_msg or "Unknown"})}
                    return
                # Progress approximation — provider may take 30-120s
                pct = min(95, 15 + attempt * 5)
                yield {"data": json.dumps({"type": "progress", "percent": pct,
                                            "label": "生成海报背景..."})}
            finally:
                s.close()
            await asyncio.sleep(3)
        yield {"data": json.dumps({"type": "error", "message": "Generation timeout"})}

    return EventSourceResponse(event_stream())


@app.get("/api/poster/download/{generation_id}", tags=["poster"])
def download_poster(
    generation_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Download the composed poster PNG. JWT via header OR ?token=."""
    from jose import jwt, JWTError
    from auth import SECRET_KEY, ALGORITHM

    jwt_token = token
    if not jwt_token and request is not None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            jwt_token = auth_header[7:]
    if not jwt_token:
        raise HTTPException(401, "未提供身份凭证")
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        current_user = db.query(User).filter(User.username == username).first()
        if not current_user or not current_user.is_active:
            raise HTTPException(401, "身份验证失败")
    except JWTError:
        raise HTTPException(401, "身份验证失败")

    gen = db.query(PosterGeneration).filter(
        PosterGeneration.id == generation_id,
        PosterGeneration.user_id == current_user.id,
    ).first()
    if not gen:
        raise HTTPException(404, "Poster generation not found")
    if gen.status != "done" or not gen.png_path:
        raise HTTPException(400, "Poster generation not completed")
    if not os.path.exists(gen.png_path):
        raise HTTPException(404, "文件已被清理")
    return FileResponse(
        path=gen.png_path,
        filename=os.path.basename(gen.png_path),
        media_type="image/png",
    )


@app.get("/api/poster/file/{fname}", tags=["poster"])
def fetch_poster_file(
    fname: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve a poster image file by filename (used inline by the frontend preview)."""
    # Safety: deny traversal
    if "/" in fname or ".." in fname:
        raise HTTPException(400, "invalid filename")
    fpath = os.path.join(UPLOAD_DIR, fname)
    if not os.path.exists(fpath):
        raise HTTPException(404, "not found")
    # Verify the file belongs to this user via the poster_generations table
    gen = db.query(PosterGeneration).filter(
        PosterGeneration.user_id == current_user.id,
        PosterGeneration.png_path.like(f"%/{fname}"),
    ).first()
    if not gen:
        raise HTTPException(403, "not authorized")
    return FileResponse(path=fpath, filename=fname, media_type="image/png")


@app.get("/api/poster/history", tags=["poster"])
def poster_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    q = db.query(PosterGeneration).filter(PosterGeneration.user_id == current_user.id)
    total = q.count()
    items = (
        q.order_by(PosterGeneration.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": g.id,
                "brand_name": g.brand_name,
                "event_keyword": g.event_keyword,
                "style": g.style,
                "size": g.size,
                "status": g.status,
                "provider": g.provider,
                "variants": g.variants,
                "has_png": bool(g.png_path),
                "error_msg": g.error_msg,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in items
        ],
    }


# ─────────────────────────────────────────────
# Agent Meta Info
# ─────────────────────────────────────────────
@app.get("/api/agents", tags=["agents"])
def get_agents():
    return [
        {"type": k, "name": v["name"], "icon": v["icon"]}
        for k, v in AGENT_META.items()
    ]


# Serve frontend in production
frontend_dist = Path("../frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
