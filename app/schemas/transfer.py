from pydantic import BaseModel
from typing import Literal, Optional


class TransferResponse(BaseModel):
    id: str
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

class RequestCatalog(BaseModel):
    consumer: str
    provider: str

class NegotitateContract(BaseModel):
    consumer: str
    provider: str
    contract_offer_id: str
    asset: str

class ContractAgreement(BaseModel):
    consumer: str
    id_contract_negotiation: str

class StartTransfer(BaseModel):
    consumer: str
    provider: str
    contract_agreement_id: str

class CheckTransfer(BaseModel):
    consumer: str
    transfer_process_id: str