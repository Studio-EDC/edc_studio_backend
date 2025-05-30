from pydantic import BaseModel, Field
from typing import List, Dict


class ContractResponse(BaseModel):
    id: str
    edc: str
    contract_id: str
    accessPolicyId: str
    contractPolicyId: str
    assetsSelector: List[str]
    context: Dict[str, str] = Field(
        default={"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
    )