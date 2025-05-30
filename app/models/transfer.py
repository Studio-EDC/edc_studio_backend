from pydantic import BaseModel
from typing import List, Dict


class Transfer(BaseModel):
    consumer: str
    provider: str
    asset: str
    has_policy_id: str
    negotiate_contract_id: str
    contract_agreement_id: str