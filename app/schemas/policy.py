from typing import Any
from pydantic import BaseModel


class PolicyResponse(BaseModel):
    id: str
    edc: str
    policy: dict[str, Any]