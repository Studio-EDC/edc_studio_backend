from pydantic import BaseModel
from typing import List, Dict


class TransferResponse(BaseModel):
    id: str
    consumer: str
    provider: str
    asset: str
    has_policy_id: str
    negotiate_contract_id: str
    contract_agreement_id: str

class RequestCatalog(BaseModel):
    consumer: str
    provider: str