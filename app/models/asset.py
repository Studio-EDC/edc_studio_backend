
from typing import Literal
from pydantic import BaseModel


class Asset(BaseModel):
    asset_id: str
    name: str
    content_type: str
    data_address_name: str
    data_address_type: Literal["HttpData", "File"]
    data_address_proxy: bool
    base_url: str
    edc: str