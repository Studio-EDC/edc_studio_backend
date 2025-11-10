"""
Policy model definition.

This module defines the data models that represent access and usage
policies in the Eclipse Data Connector (EDC) ecosystem. Policies are
based on the ODRL (Open Digital Rights Language) specification and
describe permissions, prohibitions, and obligations that regulate
how data can be used and shared between connectors.

The models follow a hierarchical structure:
- Operator: defines the comparison operator in a constraint.
- Constraint: specifies a condition (e.g., leftOperand, operator, rightOperand).
- Rule: represents a single permission, prohibition, or obligation.
- PolicyDefinition: groups rules into a complete ODRL policy.
- Policy: top-level model that associates a policy definition with a specific EDC.
"""

from enum import Enum
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class Operator(BaseModel):
    """
    Represents a logical or comparison operator used in constraints.

    Example:
        >>> operator = Operator(id="EQ")
    """

    id: str
    """Identifier of the operator (e.g., 'EQ', 'NEQ', 'GT', 'LT')."""


class Constraint(BaseModel):
    """
    Defines a constraint that applies to a policy rule.

    A constraint expresses a conditional restriction or requirement
    on the application of a rule (e.g., "purpose EQ research").

    Example:
        >>> constraint = Constraint(
        ...     leftOperand="purpose",
        ...     operator=Operator(id="EQ"),
        ...     rightOperand="research"
        ... )
    """

    leftOperand: str
    """Left operand of the constraint (e.g., 'purpose', 'spatial')."""

    operator: Operator
    """Operator defining the relationship between operands."""

    rightOperand: str
    """Right operand or value of the constraint."""

class Action(str, Enum):
    USE = "USE"
    READ = "READ"
    WRITE = "WRITE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    LOG = "LOG"
    NOTIFY = "NOTIFY"
    ANONYMIZE = "ANONYMIZE"


class Rule(BaseModel):
    """
    Defines a single rule in a policy (permission, prohibition, or obligation).

    Example:
        >>> rule = Rule(
        ...     action="USE",
        ...     constraint=[
        ...         Constraint(
        ...             leftOperand="purpose",
        ...             operator=Operator(id="EQ"),
        ...             rightOperand="research"
        ...         )
        ...     ]
        ... )
    """

    action: Action
    """Type of action that the rule allows, forbids, or obliges."""

    constraint: Optional[List[Constraint]] = None
    """Optional list of constraints associated with this rule."""

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v):
        # admite 'odrl:use', 'use', 'USE'…
        if isinstance(v, str):
            v = v.split(":")[-1].upper()
        return v


class PolicyDefinition(BaseModel):
    """
    Defines the complete structure of an ODRL policy.

    Each policy definition may include permissions, prohibitions,
    and obligations, along with metadata such as context and type.

    Example:
        >>> policy_def = PolicyDefinition(
        ...     permission=[
        ...         Rule(action="USE")
        ...     ],
        ...     context="http://www.w3.org/ns/odrl.jsonld",
        ...     type="Set"
        ... )
    """

    permission: Optional[List[Rule]] = None
    """List of allowed actions under this policy."""

    prohibition: Optional[List[Rule]] = None
    """List of forbidden actions under this policy."""

    obligation: Optional[List[Rule]] = None
    """List of required actions under this policy."""

    context: str = Field(default="http://www.w3.org/ns/odrl.jsonld")
    """JSON-LD context for ODRL policy definitions."""

    type: str = Field(default="Set")
    """Type of policy according to ODRL ('Set' by default)."""


class Policy(BaseModel):
    """
    Represents a top-level EDC policy entity.

    A policy associates an EDC connector with a policy definition,
    establishing the rules and constraints for data access and usage.

    Example:
        >>> policy = Policy(
        ...     edc="edc-provider-01",
        ...     policy_id="policy-001",
        ...     policy=PolicyDefinition(permission=[Rule(action="USE")])
        ... )
        >>> print(policy.policy_id)
        policy-001
    """

    edc: str
    """Identifier of the EDC connector associated with this policy."""

    policy_id: str
    """Unique identifier of the policy."""

    policy: PolicyDefinition
    """Full policy definition containing permissions, prohibitions, and obligations."""

    context: dict = Field(
        default={"@vocab": "https://w3id.org/edc/v0.0.1/ns/"},
    )
    """JSON-LD context used for EDC policy vocabulary resolution."""