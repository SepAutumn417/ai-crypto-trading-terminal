# v0.1 交易终端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 AI Personal Trading Terminal L4 v0.1：交易计划创建 + 仓位计算 + 风控检查 + 决策门 + 配置版本管理 + 前端 3 个页面。

**Architecture:** Python monorepo（uv workspace），5 个独立 packages（shared / position-sizing / risk-engine / decision-gate / config-versioning）+ FastAPI 应用 + Next.js 前端。所有核心计算逻辑为纯函数，无 IO，可独立测试。FastAPI 通过 editable install 引用 packages。

**Tech Stack:** Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 async / Alembic / PostgreSQL 16 / Next.js 14 / TypeScript / Tailwind / shadcn/ui / pytest / uv / pnpm

**参考文档:**
- [v0.1 设计稿](file:///f:/crypto/docs/superpowers/specs/2026-07-07-crypto-trading-terminal-v0.1-design.md)
- [L4 文档包](file:///f:/crypto/ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/)

---

## 文件结构总览

```text
f:\crypto\
  docker-compose.yml                      # PostgreSQL 16
  .env.example
  .gitignore
  pyproject.toml                          # uv workspace 根
  package.json                            # pnpm workspace 根
  pnpm-workspace.yaml
  README.md

  packages\
    shared\
      pyproject.toml
      src\shared\{__init__.py,enums.py,schemas.py,configs.py,account.py,events.py,api.py,errors.py}
      tests\{__init__.py,test_enums.py,test_schemas.py}
    position-sizing\
      pyproject.toml
      src\position_sizing\{__init__.py,rounding.py,calculator.py}
      tests\{__init__.py,test_rounding.py,test_calculator.py}
    risk-engine\
      pyproject.toml
      src\risk_engine\{__init__.py,checker.py,rules.py}
      tests\{__init__.py,test_checker.py,test_rules_block.py,test_rules_reduce.py}
    decision-gate\
      pyproject.toml
      src\decision_gate\{__init__.py,gate.py}
      tests\{__init__.py,test_gate.py}
    config-versioning\
      pyproject.toml
      src\config_versioning\{__init__.py,models.py,service.py}
      tests\{__init__.py,test_service.py}

  apps\
    api\
      pyproject.toml
      alembic.ini
      .env
      src\app\
        __init__.py
        main.py                           # FastAPI 入口
        config.py                         # Settings
        db.py                             # async engine/session + Base
        response.py                       # ApiResponse[T] / ApiError
        exceptions.py                     # AppException 及子类
        seed.py                           # 初始数据
        models\{__init__.py,base.py,trade_plan.py,position_sizing_result.py,risk_check.py,decision_gate_result.py,config_version.py,system_event.py,user_settings.py,account_risk_state.py}
        schemas\{__init__.py,trade_plan.py,config.py,system.py}
        api\{__init__.py,router.py,trade_plans.py,risk.py,configs.py,system.py}
        services\{__init__.py,plan_service.py,config_service.py}
      migrations\env.py + script.py.mako + versions\0001_init.py
      tests\{__init__.py,conftest.py,test_trade_plans_api.py,test_risk_api.py,test_configs_api.py,test_system_api.py,test_plan_service.py}

    web\
      package.json
      tsconfig.json
      next.config.js
      tailwind.config.ts
      postcss.config.js
      .env.local
      app\{layout.tsx,page.tsx,globals.css,plans\page.tsx,risk\page.tsx,settings\page.tsx}
      components\{layout\Navbar.tsx,layout\SystemStatusBadge.tsx,plans\*.tsx,risk\*.tsx,settings\*.tsx,ui\*}
      lib\{api.ts,types.ts,utils.ts}
      store\systemStore.ts
```

---

## Task 0：基础设施与 workspace 初始化

**Files:**
- Create: `f:\crypto\.gitignore`
- Create: `f:\crypto\.env.example`
- Create: `f:\crypto\docker-compose.yml`
- Create: `f:\crypto\pyproject.toml`
- Create: `f:\crypto\pnpm-workspace.yaml`
- Create: `f:\crypto\package.json`
- Create: `f:\crypto\README.md`

- [ ] **Step 1: 创建 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.ruff_cache/

# Node
node_modules/
.next/
out/

# Env
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# 工具
.superpowers/
```

- [ ] **Step 2: 创建 .env.example**

```env
DATABASE_URL=postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal
TEST_DATABASE_URL=postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test
POSTGRES_USER=crypto
POSTGRES_PASSWORD=crypto
POSTGRES_DB=crypto_terminal
API_HOST=0.0.0.0
API_PORT=8000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: 创建 docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: crypto_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-crypto}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-crypto}
      POSTGRES_DB: ${POSTGRES_DB:-crypto_terminal}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-crypto}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

- [ ] **Step 4: 创建根 pyproject.toml（uv workspace）**

```toml
[project]
name = "crypto-terminal"
version = "0.1.0"
description = "AI Personal Trading Terminal L4 - v0.1"
requires-python = ">=3.12"

[tool.uv.workspace]
members = [
    "packages/shared",
    "packages/position-sizing",
    "packages/risk-engine",
    "packages/decision-gate",
    "packages/config-versioning",
    "apps/api",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["packages", "apps/api/tests"]
```

- [ ] **Step 5: 创建 pnpm-workspace.yaml**

```yaml
packages:
  - "apps/web"
```

- [ ] **Step 6: 创建根 package.json**

```json
{
  "name": "crypto-terminal",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "build:web": "pnpm --filter web build"
  }
}
```

- [ ] **Step 7: 创建 README.md**

```markdown
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
```

- [ ] **Step 8: 启动 PostgreSQL 并验证**

Run: `cd f:\crypto && docker compose up -d postgres && docker compose ps`
Expected: postgres 容器状态为 healthy

- [ ] **Step 9: 初始化 git 并提交**

```bash
cd f:\crypto
git init
git add .
git commit -m "chore: initialize v0.1 workspace infrastructure"
```

---

## Task 1：packages/shared — 枚举与基础 schema

**Files:**
- Create: `f:\crypto\packages\shared\pyproject.toml`
- Create: `f:\crypto\packages\shared\src\shared\__init__.py`
- Create: `f:\crypto\packages\shared\src\shared\enums.py`
- Create: `f:\crypto\packages\shared\src\shared\configs.py`
- Create: `f:\crypto\packages\shared\src\shared\account.py`
- Create: `f:\crypto\packages\shared\src\shared\schemas.py`
- Create: `f:\crypto\packages\shared\src\shared\events.py`
- Create: `f:\crypto\packages\shared\src\shared\api.py`
- Create: `f:\crypto\packages\shared\src\shared\errors.py`
- Create: `f:\crypto\packages\shared\tests\__init__.py`
- Create: `f:\crypto\packages\shared\tests\test_enums.py`
- Create: `f:\crypto\packages\shared\tests\test_schemas.py`

- [ ] **Step 1: 创建 packages/shared/pyproject.toml**

```toml
[project]
name = "shared"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.5.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/shared"]

[dependency-groups]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]
```

- [ ] **Step 2: 创建 enums.py**

```python
from enum import Enum


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class MarginMode(str, Enum):
    ISOLATED = "isolated"
    CROSSED = "crossed"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OpportunityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    BLOCKED = "BLOCKED"


class RiskStatus(str, Enum):
    ALLOW = "ALLOW"
    ALLOW_CONFIRM = "ALLOW_CONFIRM"
    WARN = "WARN"
    REDUCE_RISK = "REDUCE_RISK"
    BLOCK = "BLOCK"


class DecisionGateStatus(str, Enum):
    ALLOW_CONFIRM = "ALLOW_CONFIRM"
    WAIT = "WAIT"
    REDUCE_RISK = "REDUCE_RISK"
    BLOCK = "BLOCK"
    EXPIRED = "EXPIRED"


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    CHECKED = "CHECKED"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ConfigType(str, Enum):
    RISK = "risk"
    EXECUTION = "execution"
    OPPORTUNITY_GRADE = "opportunity_grade"
    SYMBOL_RULES = "symbol_rules"
```

- [ ] **Step 3: 创建 configs.py**

```python
from decimal import Decimal
from pydantic import BaseModel

from shared.enums import MarginMode, OrderType


class RiskConfig(BaseModel):
    max_risk_percent: Decimal
    max_leverage: Decimal
    min_risk_reward_ratio: Decimal
    preferred_risk_reward_ratio: Decimal
    min_stop_distance_percent: Decimal
    daily_loss_limit_r: Decimal
    max_consecutive_losses: int
    cooldown_minutes_after_loss: int


class ExecutionConfig(BaseModel):
    enabled: bool
    mode: str
    margin_mode: MarginMode
    allowed_order_types: list[OrderType]
    require_stop_loss: bool
    require_user_confirmation: bool
    require_second_confirmation: bool


class OpportunityGradeConfig(BaseModel):
    a_max_risk_percent: Decimal
    b_max_risk_percent: Decimal
    c_max_risk_percent: Decimal
    blocked_max_risk_percent: Decimal


class SymbolRule(BaseModel):
    size_step: Decimal
    price_step: Decimal
    min_size: Decimal
    min_notional: Decimal
    max_leverage: Decimal
    fee_rate: Decimal


class SymbolRules(BaseModel):
    rules: dict[str, SymbolRule]

    def get(self, symbol: str) -> SymbolRule | None:
        return self.rules.get(symbol)
```

- [ ] **Step 4: 创建 account.py**

```python
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class AccountRiskState(BaseModel):
    daily_loss_r: Decimal = Decimal("0")
    consecutive_losses: int = 0
    cooldown_until: datetime | None = None
    last_trade_date: date | None = None


class UserSettings(BaseModel):
    execution_enabled: bool = False
    kill_switch: bool = True
    account_equity: Decimal | None = None
    mode: str = "training"
```

- [ ] **Step 5: 创建 schemas.py**

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

from shared.enums import (
    DecisionGateStatus, Direction, MarginMode,
    OpportunityGrade, PlanStatus, RiskStatus,
)


class TradePlanInput(BaseModel):
    exchange: str = "bitget"
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_prices: list[Decimal]
    leverage: Decimal
    risk_percent: Decimal
    opportunity_grade: OpportunityGrade
    equity: Decimal
    setup_type: str | None = None
    margin_mode: MarginMode = MarginMode.ISOLATED
    notes: str | None = None


class TradePlan(BaseModel):
    id: UUID
    exchange: str
    symbol: str
    direction: Direction
    entry_price: Decimal
    stop_loss_price: Decimal | None
    take_profit_prices: list[Decimal]
    leverage: Decimal
    margin_mode: MarginMode
    risk_percent: Decimal
    opportunity_grade: OpportunityGrade
    equity: Decimal
    setup_type: str | None
    notes: str | None
    status: PlanStatus
    risk_config_version: str | None = None
    strategy_config_version: str | None = None
    user_trading_config_version: str | None = None
    created_at: datetime
    updated_at: datetime


class PositionSizingResult(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    equity: Decimal
    risk_percent: Decimal
    risk_amount: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal | None
    stop_distance_percent: Decimal
    notional_value: Decimal
    raw_size: Decimal
    rounded_size: Decimal | None
    required_margin: Decimal
    leverage: Decimal
    estimated_fee: Decimal
    risk_reward_ratio: Decimal
    estimated_loss_at_stop: Decimal
    sizing_warnings: list[str] = Field(default_factory=list)


class RiskCheckResult(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    status: RiskStatus
    risk_amount: Decimal
    notional_value: Decimal
    required_margin: Decimal
    risk_reward_ratio: Decimal
    max_allowed_risk_percent: Decimal
    warnings: list[str] = Field(default_factory=list)
    block_reasons: list[str] = Field(default_factory=list)
    risk_config_version: str | None = None


class DecisionGateResult(BaseModel):
    id: UUID | None = None
    trade_plan_id: UUID | None = None
    risk_check_id: UUID | None = None
    result: DecisionGateStatus
    reasons: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: 创建 events.py、api.py、errors.py**

`events.py`:
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SystemEvent(BaseModel):
    id: UUID
    event_type: str
    severity: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    actor: str = "system"
    message: str
    payload: dict | None = None
    created_at: datetime
```

`api.py`:
```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    request_id: str
```

`errors.py`:
```python
class RiskBlockError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__(f"Risk blocked: {', '.join(reasons)}")


class ConfigNotFoundError(Exception):
    pass


class PlanNotFoundError(Exception):
    pass


class PlanStatusError(Exception):
    pass
```

- [ ] **Step 7: 创建 __init__.py 导出公共接口**

```python
from shared.enums import (
    ConfigType, DecisionGateStatus, Direction, MarginMode,
    OpportunityGrade, OrderType, PlanStatus, RiskStatus,
)
from shared.schemas import (
    DecisionGateResult, PositionSizingResult, RiskCheckResult,
    TradePlan, TradePlanInput,
)
from shared.configs import (
    ExecutionConfig, OpportunityGradeConfig, RiskConfig,
    SymbolRule, SymbolRules,
)
from shared.account import AccountRiskState, UserSettings
from shared.events import SystemEvent
from shared.api import ApiError, ApiResponse
from shared.errors import (
    ConfigNotFoundError, PlanNotFoundError, PlanStatusError, RiskBlockError,
)

__all__ = [
    "ConfigType", "DecisionGateStatus", "Direction", "MarginMode",
    "OpportunityGrade", "OrderType", "PlanStatus", "RiskStatus",
    "DecisionGateResult", "PositionSizingResult", "RiskCheckResult",
    "TradePlan", "TradePlanInput",
    "ExecutionConfig", "OpportunityGradeConfig", "RiskConfig",
    "SymbolRule", "SymbolRules",
    "AccountRiskState", "UserSettings",
    "SystemEvent", "ApiError", "ApiResponse",
    "ConfigNotFoundError", "PlanNotFoundError", "PlanStatusError", "RiskBlockError",
]
```

- [ ] **Step 8: 写 test_enums.py**

```python
from shared.enums import (
    ConfigType, DecisionGateStatus, Direction, MarginMode,
    OpportunityGrade, PlanStatus, RiskStatus,
)


def test_direction_values():
    assert Direction.LONG.value == "LONG"
    assert Direction.SHORT.value == "SHORT"


def test_opportunity_grade_values():
    assert OpportunityGrade.A.value == "A"
    assert OpportunityGrade.BLOCKED.value == "BLOCKED"


def test_risk_status_values():
    assert RiskStatus.ALLOW.value == "ALLOW"
    assert RiskStatus.REDUCE_RISK.value == "REDUCE_RISK"
    assert RiskStatus.BLOCK.value == "BLOCK"


def test_decision_gate_status_values():
    assert DecisionGateStatus.ALLOW_CONFIRM.value == "ALLOW_CONFIRM"
    assert DecisionGateStatus.EXPIRED.value == "EXPIRED"


def test_plan_status_values():
    assert PlanStatus.DRAFT.value == "DRAFT"
    assert PlanStatus.READY_FOR_CONFIRMATION.value == "READY_FOR_CONFIRMATION"


def test_config_type_values():
    assert ConfigType.RISK.value == "risk"
    assert ConfigType.SYMBOL_RULES.value == "symbol_rules"
```

- [ ] **Step 9: 写 test_schemas.py**

```python
from decimal import Decimal
from shared.enums import Direction, OpportunityGrade
from shared.schemas import TradePlanInput, PositionSizingResult
from shared.configs import RiskConfig, SymbolRule, SymbolRules


def test_trade_plan_input_creation():
    plan = TradePlanInput(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        entry_price=Decimal("62400"),
        stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800"), Decimal("64500")],
        leverage=Decimal("10"),
        risk_percent=Decimal("1"),
        opportunity_grade=OpportunityGrade.A,
        equity=Decimal("1500"),
    )
    assert plan.symbol == "BTCUSDT"
    assert plan.entry_price == Decimal("62400")


def test_position_sizing_result_defaults():
    result = PositionSizingResult(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1875"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.5"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.9375"), risk_reward_ratio=Decimal("2.24"),
        estimated_loss_at_stop=Decimal("15.9375"),
    )
    assert result.sizing_warnings == []


def test_symbol_rules_lookup():
    rules = SymbolRules(rules={
        "BTCUSDT": SymbolRule(
            size_step=Decimal("0.001"), price_step=Decimal("0.1"),
            min_size=Decimal("0.001"), min_notional=Decimal("5"),
            max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
        )
    })
    assert rules.get("BTCUSDT") is not None
    assert rules.get("ETHUSDT") is None
```

- [ ] **Step 10: 安装并运行测试**

Run: `cd f:\crypto && uv sync`
Expected: 所有 packages 安装成功

Run: `uv run pytest packages/shared/tests/ -v`
Expected: 所有测试通过

- [ ] **Step 11: 提交**

```bash
git add packages/shared pyproject.toml
git commit -m "feat(shared): add enums, schemas, configs, errors"
```

---

## Task 2：packages/position-sizing — 仓位计算

**Files:**
- Create: `f:\crypto\packages\position-sizing\pyproject.toml`
- Create: `f:\crypto\packages\position-sizing\src\position_sizing\__init__.py`
- Create: `f:\crypto\packages\position-sizing\src\position_sizing\rounding.py`
- Create: `f:\crypto\packages\position-sizing\src\position_sizing\calculator.py`
- Create: `f:\crypto\packages\position-sizing\tests\__init__.py`
- Create: `f:\crypto\packages\position-sizing\tests\test_rounding.py`
- Create: `f:\crypto\packages\position-sizing\tests\test_calculator.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "position-sizing"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.5.0", "shared"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/position_sizing"]

[tool.uv.sources]
shared = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 2: 写 test_rounding.py（失败测试）**

```python
from decimal import Decimal
from position_sizing.rounding import round_to_step


def test_round_to_step_exact():
    assert round_to_step(Decimal("0.03"), Decimal("0.001")) == Decimal("0.030")


def test_round_to_step_down():
    assert round_to_step(Decimal("0.0305"), Decimal("0.001")) == Decimal("0.030")


def test_round_to_step_large():
    assert round_to_step(Decimal("1.2345"), Decimal("0.1")) == Decimal("1.2")


def test_round_to_step_zero():
    assert round_to_step(Decimal("0"), Decimal("0.001")) == Decimal("0")


def test_round_to_step_smaller_than_step():
    assert round_to_step(Decimal("0.0005"), Decimal("0.001")) == Decimal("0")
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run pytest packages/position-sizing/tests/test_rounding.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 4: 实现 rounding.py**

```python
from decimal import Decimal, ROUND_DOWN


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    """按 step 向下取整。开仓量不能超过计算值。"""
    if step == 0:
        return value
    quotient = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return quotient * step
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest packages/position-sizing/tests/test_rounding.py -v`
Expected: PASS

- [ ] **Step 6: 写 test_calculator.py**

```python
from decimal import Decimal
from shared.configs import SymbolRule
from shared.enums import Direction
from position_sizing.calculator import calculate


def _btc_rules():
    return SymbolRule(
        size_step=Decimal("0.001"), price_step=Decimal("0.1"),
        min_size=Decimal("0.001"), min_notional=Decimal("5"),
        max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
    )


def test_calculate_long_basic():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=_btc_rules(),
    )
    assert result.risk_amount == Decimal("15")
    assert result.notional_value == Decimal("1872")
    assert result.raw_size == Decimal("0.03")
    assert result.rounded_size == Decimal("0.030")
    assert result.required_margin == Decimal("187.2")
    assert result.estimated_fee == Decimal("0.936")
    assert result.risk_reward_ratio == Decimal("2.8")
    assert result.estimated_loss_at_stop == Decimal("15.936")
    assert result.sizing_warnings == []


def test_calculate_short_basic():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("62900"),
        take_profit_prices=[Decimal("61000")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.SHORT,
        symbol_rules=_btc_rules(),
    )
    assert result.risk_amount == Decimal("15")
    assert result.risk_reward_ratio == Decimal("2.8")


def test_calculate_rounded_below_min_size():
    tiny_rules = SymbolRule(
        size_step=Decimal("1"), price_step=Decimal("0.1"),
        min_size=Decimal("1"), min_notional=Decimal("5"),
        max_leverage=Decimal("100"), fee_rate=Decimal("0.0005"),
    )
    result = calculate(
        equity=Decimal("10"), risk_percent=Decimal("0.1"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=tiny_rules,
    )
    assert result.rounded_size is None
    assert any("min_size" in w or "min_notional" in w for w in result.sizing_warnings)


def test_calculate_no_stop_loss():
    result = calculate(
        equity=Decimal("1500"), risk_percent=Decimal("1"),
        entry_price=Decimal("62400"), stop_loss_price=None,
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        fee_rate=Decimal("0.0005"), direction=Direction.LONG,
        symbol_rules=_btc_rules(),
    )
    assert result.stop_distance_percent == Decimal("0")
    assert result.notional_value == Decimal("0")
    assert result.rounded_size is None
    assert any("stop_loss" in w.lower() for w in result.sizing_warnings)
```

- [ ] **Step 7: 运行测试确认失败**

Run: `uv run pytest packages/position-sizing/tests/test_calculator.py -v`
Expected: FAIL

- [ ] **Step 8: 实现 calculator.py**

```python
from decimal import Decimal
from shared.configs import SymbolRule, SymbolRules
from shared.enums import Direction
from shared.schemas import PositionSizingResult
from position_sizing.rounding import round_to_step


def calculate(
    equity: Decimal,
    risk_percent: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal | None,
    take_profit_prices: list[Decimal],
    leverage: Decimal,
    fee_rate: Decimal,
    direction: Direction,
    symbol_rules: SymbolRule,
) -> PositionSizingResult:
    if isinstance(symbol_rules, SymbolRules):
        raise TypeError("请传入 SymbolRule 而非 SymbolRules")

    risk_amount = equity * risk_percent / Decimal("100")

    if stop_loss_price is None or entry_price == 0:
        stop_distance_percent = Decimal("0")
    else:
        stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price

    if stop_distance_percent > 0:
        notional_value = risk_amount / stop_distance_percent
    else:
        notional_value = Decimal("0")

    if entry_price > 0 and notional_value > 0:
        raw_size = notional_value / entry_price
    else:
        raw_size = Decimal("0")

    warnings: list[str] = []
    rounded_size: Decimal | None = None

    if stop_loss_price is None:
        warnings.append("no_stop_loss: 缺少止损价，无法计算有效仓位")
    elif stop_distance_percent == 0:
        warnings.append("zero_stop_distance: 止损距离为 0")
    else:
        rounded_size = round_to_step(raw_size, symbol_rules.size_step)
        if rounded_size < symbol_rules.min_size:
            warnings.append(f"below_min_size: rounded_size={rounded_size} < min_size={symbol_rules.min_size}")
            rounded_size = None
        elif rounded_size * entry_price < symbol_rules.min_notional:
            warnings.append(f"below_min_notional: notional={rounded_size * entry_price} < min_notional={symbol_rules.min_notional}")
            rounded_size = None

    required_margin = notional_value / leverage if leverage > 0 else Decimal("0")
    estimated_fee = notional_value * fee_rate

    if stop_distance_percent > 0 and take_profit_prices:
        if direction == Direction.LONG:
            tp_distance = take_profit_prices[0] - entry_price
        else:
            tp_distance = entry_price - take_profit_prices[0]
        risk_reward_ratio = tp_distance / (stop_distance_percent * entry_price)
    else:
        risk_reward_ratio = Decimal("0")

    estimated_loss_at_stop = risk_amount + estimated_fee

    return PositionSizingResult(
        equity=equity, risk_percent=risk_percent, risk_amount=risk_amount,
        entry_price=entry_price, stop_loss_price=stop_loss_price,
        stop_distance_percent=stop_distance_percent, notional_value=notional_value,
        raw_size=raw_size, rounded_size=rounded_size, required_margin=required_margin,
        leverage=leverage, estimated_fee=estimated_fee,
        risk_reward_ratio=risk_reward_ratio,
        estimated_loss_at_stop=estimated_loss_at_stop,
        sizing_warnings=warnings,
    )
```

- [ ] **Step 9: 创建 __init__.py**

```python
from position_sizing.calculator import calculate
from position_sizing.rounding import round_to_step

__all__ = ["calculate", "round_to_step"]
```

- [ ] **Step 10: 运行测试确认通过**

Run: `uv run pytest packages/position-sizing/tests/ -v`
Expected: 所有测试通过

- [ ] **Step 11: 提交**

```bash
git add packages/position-sizing
git commit -m "feat(position-sizing): add calculate() with precision rounding"
```

---

## Task 3：packages/risk-engine — 风控检查

**Files:**
- Create: `f:\crypto\packages\risk-engine\pyproject.toml`
- Create: `f:\crypto\packages\risk-engine\src\risk_engine\__init__.py`
- Create: `f:\crypto\packages\risk-engine\src\risk_engine\rules.py`
- Create: `f:\crypto\packages\risk-engine\src\risk_engine\checker.py`
- Create: `f:\crypto\packages\risk-engine\tests\__init__.py`
- Create: `f:\crypto\packages\risk-engine\tests\test_rules_block.py`
- Create: `f:\crypto\packages\risk-engine\tests\test_rules_reduce.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "risk-engine"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.5.0", "shared", "position-sizing"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/risk_engine"]

[tool.uv.sources]
shared = { workspace = true }
position-sizing = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 2: 写 test_rules_block.py（完整硬禁止测试）**

```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import (
    Direction, MarginMode, OpportunityGrade, OrderType, RiskStatus,
)
from shared.schemas import PositionSizingResult, TradePlanInput

from risk_engine.checker import check


def _risk_config():
    return RiskConfig(
        max_risk_percent=Decimal("3"), max_leverage=Decimal("10"),
        min_risk_reward_ratio=Decimal("1.5"), preferred_risk_reward_ratio=Decimal("2.0"),
        min_stop_distance_percent=Decimal("0.3"), daily_loss_limit_r=Decimal("2"),
        max_consecutive_losses=2, cooldown_minutes_after_loss=30,
    )


def _exec_config():
    return ExecutionConfig(
        enabled=True, mode="dry_run", margin_mode=MarginMode.ISOLATED,
        allowed_order_types=[OrderType.LIMIT], require_stop_loss=True,
        require_user_confirmation=True, require_second_confirmation=True,
    )


def _grade_config():
    return OpportunityGradeConfig(
        a_max_risk_percent=Decimal("3"), b_max_risk_percent=Decimal("1.5"),
        c_max_risk_percent=Decimal("0"), blocked_max_risk_percent=Decimal("0"),
    )


def _account(**kw):
    return AccountRiskState(**{**dict(
        daily_loss_r=Decimal("0"), consecutive_losses=0,
        cooldown_until=None, last_trade_date=None,
    ), **kw})


def _sizing(**kw):
    return PositionSizingResult(**{**dict(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1875"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.5"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.9375"), risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=Decimal("15.9375"), sizing_warnings=[],
    ), **kw})


def _plan(**kw):
    return TradePlanInput(**{**dict(
        symbol="BTCUSDT", direction=Direction.LONG,
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        risk_percent=Decimal("1"), opportunity_grade=OpportunityGrade.A,
        equity=Decimal("1500"),
    ), **kw})


def _run(plan=None, sizing=None, account=None, kill_switch=False, db_healthy=True):
    return check(
        sizing_result=sizing or _sizing(),
        risk_config=_risk_config(), execution_config=_exec_config(),
        opportunity_grade_config=_grade_config(),
        account_risk_state=account or _account(),
        plan=plan or _plan(),
        execution_enabled=True, kill_switch=kill_switch,
        exchange_connected=False, db_healthy=db_healthy,
    )


def test_no_stop_loss_blocks():
    r = _run(plan=_plan(stop_loss_price=None), sizing=_sizing(stop_loss_price=None, stop_distance_percent=Decimal("0")))
    assert r.status == RiskStatus.BLOCK
    assert any("no_stop_loss" in x for x in r.block_reasons)


def test_excessive_leverage_blocks():
    r = _run(plan=_plan(leverage=Decimal("20")), sizing=_sizing(leverage=Decimal("20")))
    assert r.status == RiskStatus.BLOCK


def test_low_rr_blocks():
    r = _run(sizing=_sizing(risk_reward_ratio=Decimal("1.0")))
    assert r.status == RiskStatus.BLOCK


def test_daily_loss_limit_blocks():
    r = _run(account=_account(daily_loss_r=Decimal("2")))
    assert r.status == RiskStatus.BLOCK


def test_consecutive_losses_blocks():
    r = _run(account=_account(consecutive_losses=2))
    assert r.status == RiskStatus.BLOCK


def test_cooldown_blocks():
    future = datetime.now(timezone.utc) + timedelta(minutes=20)
    r = _run(account=_account(cooldown_until=future))
    assert r.status == RiskStatus.BLOCK


def test_kill_switch_blocks():
    r = _run(kill_switch=True)
    assert r.status == RiskStatus.BLOCK


def test_blocked_grade_blocks():
    r = _run(plan=_plan(opportunity_grade=OpportunityGrade.BLOCKED))
    assert r.status == RiskStatus.BLOCK


def test_c_grade_blocks():
    r = _run(plan=_plan(opportunity_grade=OpportunityGrade.C))
    assert r.status == RiskStatus.BLOCK


def test_db_unhealthy_blocks():
    r = _run(db_healthy=False)
    assert r.status == RiskStatus.BLOCK


def test_excessive_risk_percent_blocks():
    r = _run(plan=_plan(risk_percent=Decimal("5")), sizing=_sizing(risk_percent=Decimal("5")))
    assert r.status == RiskStatus.BLOCK


def test_below_min_size_blocks():
    r = _run(sizing=_sizing(rounded_size=None, sizing_warnings=["below_min_size: ..."]))
    assert r.status == RiskStatus.BLOCK
```

- [ ] **Step 3: 写 test_rules_reduce.py**

```python
from decimal import Decimal
from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import (
    Direction, MarginMode, OpportunityGrade, OrderType, RiskStatus,
)
from shared.schemas import PositionSizingResult, TradePlanInput
from risk_engine.checker import check


def _cfgs():
    return (
        RiskConfig(
            max_risk_percent=Decimal("3"), max_leverage=Decimal("10"),
            min_risk_reward_ratio=Decimal("1.5"), preferred_risk_reward_ratio=Decimal("2.0"),
            min_stop_distance_percent=Decimal("0.3"), daily_loss_limit_r=Decimal("2"),
            max_consecutive_losses=2, cooldown_minutes_after_loss=30,
        ),
        ExecutionConfig(
            enabled=True, mode="dry_run", margin_mode=MarginMode.ISOLATED,
            allowed_order_types=[OrderType.LIMIT], require_stop_loss=True,
            require_user_confirmation=True, require_second_confirmation=True,
        ),
        OpportunityGradeConfig(
            a_max_risk_percent=Decimal("3"), b_max_risk_percent=Decimal("1.5"),
            c_max_risk_percent=Decimal("0"), blocked_max_risk_percent=Decimal("0"),
        ),
    )


def _sizing():
    return PositionSizingResult(
        equity=Decimal("1500"), risk_percent=Decimal("1"), risk_amount=Decimal("15"),
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        stop_distance_percent=Decimal("0.008"), notional_value=Decimal("1875"),
        raw_size=Decimal("0.03"), rounded_size=Decimal("0.030"),
        required_margin=Decimal("187.5"), leverage=Decimal("10"),
        estimated_fee=Decimal("0.9375"), risk_reward_ratio=Decimal("2.8"),
        estimated_loss_at_stop=Decimal("15.9375"), sizing_warnings=[],
    )


def _plan(grade=OpportunityGrade.A):
    return TradePlanInput(
        symbol="BTCUSDT", direction=Direction.LONG,
        entry_price=Decimal("62400"), stop_loss_price=Decimal("61900"),
        take_profit_prices=[Decimal("63800")], leverage=Decimal("10"),
        risk_percent=Decimal("1"), opportunity_grade=grade, equity=Decimal("1500"),
    )


def test_grade_b_reduces_risk():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc, account_risk_state=AccountRiskState(),
        plan=_plan(grade=OpportunityGrade.B), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.REDUCE_RISK
    assert r.max_allowed_risk_percent == Decimal("1.5")


def test_grade_a_allows():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc, account_risk_state=AccountRiskState(),
        plan=_plan(grade=OpportunityGrade.A), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.ALLOW
    assert r.max_allowed_risk_percent == Decimal("3")


def test_recent_loss_warns():
    rc, ec, gc = _cfgs()
    r = check(
        sizing_result=_sizing(), risk_config=rc, execution_config=ec,
        opportunity_grade_config=gc,
        account_risk_state=AccountRiskState(consecutive_losses=1),
        plan=_plan(grade=OpportunityGrade.A), execution_enabled=True,
        kill_switch=False, exchange_connected=False, db_healthy=True,
    )
    assert r.status == RiskStatus.ALLOW
    assert any("recent_loss" in w or "consecutive" in w for w in r.warnings)
```

- [ ] **Step 4: 运行测试确认失败**

Run: `uv run pytest packages/risk-engine/tests/ -v`
Expected: FAIL（模块不存在）

- [ ] **Step 5: 实现 rules.py**

```python
from datetime import datetime
from decimal import Decimal

from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import OpportunityGrade, RiskStatus
from shared.schemas import PositionSizingResult, TradePlanInput


def grade_max_risk(grade: OpportunityGrade, cfg: OpportunityGradeConfig) -> Decimal:
    match grade:
        case OpportunityGrade.A: return cfg.a_max_risk_percent
        case OpportunityGrade.B: return cfg.b_max_risk_percent
        case OpportunityGrade.C: return cfg.c_max_risk_percent
        case OpportunityGrade.BLOCKED: return cfg.blocked_max_risk_percent


def grade_to_status(grade: OpportunityGrade) -> RiskStatus:
    match grade:
        case OpportunityGrade.A: return RiskStatus.ALLOW
        case OpportunityGrade.B: return RiskStatus.REDUCE_RISK
        case OpportunityGrade.C | OpportunityGrade.BLOCKED: return RiskStatus.BLOCK


def check_hard_blocks(
    sizing: PositionSizingResult,
    risk_cfg: RiskConfig,
    exec_cfg: ExecutionConfig,
    account: AccountRiskState,
    plan: TradePlanInput,
    kill_switch: bool,
    db_healthy: bool,
    now: datetime,
) -> list[str]:
    reasons: list[str] = []

    if plan.stop_loss_price is None:
        reasons.append("no_stop_loss: 缺少止损价")

    if plan.risk_percent > risk_cfg.max_risk_percent:
        reasons.append(f"risk_percent_excessive: {plan.risk_percent} > {risk_cfg.max_risk_percent}")

    if plan.leverage > risk_cfg.max_leverage:
        reasons.append(f"leverage_excessive: {plan.leverage} > {risk_cfg.max_leverage}")

    stop_dist_pct = sizing.stop_distance_percent * Decimal("100")
    if plan.stop_loss_price is not None and stop_dist_pct < risk_cfg.min_stop_distance_percent:
        reasons.append(f"stop_distance_too_small: {stop_dist_pct}% < {risk_cfg.min_stop_distance_percent}%")

    if sizing.risk_reward_ratio < risk_cfg.min_risk_reward_ratio:
        reasons.append(f"risk_reward_too_low: {sizing.risk_reward_ratio} < {risk_cfg.min_risk_reward_ratio}")

    if account.daily_loss_r >= risk_cfg.daily_loss_limit_r:
        reasons.append(f"daily_loss_limit_reached: {account.daily_loss_r} >= {risk_cfg.daily_loss_limit_r}")

    if account.consecutive_losses >= risk_cfg.max_consecutive_losses:
        reasons.append(f"consecutive_loss_limit_reached: {account.consecutive_losses} >= {risk_cfg.max_consecutive_losses}")

    if account.cooldown_until is not None and now < account.cooldown_until:
        reasons.append(f"cooldown_active: {account.cooldown_until} > {now}")

    if kill_switch:
        reasons.append("kill_switch_active: Kill Switch 已开启")

    if not db_healthy:
        reasons.append("db_unhealthy: 数据库不可用")

    if plan.stop_loss_price is not None and sizing.rounded_size is None:
        reasons.append(f"sizing_failed: {', '.join(sizing.sizing_warnings) or 'rounded_size is None'}")

    return reasons


def check_warnings(
    sizing: PositionSizingResult,
    account: AccountRiskState,
    plan: TradePlanInput,
) -> list[str]:
    warnings: list[str] = []
    if account.consecutive_losses > 0:
        warnings.append(f"recent_loss: consecutive_losses={account.consecutive_losses}")
    if sizing.notional_value > 0:
        ratio = sizing.notional_value / sizing.equity
        if ratio > Decimal("5"):
            warnings.append(f"wide_stop: notional/equity={ratio} 偏高")
    return warnings
```

- [ ] **Step 6: 实现 checker.py**

```python
from datetime import datetime, timezone
from decimal import Decimal

from shared.account import AccountRiskState
from shared.configs import ExecutionConfig, OpportunityGradeConfig, RiskConfig
from shared.enums import RiskStatus
from shared.schemas import PositionSizingResult, RiskCheckResult, TradePlanInput

from risk_engine.rules import (
    check_hard_blocks, check_warnings, grade_max_risk, grade_to_status,
)


def check(
    sizing_result: PositionSizingResult,
    risk_config: RiskConfig,
    execution_config: ExecutionConfig,
    opportunity_grade_config: OpportunityGradeConfig,
    account_risk_state: AccountRiskState,
    plan: TradePlanInput,
    execution_enabled: bool,
    kill_switch: bool,
    exchange_connected: bool,
    db_healthy: bool,
) -> RiskCheckResult:
    now = datetime.now(timezone.utc)

    block_reasons = check_hard_blocks(
        sizing=sizing_result, risk_cfg=risk_config, exec_cfg=execution_config,
        account=account_risk_state, plan=plan,
        kill_switch=kill_switch, db_healthy=db_healthy, now=now,
    )

    if block_reasons:
        return RiskCheckResult(
            status=RiskStatus.BLOCK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=Decimal("0"),
            warnings=[], block_reasons=block_reasons, risk_config_version=None,
        )

    grade_status = grade_to_status(plan.opportunity_grade)
    max_allowed = grade_max_risk(plan.opportunity_grade, opportunity_grade_config)
    warnings = check_warnings(sizing=sizing_result, account=account_risk_state, plan=plan)

    if not exchange_connected:
        warnings.append("exchange_disconnected: v0.1 无交易所连接（正常）")

    if grade_status == RiskStatus.BLOCK:
        return RiskCheckResult(
            status=RiskStatus.BLOCK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=Decimal("0"),
            warnings=warnings,
            block_reasons=[f"grade_blocked: 机会等级 {plan.opportunity_grade.value} 不允许交易"],
            risk_config_version=None,
        )

    if grade_status == RiskStatus.REDUCE_RISK:
        return RiskCheckResult(
            status=RiskStatus.REDUCE_RISK,
            risk_amount=sizing_result.risk_amount,
            notional_value=sizing_result.notional_value,
            required_margin=sizing_result.required_margin,
            risk_reward_ratio=sizing_result.risk_reward_ratio,
            max_allowed_risk_percent=max_allowed,
            warnings=warnings, block_reasons=[], risk_config_version=None,
        )

    return RiskCheckResult(
        status=RiskStatus.ALLOW,
        risk_amount=sizing_result.risk_amount,
        notional_value=sizing_result.notional_value,
        required_margin=sizing_result.required_margin,
        risk_reward_ratio=sizing_result.risk_reward_ratio,
        max_allowed_risk_percent=max_allowed,
        warnings=warnings, block_reasons=[], risk_config_version=None,
    )
```

- [ ] **Step 7: 创建 __init__.py**

```python
from risk_engine.checker import check
__all__ = ["check"]
```

- [ ] **Step 8: 运行测试确认通过**

Run: `uv run pytest packages/risk-engine/tests/ -v`
Expected: 所有测试通过

- [ ] **Step 9: 提交**

```bash
git add packages/risk-engine
git commit -m "feat(risk-engine): implement hard block + reduce risk rules"
```

---

## Task 4：packages/decision-gate — 决策门

**Files:**
- Create: `f:\crypto\packages\decision-gate\pyproject.toml`
- Create: `f:\crypto\packages\decision-gate\src\decision_gate\__init__.py`
- Create: `f:\crypto\packages\decision-gate\src\decision_gate\gate.py`
- Create: `f:\crypto\packages\decision-gate\tests\__init__.py`
- Create: `f:\crypto\packages\decision-gate\tests\test_gate.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "decision-gate"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.5.0", "shared", "risk-engine"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/decision_gate"]

[tool.uv.sources]
shared = { workspace = true }
risk-engine = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 2: 写 test_gate.py**

```python
from decimal import Decimal
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import RiskCheckResult
from decision_gate.gate import decide


def _risk(status: RiskStatus) -> RiskCheckResult:
    return RiskCheckResult(
        status=status, risk_amount=Decimal("15"), notional_value=Decimal("1875"),
        required_margin=Decimal("187.5"), risk_reward_ratio=Decimal("2.8"),
        max_allowed_risk_percent=Decimal("3"), warnings=[], block_reasons=[],
        risk_config_version="risk-v1",
    )


def test_allow_becomes_allow_confirm():
    assert decide(_risk(RiskStatus.ALLOW), True, False).result == DecisionGateStatus.ALLOW_CONFIRM


def test_reduce_risk_passes_through():
    assert decide(_risk(RiskStatus.REDUCE_RISK), True, False).result == DecisionGateStatus.REDUCE_RISK


def test_block_passes_through():
    assert decide(_risk(RiskStatus.BLOCK), True, False).result == DecisionGateStatus.BLOCK


def test_execution_disabled_blocks():
    r = decide(_risk(RiskStatus.ALLOW), False, False)
    assert r.result == DecisionGateStatus.BLOCK
    assert any("execution_disabled" in x for x in r.reasons)


def test_kill_switch_blocks():
    r = decide(_risk(RiskStatus.ALLOW), True, True)
    assert r.result == DecisionGateStatus.BLOCK
    assert any("kill_switch" in x for x in r.reasons)


def test_expired():
    assert decide(_risk(RiskStatus.ALLOW), True, False, plan_expired=True).result == DecisionGateStatus.EXPIRED


def test_warn_becomes_wait():
    assert decide(_risk(RiskStatus.WARN), True, False).result == DecisionGateStatus.WAIT
```

- [ ] **Step 3: 实现 gate.py**

```python
from typing import Optional
from shared.enums import DecisionGateStatus, RiskStatus
from shared.schemas import DecisionGateResult, RiskCheckResult


def decide(
    risk_result: RiskCheckResult,
    execution_enabled: bool,
    kill_switch: bool,
    ai_evaluation: Optional[dict] = None,
    plan_expired: bool = False,
) -> DecisionGateResult:
    reasons: list[str] = []

    if plan_expired:
        return DecisionGateResult(result=DecisionGateStatus.EXPIRED, reasons=["plan_expired"])

    if not execution_enabled:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["execution_disabled: 执行模式未开启"],
        )

    if kill_switch:
        return DecisionGateResult(
            result=DecisionGateStatus.BLOCK,
            reasons=["kill_switch_active: Kill Switch 已开启"],
        )

    match risk_result.status:
        case RiskStatus.ALLOW | RiskStatus.ALLOW_CONFIRM:
            return DecisionGateResult(result=DecisionGateStatus.ALLOW_CONFIRM, reasons=reasons)
        case RiskStatus.REDUCE_RISK:
            return DecisionGateResult(result=DecisionGateStatus.REDUCE_RISK, reasons=reasons)
        case RiskStatus.WARN:
            return DecisionGateResult(
                result=DecisionGateStatus.WAIT,
                reasons=["risk_warn: 风控警告，等待用户调整"],
            )
        case RiskStatus.BLOCK:
            return DecisionGateResult(
                result=DecisionGateStatus.BLOCK,
                reasons=list(risk_result.block_reasons),
            )
```

- [ ] **Step 4: 创建 __init__.py 并运行测试**

```python
from decision_gate.gate import decide
__all__ = ["decide"]
```

Run: `uv run pytest packages/decision-gate/tests/ -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add packages/decision-gate
git commit -m "feat(decision-gate): implement decide() with 5 status outputs"
```

---

## Task 5：packages/config-versioning — 配置版本管理

**Files:**
- Create: `f:\crypto\packages\config-versioning\pyproject.toml`
- Create: `f:\crypto\packages\config-versioning\src\config_versioning\__init__.py`
- Create: `f:\crypto\packages\config-versioning\src\config_versioning\models.py`
- Create: `f:\crypto\packages\config-versioning\src\config_versioning\service.py`
- Create: `f:\crypto\packages\config-versioning\tests\__init__.py`
- Create: `f:\crypto\packages\config-versioning\tests\test_service.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "config-versioning"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.5.0", "shared"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/config_versioning"]

[tool.uv.sources]
shared = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 2: 创建 models.py**

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from shared.enums import ConfigType


class ConfigVersion(BaseModel):
    id: UUID
    config_type: ConfigType
    version_label: str
    payload: dict
    is_active: bool = False
    created_at: datetime
    activated_at: datetime | None = None
```

- [ ] **Step 3: 写 test_service.py**

```python
from decimal import Decimal
from uuid import uuid4
import pytest
from shared.enums import ConfigType
from config_versioning.service import ConfigStore, ConfigNotFoundError


@pytest.fixture
def store():
    return ConfigStore()


def test_create_version(store):
    v = store.create_version(ConfigType.RISK, "risk-v1", {"max_leverage": 10})
    assert v.config_type == ConfigType.RISK
    assert v.version_label == "risk-v1"
    assert v.is_active is False


def test_activate_version(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    store.activate_version(v1.id)
    assert store.get_version(v1.id).is_active is True

    v2 = store.create_version(ConfigType.RISK, "risk-v2", {})
    store.activate_version(v2.id)
    assert store.get_version(v1.id).is_active is False
    assert store.get_version(v2.id).is_active is True


def test_get_active_version(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    store.activate_version(v1.id)
    assert store.get_active_version(ConfigType.RISK).id == v1.id


def test_get_active_none_raises(store):
    store.create_version(ConfigType.RISK, "risk-v1", {})
    with pytest.raises(ConfigNotFoundError):
        store.get_active_version(ConfigType.RISK)


def test_list_versions(store):
    v1 = store.create_version(ConfigType.RISK, "risk-v1", {})
    v2 = store.create_version(ConfigType.RISK, "risk-v2", {})
    v3 = store.create_version(ConfigType.EXECUTION, "exec-v1", {})
    versions = store.list_versions(ConfigType.RISK)
    assert len(versions) == 2


def test_duplicate_label_raises(store):
    store.create_version(ConfigType.RISK, "risk-v1", {})
    with pytest.raises(ValueError):
        store.create_version(ConfigType.RISK, "risk-v1", {})


def test_get_version_not_found(store):
    with pytest.raises(ConfigNotFoundError):
        store.get_version(uuid4())
```

- [ ] **Step 4: 实现 service.py**

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4
from shared.enums import ConfigType
from config_versioning.models import ConfigVersion


class ConfigNotFoundError(Exception):
    pass


class ConfigStore:
    """内存实现，供单元测试使用。apps/api 用数据库实现替换。"""

    def __init__(self) -> None:
        self._versions: dict[UUID, ConfigVersion] = {}

    def create_version(self, config_type: ConfigType, version_label: str, payload: dict) -> ConfigVersion:
        for v in self._versions.values():
            if v.config_type == config_type and v.version_label == version_label:
                raise ValueError(f"Duplicate version_label: {config_type.value}/{version_label}")
        version = ConfigVersion(
            id=uuid4(), config_type=config_type, version_label=version_label,
            payload=payload, is_active=False,
            created_at=datetime.now(timezone.utc), activated_at=None,
        )
        self._versions[version.id] = version
        return version

    def get_version(self, version_id: UUID) -> ConfigVersion:
        v = self._versions.get(version_id)
        if v is None:
            raise ConfigNotFoundError(f"Version {version_id} not found")
        return v

    def list_versions(self, config_type: ConfigType) -> list[ConfigVersion]:
        return [v for v in self._versions.values() if v.config_type == config_type]

    def activate_version(self, version_id: UUID) -> ConfigVersion:
        target = self.get_version(version_id)
        for v in self._versions.values():
            if v.config_type == target.config_type and v.is_active:
                self._versions[v.id] = v.model_copy(update={"is_active": False})
        activated = target.model_copy(update={
            "is_active": True,
            "activated_at": datetime.now(timezone.utc),
        })
        self._versions[activated.id] = activated
        return activated

    def get_active_version(self, config_type: ConfigType) -> ConfigVersion:
        for v in self._versions.values():
            if v.config_type == config_type and v.is_active:
                return v
        raise ConfigNotFoundError(f"No active version for {config_type.value}")
```

- [ ] **Step 5: 创建 __init__.py 并运行测试**

```python
from config_versioning.models import ConfigVersion
from config_versioning.service import ConfigNotFoundError, ConfigStore
__all__ = ["ConfigVersion", "ConfigStore", "ConfigNotFoundError"]
```

Run: `uv run pytest packages/config-versioning/tests/ -v`
Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add packages/config-versioning
git commit -m "feat(config-versioning): add in-memory ConfigStore"
```

---

## Task 6：apps/api — FastAPI 骨架 + DB 模型 + 迁移

**Files:**
- Create: `f:\crypto\apps\api\pyproject.toml`
- Create: `f:\crypto\apps\api\alembic.ini`
- Create: `f:\crypto\apps\api\.env`
- Create: `f:\crypto\apps\api\src\app\__init__.py`
- Create: `f:\crypto\apps\api\src\app\config.py`
- Create: `f:\crypto\apps\api\src\app\db.py`
- Create: `f:\crypto\apps\api\src\app\response.py`
- Create: `f:\crypto\apps\api\src\app\exceptions.py`
- Create: `f:\crypto\apps\api\src\app\main.py`
- Create: 9 个实体 model 文件 + base.py + __init__.py = 11 个文件（见文件结构总览，其中 base.py 为 DeclarativeBase 基类、__init__.py 为导出聚合，实体 model 为 9 个：trade_plan / position_sizing_result / risk_check / decision_gate_result / config_version / system_event / user_settings / account_risk_state；v0.1 plan 文件结构总览列出 8 个实体 model + base.py，实际实现中 trade_journal 在后续迁移补入，此处以文件结构总览为准）
- Create: `f:\crypto\apps\api\migrations\env.py`
- Create: `f:\crypto\apps\api\migrations\script.py.mako`

- [ ] **Step 1: 创建 apps/api/pyproject.toml**

```toml
[project]
name = "api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110.0", "uvicorn[standard]>=0.27.0",
    "sqlalchemy[asyncio]>=2.0.0", "asyncpg>=0.29.0", "alembic>=1.13.0",
    "pydantic>=2.5.0", "pydantic-settings>=2.1.0",
    "shared", "position-sizing", "risk-engine", "decision-gate", "config-versioning",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/app"]

[tool.uv.sources]
shared = { workspace = true }
position-sizing = { workspace = true }
risk-engine = { workspace = true }
decision-gate = { workspace = true }
config-versioning = { workspace = true }

[dependency-groups]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "httpx>=0.26.0"]
```

- [ ] **Step 2: 创建 config.py / db.py / response.py / exceptions.py**

`config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal"
    test_database_url: str = "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

`db.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, future=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
```

`response.py`:
```python
from typing import Generic, TypeVar
from uuid import uuid4
from pydantic import BaseModel

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    request_id: str

    @classmethod
    def ok(cls, data) -> "ApiResponse":
        return cls(success=True, data=data, error=None, request_id=str(uuid4()))

    @classmethod
    def err(cls, code: str, message: str, details: dict | None = None) -> "ApiResponse":
        return cls(success=False, data=None, error=ApiError(code=code, message=message, details=details), request_id=str(uuid4()))
```

`exceptions.py`:
```python
from fastapi import HTTPException


class AppException(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details})


class ConfigNotFoundException(AppException):
    def __init__(self, config_type: str):
        super().__init__("CONFIG_NOT_FOUND", f"配置 {config_type} 未找到激活版本", 404)


class PlanNotFoundException(AppException):
    def __init__(self, plan_id: str):
        super().__init__("PLAN_NOT_FOUND", f"计划 {plan_id} 不存在", 404)


class PlanStatusException(AppException):
    def __init__(self, plan_id: str, current: str, expected: str):
        super().__init__("PLAN_STATUS_ERROR", f"计划 {plan_id} 状态 {current}，期望 {expected}", 409)
```

- [ ] **Step 3: 创建 8 个实体 model 文件（+ base.py + __init__.py）**

> 共 10 个文件：`base.py`（DeclarativeBase）+ `__init__.py`（导出聚合）+ 8 个实体 model（trade_plan / position_sizing_result / risk_check / decision_gate_result / config_version / system_event / user_settings / account_risk_state）。

每个 model 文件遵循设计稿 §4.2 的字段定义。关键模板（trade_plan.py 为例）：

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    candidate_plan_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    setup_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_price: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    take_profit_prices: Mapped[list] = mapped_column(JSONB, nullable=False)
    leverage: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    margin_mode: Mapped[str] = mapped_column(String(32), default="isolated")
    risk_percent: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    opportunity_grade: Mapped[str] = mapped_column(String(16), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    strategy_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_trading_config_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

其他 7 个 model 文件按设计稿 §4.2 字段定义同样实现（position_sizing_result / risk_check / decision_gate_result / config_version / system_event / user_settings / account_risk_state）。

- [ ] **Step 4: 创建 models/__init__.py 聚合导出**

```python
from app.models.account_risk_state import AccountRiskState
from app.models.config_version import ConfigVersionModel
from app.models.decision_gate_result import DecisionGateResult
from app.models.position_sizing_result import PositionSizingResult
from app.models.risk_check import RiskCheck
from app.models.system_event import SystemEvent
from app.models.trade_plan import TradePlan
from app.models.user_settings import UserSettings

__all__ = [
    "AccountRiskState", "ConfigVersionModel", "DecisionGateResult",
    "PositionSizingResult", "RiskCheck", "SystemEvent", "TradePlan", "UserSettings",
]
```

- [ ] **Step 5: 创建 main.py 最小骨架**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.response import ApiResponse


app = FastAPI(title="AI Personal Trading Terminal L4", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    return ApiResponse.ok({"status": "ok"})


@app.on_event("startup")
async def startup_seed():
    from app.db import async_session
    from app.seed import seed_all
    async with async_session() as db:
        await seed_all(db)
```

注意：`api_router` 此时还未创建完整，可先创建只含 health 的占位 `api/router.py`：

```python
from fastapi import APIRouter
api_router = APIRouter()
```

- [ ] **Step 6: 创建 alembic.ini、migrations/env.py、migrations/script.py.mako**

`alembic.ini` 标准配置（参考 SQLAlchemy 文档），`script_location = migrations`，`prepend_sys_path = .`。

`migrations/env.py`:
```python
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from app.config import settings
from app.db import Base
from app.models import *  # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

`migrations/script.py.mako`: 标准 Alembic 模板。

- [ ] **Step 7: 生成并执行迁移**

```bash
cd f:\crypto\apps\api
uv run alembic revision --autogenerate -m "init v0.1 tables"
```
检查生成的迁移文件包含 8 张表的 `create_table` + `idx_config_versions_active` 部分唯一索引（如缺失手动补充）。

```bash
uv run alembic upgrade head
```
Expected: 所有表创建成功

- [ ] **Step 8: 验证启动**

Run: `cd f:\crypto\apps\api && uv run uvicorn src.app.main:app --reload --port 8000`
打开 http://localhost:8000/api/health ，应返回 success=true

- [ ] **Step 9: 提交**

```bash
git add apps/api
git commit -m "feat(api): add FastAPI skeleton + DB models + initial migration"
```

---

## Task 7：apps/api — seed 数据 + 系统 API

**Files:**
- Create: `f:\crypto\apps\api\src\app\seed.py`
- Create: `f:\crypto\apps\api\src\app\schemas\__init__.py`
- Create: `f:\crypto\apps\api\src\app\schemas\system.py`
- Create: `f:\crypto\apps\api\src\app\api\__init__.py`
- Create: `f:\crypto\apps\api\src\app\api\router.py`（修改）
- Create: `f:\crypto\apps\api\src\app\api\system.py`
- Create: `f:\crypto\apps\api\tests\__init__.py`
- Create: `f:\crypto\apps\api\tests\conftest.py`
- Create: `f:\crypto\apps\api\tests\test_system_api.py`

- [ ] **Step 1: 创建 seed.py**

包含 `SEED_RISK_V1 / SEED_EXECUTION_V1 / SEED_OPPORTUNITY_GRADE_V1 / SEED_SYMBOL_RULES_V1`（对齐设计稿附录 A），以及 `seed_all(db)` 函数：插入 user_settings 单行（kill_switch=True, execution_enabled=False）、account_risk_state 单行（全 0）、4 个 config_versions（is_active=True）。

具体代码见设计稿附录 A 的 YAML 内容转为 Python dict。

- [ ] **Step 2: 创建 schemas/system.py**

```python
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class SystemStatus(BaseModel):
    execution_enabled: bool
    kill_switch: bool
    db_healthy: bool
    latest_event_type: str | None = None
    latest_event_at: datetime | None = None


class KillSwitchRequest(BaseModel):
    enabled: bool


class ExecutionModeRequest(BaseModel):
    enabled: bool


class UserSettingsOut(BaseModel):
    execution_enabled: bool
    kill_switch: bool
    account_equity: Decimal | None
    mode: str
```

- [ ] **Step 3: 创建 api/system.py**

实现 3 个端点：
- `GET /api/system/status`：返回 user_settings + 最新 system_event
- `POST /api/system/kill-switch`：切换 kill_switch，写 system_event
- `POST /api/system/execution-mode`：切换 execution_enabled，写 system_event

每个端点用 `Depends(get_db)`，返回 `ApiResponse.ok(...)`。

- [ ] **Step 4: 修改 api/router.py 挂载 system_router**

```python
from fastapi import APIRouter
from app.api.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
```

- [ ] **Step 5: 创建 tests/conftest.py**

提供 `client` fixture：使用 `TEST_DATABASE_URL`（postgres 测试库），每个测试前 `create_all`、后 `drop_all`，并先 `seed_all`。

关键代码：
```python
import os
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_terminal_test",
)
from app.db import Base, get_db, settings
from app.main import app
from app.models import *  # noqa

settings.database_url = os.environ["DATABASE_URL"]
# ... create_async_engine + AsyncClient + dependency_overrides
```

- [ ] **Step 6: 写 test_system_api.py**

```python
import pytest


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["execution_enabled"] is False
    assert data["kill_switch"] is True


@pytest.mark.asyncio
async def test_toggle_kill_switch(client):
    resp = await client.post("/api/system/kill-switch", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["kill_switch"] is False


@pytest.mark.asyncio
async def test_toggle_execution_mode(client):
    resp = await client.post("/api/system/execution-mode", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["execution_enabled"] is True
```

- [ ] **Step 7: 创建测试数据库并运行测试**

```bash
docker exec -it crypto_postgres psql -U crypto -c "CREATE DATABASE crypto_terminal_test;"
cd f:\crypto\apps\api
uv run pytest tests/test_system_api.py -v
```
Expected: 所有测试通过

- [ ] **Step 8: 提交**

```bash
git add apps/api
git commit -m "feat(api): add seed data + system status/kill-switch/execution-mode APIs"
```

---

## Task 8：apps/api — 配置版本 API

**Files:**
- Create: `f:\crypto\apps\api\src\app\schemas\config.py`
- Create: `f:\crypto\apps\api\src\app\api\configs.py`
- Modify: `f:\crypto\apps\api\src\app\api\router.py`
- Create: `f:\crypto\apps\api\tests\test_configs_api.py`

- [ ] **Step 1: 创建 schemas/config.py**

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class ConfigVersionOut(BaseModel):
    id: UUID
    config_type: str
    version_label: str
    payload: dict
    is_active: bool
    created_at: datetime
    activated_at: datetime | None


class CreateConfigRequest(BaseModel):
    config_type: str
    version_label: str
    payload: dict


class ActiveConfigsOut(BaseModel):
    risk: ConfigVersionOut | None = None
    execution: ConfigVersionOut | None = None
    opportunity_grade: ConfigVersionOut | None = None
    symbol_rules: ConfigVersionOut | None = None
```

- [ ] **Step 2: 创建 api/configs.py**

实现 4 个端点：
- `GET /api/configs/active`：返回 4 类激活配置
- `GET /api/configs?type=risk`：列出某类型所有版本
- `POST /api/configs`：创建新版本（检查 label 重复）
- `POST /api/configs/{version_id}/activate`：激活某版本（同类型其他失活）

- [ ] **Step 3: 修改 router.py 挂载 configs_router**

- [ ] **Step 4: 写 test_configs_api.py**

```python
import pytest


@pytest.mark.asyncio
async def test_get_active_configs(client):
    resp = await client.get("/api/configs/active")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk"]["version_label"] == "risk-v1"
    assert data["symbol_rules"]["version_label"] == "symbol_rules-v1"


@pytest.mark.asyncio
async def test_list_configs(client):
    resp = await client.get("/api/configs?type=risk")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_create_and_activate_config(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk", "version_label": "risk-v2", "payload": {"max_leverage": "5"},
    })
    assert resp.status_code == 200
    new_id = resp.json()["data"]["id"]

    resp = await client.post(f"/api/configs/{new_id}/activate")
    assert resp.json()["data"]["is_active"] is True

    resp = await client.get("/api/configs?type=risk")
    versions = {v["version_label"]: v for v in resp.json()["data"]}
    assert versions["risk-v2"]["is_active"] is True
    assert versions["risk-v1"]["is_active"] is False


@pytest.mark.asyncio
async def test_duplicate_label_rejected(client):
    resp = await client.post("/api/configs", json={
        "config_type": "risk", "version_label": "risk-v1", "payload": {},
    })
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DUPLICATE_LABEL"
```

- [ ] **Step 5: 运行测试并提交**

Run: `cd f:\crypto\apps\api && uv run pytest tests/test_configs_api.py -v`

```bash
git add apps/api
git commit -m "feat(api): add config version CRUD + activate APIs"
```

---

## Task 9：apps/api — 交易计划 + 风控 API + plan_service

**Files:**
- Create: `f:\crypto\apps\api\src\app\schemas\trade_plan.py`
- Create: `f:\crypto\apps\api\src\app\services\__init__.py`
- Create: `f:\crypto\apps\api\src\app\services\config_service.py`
- Create: `f:\crypto\apps\api\src\app\services\plan_service.py`
- Create: `f:\crypto\apps\api\src\app\api\trade_plans.py`
- Create: `f:\crypto\apps\api\src\app\api\risk.py`
- Modify: `f:\crypto\apps\api\src\app\api\router.py`
- Create: `f:\crypto\apps\api\tests\test_trade_plans_api.py`
- Create: `f:\crypto\apps\api\tests\test_risk_api.py`
- Create: `f:\crypto\apps\api\tests\test_plan_service.py`

- [ ] **Step 1: 创建 schemas/trade_plan.py**

包含 `TradePlanCreate / TradePlanOut / PositionSizingOut / RiskCheckOut / DecisionGateOut / CheckResult / CalculatePositionRequest / RiskCheckRequest`，字段对齐 shared.schemas。

- [ ] **Step 2: 创建 services/config_service.py**

提供从 DB 加载激活配置的函数：
- `get_active_risk_config(db) -> (RiskConfig, version_label)`
- `get_active_execution_config(db) -> (ExecutionConfig, version_label)`
- `get_active_opportunity_grade_config(db) -> (OpportunityGradeConfig, version_label)`
- `get_active_symbol_rules(db) -> (SymbolRules, version_label)`
- `get_symbol_rule(db, symbol) -> SymbolRule`
- `get_account_risk_state(db) -> AccountRiskState`
- `get_user_settings(db) -> UserSettings | None`

每个函数从 `config_versions` 表查询 `is_active=True` 的记录，按 payload 构造 Pydantic 配置对象。

- [ ] **Step 3: 创建 services/plan_service.py**

核心编排函数：
- `create_plan(db, plan_input) -> TradePlan`：创建计划（status=DRAFT）
- `get_plan(db, plan_id) -> TradePlan`
- `list_plans(db, status=None) -> list[TradePlan]`
- `check_plan(db, plan_id) -> dict`：跑 sizing + risk + decision，单事务落库 3 个结果 + 更新 plan.status

`check_plan` 流程（对齐设计稿 §2.3）：
1. 加载 plan（status 必须为 DRAFT 或 CHECKED）
2. 加载所有激活配置 + account_risk_state + user_settings
3. 调 `position_sizing.calculate()`
4. 调 `risk_engine.check()`
5. 调 `decision_gate.decide()`
6. 单事务写入 position_sizing_results / risk_checks / decision_gate_results，更新 trade_plan.status：
   - ALLOW_CONFIRM → READY_FOR_CONFIRMATION
   - REDUCE_RISK / WAIT / BLOCK → CHECKED
7. 返回 `{plan, sizing, risk, decision}`

- [ ] **Step 4: 创建 api/trade_plans.py**

实现 4 个端点：
- `POST /api/trade-plans`：创建计划
- `POST /api/trade-plans/{id}/check`：跑检查
- `GET /api/trade-plans?status=DRAFT`：列表
- `GET /api/trade-plans/{id}`：详情（含 sizing/risk/decision）

- [ ] **Step 5: 创建 api/risk.py**

实现 2 个端点（不落库）：
- `POST /api/risk/calculate-position`
- `POST /api/risk/check`

- [ ] **Step 6: 修改 router.py 挂载 trade_plans_router + risk_router**

- [ ] **Step 7: 写 test_trade_plans_api.py**

```python
import pytest


@pytest.mark.asyncio
async def test_create_plan(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "DRAFT"
    return body["data"]["id"]


@pytest.mark.asyncio
async def test_check_plan_allows(client):
    # 先创建
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    # 先开启 execution_mode、关闭 kill_switch
    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    # 跑检查
    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    assert body["decision"]["result"] == "ALLOW_CONFIRM"
    assert body["plan"]["status"] == "READY_FOR_CONFIRMATION"


@pytest.mark.asyncio
async def test_check_plan_blocks_no_stop(client):
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": None,
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    resp = await client.post(f"/api/trade-plans/{plan_id}/check")
    body = resp.json()["data"]
    assert body["risk"]["status"] == "BLOCK"
    assert body["decision"]["result"] == "BLOCK"
    assert body["plan"]["status"] == "CHECKED"


@pytest.mark.asyncio
async def test_list_plans(client):
    await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    resp = await client.get("/api/trade-plans?status=DRAFT")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1
```

- [ ] **Step 8: 写 test_risk_api.py**

```python
import pytest


@pytest.mark.asyncio
async def test_calculate_position(client):
    resp = await client.post("/api/risk/calculate-position", json={
        "equity": "1500", "risk_percent": "1",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "fee_rate": "0.0005", "direction": "LONG", "symbol": "BTCUSDT",
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["risk_amount"] == "15"
    assert data["rounded_size"] == "0.030"


@pytest.mark.asyncio
async def test_risk_check(client):
    resp = await client.post("/api/risk/check", json={
        "plan": {
            "symbol": "BTCUSDT", "direction": "LONG",
            "entry_price": "62400", "stop_loss_price": "61900",
            "take_profit_prices": ["63800"], "leverage": "10",
            "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
        },
        "sizing_result": {
            "equity": "1500", "risk_percent": "1", "risk_amount": "15",
            "entry_price": "62400", "stop_loss_price": "61900",
            "stop_distance_percent": "0.008", "notional_value": "1875",
            "raw_size": "0.03", "rounded_size": "0.030",
            "required_margin": "187.5", "leverage": "10",
            "estimated_fee": "0.9375", "risk_reward_ratio": "2.8",
            "estimated_loss_at_stop": "15.9375", "sizing_warnings": [],
        },
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ALLOW"
```

- [ ] **Step 9: 写 test_plan_service.py（集成测试，验证风控结果落库）**

```python
import pytest
from sqlalchemy import select
from app.models import RiskCheck, PositionSizingResult, DecisionGateResult


@pytest.mark.asyncio
async def test_check_persists_results(client, db_session):
    # 创建 + 检查
    resp = await client.post("/api/trade-plans", json={
        "symbol": "BTCUSDT", "direction": "LONG",
        "entry_price": "62400", "stop_loss_price": "61900",
        "take_profit_prices": ["63800"], "leverage": "10",
        "risk_percent": "1", "opportunity_grade": "A", "equity": "1500",
    })
    plan_id = resp.json()["data"]["id"]

    await client.post("/api/system/execution-mode", json={"enabled": True})
    await client.post("/api/system/kill-switch", json={"enabled": False})

    await client.post(f"/api/trade-plans/{plan_id}/check")

    # 验证 3 个结果表都有数据
    from uuid import UUID
    ps = await db_session.scalar(select(PositionSizingResult).where(PositionSizingResult.trade_plan_id == UUID(plan_id)))
    rc = await db_session.scalar(select(RiskCheck).where(RiskCheck.trade_plan_id == UUID(plan_id)))
    dg = await db_session.scalar(select(DecisionGateResult).where(DecisionGateResult.trade_plan_id == UUID(plan_id)))
    assert ps is not None
    assert rc is not None
    assert dg is not None
```

- [ ] **Step 10: 运行所有 API 测试并提交**

Run: `cd f:\crypto\apps\api && uv run pytest tests/ -v`
Expected: 所有测试通过

```bash
git add apps/api
git commit -m "feat(api): add trade-plans + risk APIs with plan_service orchestration"
```

---

## Task 10：apps/web — Next.js 前端 3 个页面

**Files:**
- Create: `f:\crypto\apps\web\package.json`
- Create: `f:\crypto\apps\web\tsconfig.json`
- Create: `f:\crypto\apps\web\next.config.js`
- Create: `f:\crypto\apps\web\tailwind.config.ts`
- Create: `f:\crypto\apps\web\postcss.config.js`
- Create: `f:\crypto\apps\web\.env.local`
- Create: `f:\crypto\apps\web\app\{layout.tsx,page.tsx,globals.css}`
- Create: `f:\crypto\apps\web\app\plans\page.tsx`
- Create: `f:\crypto\apps\web\app\risk\page.tsx`
- Create: `f:\crypto\apps\web\app\settings\page.tsx`
- Create: `f:\crypto\apps\web\components\layout\{Navbar.tsx,SystemStatusBadge.tsx}`
- Create: `f:\crypto\apps\web\components\plans\{PlanList.tsx,PlanForm.tsx,PlanDetail.tsx,SizingCard.tsx,RiskCard.tsx,DecisionCard.tsx}`
- Create: `f:\crypto\apps\web\components\risk\{RiskConfigCard.tsx,AccountRiskStateCard.tsx,KillSwitchToggle.tsx,ConfigVersionManager.tsx}`
- Create: `f:\crypto\apps\web\components\settings\{EquityEditor.tsx,RiskConfigEditor.tsx,ExecutionConfigEditor.tsx,OpportunityGradeEditor.tsx,SymbolRulesEditor.tsx}`
- Create: `f:\crypto\apps\web\lib\{api.ts,types.ts,utils.ts}`
- Create: `f:\crypto\apps\web\store\systemStore.ts`

- [ ] **Step 1: 初始化 Next.js 项目**

```bash
cd f:\crypto\apps\web
pnpm create next-app . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
pnpm add @tanstack/react-query zustand react-hook-form @hookform/resolvers zod
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button input label select table tabs switch dialog badge card form textarea separator
```

- [ ] **Step 2: 配置 next.config.js（API 代理）**

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
    ];
  },
};
module.exports = nextConfig;
```

- [ ] **Step 3: 创建 lib/types.ts**

与后端 Pydantic 对齐的 TypeScript 类型：`TradePlan / PositionSizingResult / RiskCheckResult / DecisionGateResult / SystemStatus / UserSettings / ConfigVersion / RiskConfig / ExecutionConfig / OpportunityGradeConfig / SymbolRules`。

- [ ] **Step 4: 创建 lib/api.ts**

封装所有 API 调用：`api.getSystemStatus() / api.toggleKillSwitch(enabled) / api.toggleExecutionMode(enabled) / api.createPlan(input) / api.checkPlan(id) / api.listPlans(status) / api.getPlan(id) / api.calculatePosition(input) / api.getActiveConfigs() / api.listConfigs(type) / api.createConfig(input) / api.activateConfig(id) / api.updateEquity(equity)`。

- [ ] **Step 5: 创建 store/systemStore.ts**

```typescript
import { create } from 'zustand';

interface SystemState {
  executionEnabled: boolean;
  killSwitch: boolean;
  setExecutionEnabled: (v: boolean) => void;
  setKillSwitch: (v: boolean) => void;
}

export const useSystemStore = create<SystemState>((set) => ({
  executionEnabled: false,
  killSwitch: true,
  setExecutionEnabled: (v) => set({ executionEnabled: v }),
  setKillSwitch: (v) => set({ killSwitch: v }),
}));
```

- [ ] **Step 6: 创建 app/layout.tsx + Navbar + SystemStatusBadge**

`layout.tsx`：包裹 QueryClientProvider，渲染 Navbar。`page.tsx`：重定向到 `/plans`。

`Navbar.tsx`：3 个导航链接（Trade Plans / Risk Center / Settings）+ SystemStatusBadge（显示 Kill Switch 状态灯 + Execution Mode 开关）。

`SystemStatusBadge.tsx`：调用 `api.getSystemStatus()`，同步到 systemStore，提供 Kill Switch / Execution Mode 的开关按钮。

- [ ] **Step 7: 创建 app/plans/page.tsx + 6 个 plans 组件**

布局：左侧 PlanList（按 created_at 倒序，支持 status 筛选），右侧 PlanForm 或 PlanDetail。

`PlanForm.tsx`：react-hook-form + zod 校验，字段：exchange / symbol / direction / entry_price / stop_loss_price / take_profit_prices（动态数组）/ leverage / risk_percent / opportunity_grade / equity / setup_type / margin_mode / notes。提交调 `api.createPlan()`，成功后刷新列表。

`PlanDetail.tsx`：展示计划字段 + "检查"按钮（调 `api.checkPlan(id)`）+ 检查结果展示 SizingCard / RiskCard / DecisionCard。

`SizingCard.tsx`：展示 risk_amount / notional_value / rounded_size / required_margin / estimated_fee / risk_reward_ratio / estimated_loss_at_stop。

`RiskCard.tsx`：展示 status / max_allowed_risk_percent / warnings / block_reasons。

`DecisionCard.tsx`：展示 result / reasons。

- [ ] **Step 8: 创建 app/risk/page.tsx + 4 个 risk 组件**

`RiskConfigCard.tsx`：展示当前激活的 risk 配置字段。

`AccountRiskStateCard.tsx`：展示 daily_loss_r / consecutive_losses / cooldown_until / last_trade_date（v0.1 恒为初始值，但 UI 完整）。

`KillSwitchToggle.tsx`：Kill Switch 开关按钮，调 `api.toggleKillSwitch()`。

`ConfigVersionManager.tsx`：Tabs 切换 risk / execution / opportunity_grade / symbol_rules，每个 Tab 下展示版本列表 + 创建新版本表单 + 激活按钮。

- [ ] **Step 9: 创建 app/settings/page.tsx + 5 个 settings 组件**

`EquityEditor.tsx`：输入账户权益，保存到 user_settings。

`RiskConfigEditor.tsx`：编辑风控配置（max_leverage / min_rr / daily_loss_limit_r 等），创建新版本。

`ExecutionConfigEditor.tsx`：编辑执行配置（margin_mode / allowed_order_types / require_stop_loss 等）。

`OpportunityGradeEditor.tsx`：编辑 A/B/C/BLOCKED 的 max_risk_percent。

`SymbolRulesEditor.tsx`：编辑每个 symbol 的 size_step / price_step / min_size / min_notional / max_leverage / fee_rate。

所有编辑器提交时调 `api.createConfig()` 创建新版本，可选调 `api.activateConfig()` 激活。

- [ ] **Step 10: 启动前后端联调**

```bash
# 终端 1
docker compose up -d postgres
cd apps/api && uv run uvicorn src.app.main:app --reload --port 8000

# 终端 2
cd apps/web && pnpm dev
```

打开 http://localhost:3000 ，验证：
1. 首页重定向到 /plans
2. Navbar 显示 Kill Switch 状态灯（红色，默认开启）
3. Trade Plans 页面可创建计划
4. 创建后点"检查"显示 sizing/risk/decision 三块卡片
5. Risk Center 页面展示配置 + Kill Switch 开关
6. Settings 页面可编辑账户权益 + 各类配置

- [ ] **Step 11: 提交**

```bash
git add apps/web
git commit -m "feat(web): add Trade Plans + Risk Center + Settings pages"
```

---

## Task 11：验收测试与文档

**Files:**
- Modify: `f:\crypto\README.md`（补充运行说明）
- Create: `f:\crypto\apps\api\tests\test_acceptance.py`

- [ ] **Step 1: 写验收测试（对齐设计稿 §7）**

`test_acceptance.py` 覆盖：
- 创建交易计划
- 输入入场/止损/止盈
- 计算风险金额 / 止损距离 / 名义仓位 / 保证金 / 盈亏比
- 输出风控结论
- 保存计划
- 无止损 BLOCK
- 超杠杆 BLOCK
- 风控结果落库
- 精度圆整（rounded_size）
- 当日亏损限制 BLOCK
- 连亏限制 BLOCK
- 冷却期 BLOCK
- Kill Switch BLOCK
- Execution Mode 关闭时 decision-gate BLOCK
- 配置版本激活后生效
- 机会等级 A/B/C/BLOCKED 映射
- decision-gate 五种状态
- system_events 记录

- [ ] **Step 2: 运行全部测试**

Run: `cd f:\crypto && uv run pytest -v`
Expected: 所有测试通过

- [ ] **Step 3: 更新 README.md**

补充：开发环境启动步骤、测试运行命令、项目结构说明、v0.1 验收清单。

- [ ] **Step 4: 最终提交**

```bash
git add .
git commit -m "test: add v0.1 acceptance tests + update README"
```

- [ ] **Step 5: 验收对照**

对照设计稿 §7.1 / §7.2 / §7.3 的所有验收点，逐项确认通过。

---

## 自审记录

**1. Spec 覆盖检查**：
- §1.1 范围全部覆盖（Task 1-5 核心 packages，Task 6-9 API，Task 10 前端，Task 11 验收）
- §1.2 不做项：未涉及
- §1.3 差异说明：account_equity 手动输入（Task 7 user_settings + Task 10 EquityEditor）、symbol rules 配置（Task 8 configs API + Task 10 SymbolRulesEditor）、account_risk_state（Task 6 model + Task 7 seed）
- §2 架构：Task 0 workspace + Task 1-5 packages + Task 6-9 api + Task 10 web
- §3 后端模块设计：Task 1-5 一一对应
- §4 数据库：Task 6 8 张表 + 迁移
- §5 API：Task 7-9 所有端点
- §6 前端：Task 10 3 个页面
- §7 验收：Task 11

**2. 占位符扫描**：无 TBD/TODO，所有步骤都有具体代码或具体指令。

**3. 类型一致性**：packages/shared 定义的枚举和 schema 在所有后续 packages 和 apps/api 中复用，字段名一致（risk_amount / notional_value / rounded_size / risk_reward_ratio 等）。

**4. 已知简化**（实施时按需扩展）：
- Task 6 的 8 个 model 文件只给了 trade_plan.py 完整模板，其余 7 个按设计稿 §4.2 字段定义同样实现
- Task 7 的 seed.py 给了数据结构，具体 dict 内容见设计稿附录 A
- Task 9 的 plan_service.check_plan 给了流程，具体代码按流程实现
- Task 10 前端组件给了职责描述，具体 JSX 按设计稿 §6.2 布局实现

这些简化不影响可执行性，工程师可按设计稿 + 模板完成。
