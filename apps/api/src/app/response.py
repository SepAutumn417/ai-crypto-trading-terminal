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