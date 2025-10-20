"""
Policy routes.

This module defines the API endpoints for managing policies in the
EDC Studio Backend. Policies are based on the ODRL (Open Digital Rights
Language) specification and describe permissions, prohibitions, and
obligations for data usage between connectors.

All endpoints in this module interact with the service layer
(`app.services.policies_service`) to perform CRUD operations on
EDC policy definitions.
"""

from fastapi import APIRouter, HTTPException
from app.models.policy import Policy
from app.services.policies_service import create_policy, delete_policy, get_policies_by_edc_id, get_policy_by_policy_id_service

router = APIRouter()


@router.post("", status_code=201)
async def create_policy_route(data: Policy):
    """
    Create a new policy definition for a given EDC connector.

    Args:
        data (Policy): The policy data to create, including permissions,
            prohibitions, obligations, and context.

    Returns:
        str: The identifier (`@id`) of the newly created policy.

    Example:
        >>> POST /policies
        {
            "edc": "edc-provider-01",
            "policy_id": "policy-001",
            "policy": {
                "permission": [
                    {"action": "USE"}
                ],
                "context": "http://www.w3.org/ns/odrl.jsonld",
                "type": "Set"
            }
        }
    """

    inserted_id = await create_policy(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=list[Policy])
async def list_policies_by_edc(edc_id: str):
    """
    Retrieve all policies associated with a specific EDC connector.

    Args:
        edc_id (str): Identifier of the EDC connector.

    Returns:
        List[Policy]: List of policy definitions registered under the given connector.

    Example:
        >>> GET /policies/by-edc/edc-provider-01
    """

    return await get_policies_by_edc_id(edc_id)

@router.get("/by-policy-id/{edc_id}/{policy_id}", response_model=Policy)
async def get_policy_by_policy_id(edc_id: str, policy_id: str):
    """
    Retrieve a specific policy by its identifier within a given EDC connector.

    Args:
        edc_id (str): Identifier of the EDC connector.
        policy_id (str): Identifier of the policy definition.

    Returns:
        Policy: The policy that matches the given EDC and policy ID.

    Example:
        >>> GET /policies/by-policy-id/edc-provider-01/policy-001
    """

    return await get_policy_by_policy_id_service(edc_id, policy_id)

@router.delete("/{policy_id}/{edc_id}")
async def delete_asset_route(policy_id: str, edc_id: str):
    """
    Delete a policy definition associated with a specific EDC connector.

    Args:
        policy_id (str): Identifier of the policy to delete.
        edc_id (str): Identifier of the EDC connector.

    Returns:
        dict: Confirmation message indicating successful deletion.

    Raises:
        HTTPException: 404 if the policy does not exist or cannot be deleted.

    Example:
        >>> DELETE /policies/policy-001/edc-provider-01
    """
    
    await delete_policy(policy_id, edc_id)
    return {"message": "Asset deleted successfully"}
