from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    success: bool
    data: T
    message: str = "ok"


def create_success_response(data: T, message: str = "ok") -> StandardResponse[T]:
    return StandardResponse(success=True, data=data, message=message)
