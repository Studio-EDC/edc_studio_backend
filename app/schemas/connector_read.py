from pydantic import BaseModel
from typing import Optional, Literal
from app.models.connector import PortConfig

class ConnectorResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    type: Literal["provider", "consumer"]
    ports: Optional[PortConfig]
    state: Literal["running", "stopped"]
    mode: Literal["managed", "remote"]