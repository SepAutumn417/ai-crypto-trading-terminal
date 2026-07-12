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
    reason: str | None = None  # P0-5: 审计原因（激活/解除时记录）


class ExecutionModeRequest(BaseModel):
    enabled: bool


class UserSettingsOut(BaseModel):
    execution_enabled: bool
    kill_switch: bool
    account_equity: Decimal | None
    mode: str
