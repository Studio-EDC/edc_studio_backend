from typing import Any
from pydantic import BaseModel


class Policy(BaseModel):
    edc: str
    policy: dict[str, Any]