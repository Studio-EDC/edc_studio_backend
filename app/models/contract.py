from pydantic import BaseModel
from typing import List, Dict


class Contract(BaseModel):
    edc: str
    contract_id: str 
    accessPolicyId: str
    contractPolicyId: str
    assetsSelector: List[str]
    context: Dict[str, str] = {
        "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
    }