from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # nullable for OAuth-only users
    role = Column(String(20), default="user")  # "user" or "admin"
    credits = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Multi-channel auth fields
    phone = Column(String(20), unique=True, nullable=True, index=True)
    auth_provider = Column(String(30), default="local")  # local | email_otp | phone_sms | google
    google_id = Column(String(100), unique=True, nullable=True)
    google_email = Column(String(200), nullable=True)

    # Enterprise / profile fields
    company_name = Column(String(200), nullable=True)
    industry = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)  # 1-10 | 11-50 | 51-200 | 201-1000 | 1000+

    # Registration approval workflow
    pending_approval = Column(Boolean, default=False)

    # Membership (VIP / VVIP / VVVIP tiers)
    tier                   = Column(String(20), default="regular", index=True)  # regular|vip|vvip|vvvip
    tier_expires_at        = Column(DateTime, nullable=True)
    last_monthly_grant_at  = Column(DateTime, nullable=True)  # when we last auto-granted monthly credits

    tasks = relationship("Task", back_populates="user")
    credit_transactions = relationship("CreditTransaction", back_populates="user")


class OtpCode(Base):
    """One-time password codes for email / phone verification."""
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True)
    channel = Column(String(10), nullable=False)   # "email" | "phone"
    target = Column(String(200), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    purpose = Column(String(20), default="register")  # register | login | reset_password
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthRateLimit(Base):
    """Sliding-window rate limit buckets for auth-sensitive endpoints."""
    __tablename__ = "auth_rate_limits"
    id = Column(Integer, primary_key=True)
    bucket = Column(String(150), nullable=False, index=True)  # e.g. "otp:email:xxx@x.com"
    window_start = Column(DateTime, nullable=False)
    count = Column(Integer, default=0)


class MembershipPlan(Base):
    """VIP/VVIP/VVVIP subscription plans.

    Admins create plans with tier, duration, price, credits, and feature set.
    A plan represents a single purchasable package (e.g. "VIP Monthly").
    """
    __tablename__ = "membership_plans"
    id                 = Column(Integer, primary_key=True)
    tier               = Column(String(20), nullable=False, index=True)  # vip | vvip | vvvip
    name               = Column(String(100), nullable=False)
    duration_days      = Column(Integer, nullable=False)
    price_cents        = Column(Integer, nullable=False)   # stored in fen/cents
    price_currency     = Column(String(10), default="CNY")
    activation_credits = Column(Integer, default=0)        # granted immediately on activation
    monthly_credits    = Column(Integer, default=0)        # granted each month during active period
    features           = Column(JSON, default=list)        # ["gamma_ppt","hires_logo",...]
    description        = Column(Text, nullable=True)
    is_active          = Column(Boolean, default=True)
    sort_order         = Column(Integer, default=0)
    created_at         = Column(DateTime, default=datetime.utcnow)


class PaymentOrder(Base):
    """Membership purchase orders.

    Status lifecycle:
        pending            - order created, awaiting user action
        awaiting_confirm   - user clicked "I paid" (manual) or webhook pending
        paid               - confirmed and tier activated
        canceled           - user or admin canceled
        refunded           - admin refunded (tier downgraded)
        failed             - external provider reported failure
    """
    __tablename__ = "payment_orders"
    id                = Column(Integer, primary_key=True)
    order_no          = Column(String(40), unique=True, index=True, nullable=False)
    user_id           = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_id           = Column(Integer, ForeignKey("membership_plans.id"), nullable=False)
    channel           = Column(String(20), nullable=False)  # stripe | alipay | wechat | manual
    amount_cents      = Column(Integer, nullable=False)
    currency          = Column(String(10), default="CNY")
    status            = Column(String(20), default="pending", index=True)
    external_order_id = Column(String(200), nullable=True)
    external_metadata = Column(JSON, nullable=True)
    paid_at           = Column(DateTime, nullable=True)
    canceled_at       = Column(DateTime, nullable=True)
    refunded_at       = Column(DateTime, nullable=True)
    admin_notes       = Column(Text, nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
    expires_at        = Column(DateTime, nullable=False)   # order validity (24h default)

    user = relationship("User")
    plan = relationship("MembershipPlan")


class LLMConfig(Base):
    __tablename__ = "llm_configs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)  # "openai", "anthropic", "volcano"
    api_key = Column(String(1000), nullable=False)
    model_name = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=True)
    agent_type = Column(String(50), nullable=False)  # "strategy", "brand", "operations", "all"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentKnowledge(Base):
    __tablename__ = "agent_knowledge"
    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String(50), nullable=False)  # "strategy", "brand", "operations"
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    knowledge_type = Column(String(50), default="general")  # framework, case_study, market_data, methodology, industry_report, general
    source = Column(String(100), nullable=True)  # "seed", "upload", "crawl", "manual"
    source_file = Column(String(300), nullable=True)  # original filename
    quality_score = Column(Integer, default=7)  # 1-10
    tags = Column(String(500), nullable=True)  # comma-separated tags


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    query = Column(Text, nullable=False)
    agents_selected = Column(JSON)  # list: ["strategy","brand","operations"]
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    brand_name = Column(String(200), nullable=True)
    locale = Column(String(10), default="zh-CN")  # UI language when task was created
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tasks")
    results = relationship("TaskResult", back_populates="task", cascade="all, delete-orphan")


class TaskResult(Base):
    __tablename__ = "task_results"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    agent_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_type = Column(String(20), nullable=True)  # "md", "pdf", "png"
    file_name = Column(String(200), nullable=True)
    download_credits = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="results")


class SystemSetting(Base):
    """
    Simple key/value store for runtime configuration (PPT provider selection,
    external API keys, endpoints). Values are JSON-encoded in the `value` column.
    """
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)          # JSON-encoded
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TokenUsage(Base):
    """Track token consumption per LLM API call."""
    __tablename__ = "token_usages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    agent_type = Column(String(50), nullable=True)   # strategy / brand / operations
    provider = Column(String(50), nullable=False)     # openai / anthropic / volcano
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", backref="token_usages")
    task = relationship("Task", backref="token_usages")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=False)
    task_result_id = Column(Integer, ForeignKey("task_results.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="credit_transactions")


class PosterGeneration(Base):
    """Standalone poster generation (festival/event posters for brands).

    Mirrors LogoGeneration structure. Pipeline: background image generation
    → Pillow composition overlaying product + logo + brand info → Claude
    Vision quality check → final PNG output (2160×3840 default, 9:16 portrait).
    """
    __tablename__ = "poster_generations"
    id                  = Column(Integer, primary_key=True, index=True)
    user_id             = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand_name          = Column(String(200), nullable=False)
    event_keyword       = Column(String(100), nullable=True)   # 节气/节日关键词 e.g. "谷雨"
    headline            = Column(String(200), nullable=True)   # main headline text
    subline             = Column(String(300), nullable=True)   # sub-headline / slogan
    industry            = Column(String(100), nullable=True)
    style               = Column(String(50), default="natural")
    size                = Column(String(20), default="portrait")  # portrait | square | landscape | story
    primary_color       = Column(String(20), nullable=True)
    product_image_url   = Column(String(500), nullable=True)   # optional reference
    prompt_optimized    = Column(Text, nullable=True)
    status              = Column(String(20), default="processing")  # processing | done | failed
    provider            = Column(String(50), nullable=True)
    error_msg           = Column(Text, nullable=True)
    variants            = Column(JSON, nullable=True)  # [{index, png_url}]
    png_path            = Column(String(500), nullable=True)
    credits_charged     = Column(Integer, default=5)
    quality_feedback    = Column(Text, nullable=True)  # Claude Vision quality review (future)
    created_at          = Column(DateTime, default=datetime.utcnow)
    completed_at        = Column(DateTime, nullable=True)

    user = relationship("User", backref="poster_generations")


class LogoGeneration(Base):
    __tablename__ = "logo_generations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    brand_name = Column(String(200), nullable=False)
    industry = Column(String(100), nullable=True)
    style = Column(String(50), default="modern")
    primary_color = Column(String(20), nullable=True)
    secondary_color = Column(String(20), nullable=True)
    include_text = Column(Boolean, default=True)
    variant_count = Column(Integer, default=3)
    prompt_optimized = Column(Text, nullable=True)
    status = Column(String(20), default="processing")  # processing, done, failed
    provider = Column(String(50), nullable=True)
    error_msg = Column(Text, nullable=True)
    # Result URLs (stored as JSON list)
    variants = Column(JSON, nullable=True)  # [{index, png_url, svg_url}]
    # File paths for local storage
    png_path = Column(String(500), nullable=True)
    psd_path = Column(String(500), nullable=True)
    brand_kit_path = Column(String(500), nullable=True)
    credits_charged = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", backref="logo_generations")
