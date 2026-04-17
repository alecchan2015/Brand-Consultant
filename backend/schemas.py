from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    credits: int
    is_active: bool
    created_at: datetime
    # Extended multi-channel fields (all optional for backward compat)
    phone: Optional[str] = None
    auth_provider: Optional[str] = "local"
    pending_approval: Optional[bool] = False
    company_name: Optional[str] = None
    industry: Optional[str] = None
    position: Optional[str] = None
    company_size: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfilePatch(BaseModel):
    """User-editable profile fields (self-service or admin-editable)."""
    company_name: Optional[str] = None
    industry: Optional[str] = None
    position: Optional[str] = None
    company_size: Optional[str] = None
    phone: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class LLMConfigCreate(BaseModel):
    name: str
    provider: str  # "openai", "anthropic", "volcano"
    api_key: str
    model_name: str
    base_url: Optional[str] = None
    agent_type: str  # "strategy", "brand", "operations", "all"


class LLMConfigOut(BaseModel):
    id: int
    name: str
    provider: str
    model_name: str
    base_url: Optional[str]
    agent_type: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeCreate(BaseModel):
    agent_type: str
    title: str
    content: str


class KnowledgeOut(BaseModel):
    id: int
    agent_type: str
    title: str
    content: str
    created_at: datetime
    is_active: bool
    knowledge_type: Optional[str] = "general"
    source: Optional[str] = None
    source_file: Optional[str] = None
    quality_score: Optional[int] = 7
    tags: Optional[str] = None

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    query: str
    agents_selected: List[str]
    brand_name: Optional[str] = None


class TaskResultOut(BaseModel):
    id: int
    agent_type: str
    content: Optional[str]
    file_type: Optional[str]
    file_name: Optional[str]
    download_credits: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskOut(BaseModel):
    id: int
    query: str
    agents_selected: List[str]
    status: str
    brand_name: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    results: List[TaskResultOut] = []

    class Config:
        from_attributes = True


class UserCreditsUpdate(BaseModel):
    credits: int
    reason: Optional[str] = "管理员调整"


class UserStatusUpdate(BaseModel):
    is_active: bool


# ─── Multi-channel auth schemas ────────────────────────────────────────────
class OtpSendReq(BaseModel):
    channel: str                         # "email" | "phone"
    target: str                          # email address or phone number
    purpose: Optional[str] = "register"  # register | login | reset_password


class EmailRegisterReq(BaseModel):
    email: EmailStr
    otp: str
    password: Optional[str] = None       # optional; email-OTP accounts can skip
    username: Optional[str] = None
    profile: Optional[UserProfilePatch] = None


class EmailOtpLoginReq(BaseModel):
    email: EmailStr
    otp: str


class PhoneRegisterReq(BaseModel):
    phone: str
    otp: str
    password: Optional[str] = None
    username: Optional[str] = None
    profile: Optional[UserProfilePatch] = None


class PhoneOtpLoginReq(BaseModel):
    phone: str
    otp: str


class GoogleCallbackReq(BaseModel):
    code: str
    state: str
    profile: Optional[UserProfilePatch] = None


class AuthPublicConfig(BaseModel):
    methods: dict
    approval_required: bool


class AuthRegistrationConfigPatch(BaseModel):
    """All admin-editable registration policy. Partial updates supported."""
    methods: Optional[dict] = None
    approval_required: Optional[bool] = None
    email_whitelist_domains: Optional[List[str]] = None
    email_blacklist_domains: Optional[List[str]] = None
    credits_by_channel: Optional[dict] = None
    rate_limit: Optional[dict] = None


class SmsProviderPatch(BaseModel):
    provider: Optional[str] = "tencent"
    secret_id: Optional[str] = None
    secret_key: Optional[str] = None
    region: Optional[str] = None
    sdk_app_id: Optional[str] = None
    sign_name: Optional[str] = None
    template_id: Optional[str] = None


class EmailProviderPatch(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    use_ssl: Optional[bool] = None


class GoogleOAuthPatch(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None


class ProviderTestReq(BaseModel):
    """Target to send a test OTP/SMS to (admin config verification)."""
    target: str


class RegistrationResponse(BaseModel):
    """Returned after successful registration. token may be absent if awaiting approval."""
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[UserOut] = None
    pending_approval: bool = False
    message: Optional[str] = None
