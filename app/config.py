from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "URL Shortener API"
    base_url: str = "http://localhost:8000"
    short_code_length: int = 6
    database_url: str = "sqlite:///./shortener.db"

    class Config:
        env_file = ".env"


settings = Settings()
