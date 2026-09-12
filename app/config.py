from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://gvrm:gvrm@localhost:5432/gvrm_iex"
    jwt_secret: str = "CHANGE_ME"
    access_token_minutes: int = 60
    upload_dir: str = "/data/uploads"
    cors_origins: str = "http://localhost:8000"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
