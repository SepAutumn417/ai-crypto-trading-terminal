from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal"
    test_database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    mock_exchange: bool = True

    # Bitget 凭证（实盘必填，mock 模式可空）
    bitget_api_key: str | None = None
    bitget_api_secret: str | None = None
    bitget_passphrase: str | None = None

    # CORS 允许来源
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()