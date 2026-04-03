from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket"
    upload_dir: str = "uploads"

    model_config = {"env_prefix": ""}


settings = Settings()
