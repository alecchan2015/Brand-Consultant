import os
import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, Request, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from database import Base, engine, get_db
from models import User, LLMConfig, AgentKnowledge, Task, TaskResult, CreditTransaction, TokenUsage, LogoGeneration
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
            }
            for col, dtype in user_migrations.items():
                if col not in user_cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {dtype}"))
            conn.commit()

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
# Task Routes
# ─────────────────────────────────────────────

@app.post("/api/tasks", response_model=TaskOut, tags=["tasks"])
def create_task(
    body: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid_agents = {"strategy", "brand", "logo_design", "operations"}
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

                    # Save TaskResult
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
                            download_credits=0,
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
                            download_credits=0,
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
                            task.id, agent_type, task.brand_name or "品牌", full_content, db=db
                        )
                        pptx_result = TaskResult(
                            task_id=task.id,
                            agent_type=agent_type,
                            content=None,
                            file_path=pptx_path,
                            file_type="pptx",
                            file_name=pptx_name,
                            download_credits=0,
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
                                download_credits=0,
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
                                download_credits=0,
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
                                        download_credits=0,
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
                                    download_credits=0,
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
