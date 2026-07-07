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
