from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str
    claude_api_key: str
    secret_key: str
    session_ttl_hours: int = 24
    voyage_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
