from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class OperatorResponse(BaseModel):
    id: str


class ConstraintResponse(BaseModel):
    leftOperand: str
    operator: OperatorResponse
    rightOperand: str


class RuleResponse(BaseModel):
    action: Literal["USE", "READ", "WRITE", "MODIFY", "DELETE", "LOG", "NOTIFY", "ANONYMIZE"]
    constraint: Optional[List[ConstraintResponse]] = None


class PolicyDefinitionResponse(BaseModel):
    permission: Optional[List[RuleResponse]] = None
    prohibition: Optional[List[RuleResponse]] = None
    obligation: Optional[List[RuleResponse]] = None
    context: str = Field(default="http://www.w3.org/ns/odrl.jsonld")
    type: str = Field(default="Set")


class PolicyResponse(BaseModel):
    id: str  # MongoDB _id convertido a string
    edc: str
    policy_id: str
    policy: PolicyDefinitionResponse
    context: dict = Field(
        default={"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
    )