from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str
    claude_api_key: str
    secret_key: str
    session_ttl_hours: int = 24

    class Config:
        env_file = ".env"


settings = Settings()
