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
