from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Operator(BaseModel):
    id: str


class Constraint(BaseModel):
    leftOperand: str
    operator: Operator
    rightOperand: str


class Rule(BaseModel):
    action: Literal["USE", "READ", "WRITE", "MODIFY", "DELETE", "LOG", "NOTIFY", "ANONYMIZE"]
    constraint: Optional[List[Constraint]] = None


class PolicyDefinition(BaseModel):
    permission: Optional[List[Rule]] = None
    prohibition: Optional[List[Rule]] = None
    obligation: Optional[List[Rule]] = None
    context: str = Field(default="http://www.w3.org/ns/odrl.jsonld")
    type: str = Field(default="Set")


class Policy(BaseModel):
    edc: str
    policy_id: str
    policy: PolicyDefinition
    context: dict = Field(
        default={"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
    )