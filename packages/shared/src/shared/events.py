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
