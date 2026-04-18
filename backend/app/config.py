from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket"
    upload_dir: str = "uploads"

    session_secret_key: str
    session_cookie_name: str = "openmarket_session"
    admin_session_idle_minutes: int = 480
    admin_session_absolute_max_hours: int = 24

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    lan_ip_cidrs: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8"

    allowed_cors_origins: str = "https://admin.local,https://pos.local,https://store.local"

    first_run_owner_email: str | None = None
    first_run_owner_password: str | None = None

    hibp_enabled: bool = True

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @field_validator("session_secret_key")
    @classmethod
    def _validate_session_secret(cls, v: str) -> str:
        bad = {"changeme", "secret", "password", "dev", "test"}
        if v.lower() in bad:
            raise ValueError("session_secret_key is an insecure placeholder")
        if len(v) < 32:
            raise ValueError("session_secret_key must be at least 32 characters")
        return v


settings = Settings()
