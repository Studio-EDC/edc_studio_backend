from pydantic import BaseModel
from typing import List, Dict, Literal, Optional


class Transfer(BaseModel):
    consumer: str
    provider: str
    asset: str
    has_policy_id: str
    negotiate_contract_id: str
    contract_agreement_id: str
    transfer_process_id: str
    transfer_flow: Literal["push", "pull"]
    authorization: Optional[str] = None
    endpoint: Optional[str] = None