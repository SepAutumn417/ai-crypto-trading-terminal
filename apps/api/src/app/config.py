from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal"
    test_database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test"
    # P0-2: 默认仅监听 127.0.0.1，防止局域网/容器网络暴露
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    mock_exchange: bool = True

    # P0-1: 实盘硬开关，必须显式设为 true 才允许真实下单
    real_trading_enabled: bool = False

    # Bitget 凭证（实盘必填，mock 模式可空）
    bitget_api_key: str | None = None
    bitget_api_secret: str | None = None
    bitget_passphrase: str | None = None

    # CORS 允许来源
    cors_origins: list[str] = ["http://localhost:3000"]

    # P0-2: REST API 认证 token，未配置时高风险端点全部拒绝访问
    api_token: str | None = None

    # P0-2: WebSocket 认证 token
    ws_token: str | None = None

    # P0-3: 二次确认有效期（秒），默认 60 秒
    confirmation_ttl_seconds: int = 60

    # P0-3: 二次确认口令（用户设置的二次确认密码）
    confirmation_passphrase: str | None = None

    # v0.5: LLM 配置（OpenAI 兼容接口）
    ai_evaluation_enabled: bool = False
    llm_provider: str = "openai"  # openai | deepseek | moonshot | custom
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 5  # PRD: AI 评估延迟 ≤ 5s，超时降级为 None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
