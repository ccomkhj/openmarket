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

    trusted_proxy_cidrs: str = "127.0.0.1/32"

    first_run_owner_email: str | None = None
    first_run_owner_password: str | None = None

    hibp_enabled: bool = True

    fiskaly_api_key: str = ""
    fiskaly_api_secret: str = ""
    fiskaly_tss_id: str = ""
    fiskaly_base_url: str = "https://kassensichv-middleware.fiskaly.com"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    @field_validator("session_secret_key")
    @classmethod
    def _validate_session_secret(cls, v: str) -> str:
        lowered = v.lower()
        exact_bad = {"changeme", "secret", "password", "dev", "test"}
        if lowered in exact_bad:
            raise ValueError("session_secret_key is an insecure placeholder")
        substrings_bad = ("change_me", "change me", "changeme")
        if any(s in lowered for s in substrings_bad):
            raise ValueError("session_secret_key contains a placeholder substring")
        if len(v) < 32:
            raise ValueError("session_secret_key must be at least 32 characters")
        return v

    @property
    def lan_ip_cidr_list(self) -> list[str]:
        return [s.strip() for s in self.lan_ip_cidrs.split(",") if s.strip()]

    @property
    def allowed_cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.allowed_cors_origins.split(",") if s.strip()]

    @property
    def trusted_proxy_cidr_list(self) -> list[str]:
        return [s.strip() for s in self.trusted_proxy_cidrs.split(",") if s.strip()]


settings = Settings()
