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
