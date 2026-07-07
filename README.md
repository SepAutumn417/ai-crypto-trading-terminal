# AI Personal Trading Terminal L4

v0.1：交易计划 + 仓位计算 + 风控 + 决策门。

## 开发环境

```bash
docker compose up -d postgres
uv sync
docker exec -it crypto_postgres psql -U crypto -c "CREATE DATABASE crypto_terminal_test;"
cd apps/api && uv run alembic upgrade head && cd ../..
cd apps/api && uv run uvicorn src.app.main:app --reload --port 8000 && cd ../..
pnpm install && pnpm dev:web
```

## 文档
- [v0.1 设计稿](docs/superpowers/specs/2026-07-07-crypto-trading-terminal-v0.1-design.md)
- [L4 文档包](ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/)
