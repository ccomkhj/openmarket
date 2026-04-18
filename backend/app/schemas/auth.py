from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    totp_code: str | None = None


class LoginResponse(BaseModel):
    user_id: int
    role: str
    mfa_required: bool = False


class PosLoginRequest(BaseModel):
    user_id: int
    pin: str = Field(min_length=4, max_length=6)


class PosLoginResponse(BaseModel):
    user_id: int
    full_name: str


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12)
    full_name: str


class MfaEnrollResponse(BaseModel):
    secret: str
    uri: str


class MfaVerifyRequest(BaseModel):
    code: str


class MeResponse(BaseModel):
    id: int
    email: str | None
    full_name: str
    role: str


class BootstrapStatus(BaseModel):
    setup_required: bool


class UserCreate(BaseModel):
    email: str | None = None
    password: str | None = None
    pin: str | None = None
    full_name: str
    role: str


class UserOut(BaseModel):
    id: int
    email: str | None
    full_name: str
    role: str
    active: bool
    created_at: str | None = None
    last_login_at: str | None = None
