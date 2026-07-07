from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal"
    test_database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mock_exchange: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()