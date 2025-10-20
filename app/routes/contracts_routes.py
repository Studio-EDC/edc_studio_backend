"""
Contract routes.

This module defines the API endpoints for managing contract definitions
within the EDC Studio Backend. A contract links assets with their
corresponding access and usage policies, enabling regulated data
exchange between provider and consumer connectors.

All endpoints in this module interact with the service layer
(`app.services.contracts_service`) to perform database operations.
"""

from fastapi import APIRouter, HTTPException
from app.models.contract import Contract
from app.services.contracts_service import create_contract, delete_contract, get_contract_by_contract_id_service, get_contracts_by_edc_id, update_contract

router = APIRouter()


@router.post("", status_code=201)
async def create_contract_route(data: Contract):
    """
    Create a new contract definition for a specific EDC connector.

    Args:
        data (Contract): The contract data to be created, including
            asset selection and policy references.

    Returns:
        str: The identifier (`@id`) of the newly created contract.

    Example:
        >>> POST /contracts
        {
            "edc": "edc-provider-01",
            "contract_id": "contract-001",
            "accessPolicyId": "policy-access-01",
            "contractPolicyId": "policy-contract-01",
            "assetsSelector": ["asset-001"]
        }
    """

    inserted_id = await create_contract(data)
    return inserted_id['@id']


@router.get("/by-edc/{edc_id}", response_model=list[Contract])
async def list_contracts_by_edc(edc_id: str):
    """
    Retrieve all contracts associated with a specific EDC connector.

    Args:
        edc_id (str): Identifier of the EDC connector.

    Returns:
        List[Contract]: List of contract definitions belonging to the connector.

    Example:
        >>> GET /contracts/by-edc/edc-provider-01
    """

    return await get_contracts_by_edc_id(edc_id)


@router.get("/by-contract-id/{edc_id}/{contract_id}", response_model=Contract)
async def get_contract_by_contract_id(edc_id: str, contract_id: str):
    """
    Retrieve a specific contract by its identifier and associated EDC.

    Args:
        edc_id (str): Identifier of the EDC connector.
        contract_id (str): Identifier of the contract definition.

    Returns:
        Contract: The contract definition that matches the provided identifiers.

    Example:
        >>> GET /contracts/by-contract-id/edc-provider-01/contract-001
    """

    return await get_contract_by_contract_id_service(edc_id, contract_id)


@router.put("/{edc_id}")
async def update_contract_route(contract: Contract, edc_id: str):
    """
    Update an existing contract definition.

    Args:
        contract (Contract): The updated contract data.
        edc_id (str): Identifier of the EDC connector associated with the contract.

    Returns:
        dict: Confirmation message indicating successful update.

    Raises:
        HTTPException: 404 if the contract does not exist or cannot be updated.

    Example:
        >>> PUT /contracts/edc-provider-01
        {
            "contract_id": "contract-001",
            "accessPolicyId": "policy-access-02",
            "contractPolicyId": "policy-contract-02",
            "assetsSelector": ["asset-002"]
        }
    """

    success = await update_contract(contract, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not updated")
    return {"message": "Asset updated successfully"}


@router.delete("/{contract_id}/{edc_id}")
async def delete_contract_route(contract_id: str, edc_id: str):
    """
    Delete a contract definition.

    Args:
        contract_id (str): Identifier of the contract to delete.
        edc_id (str): Identifier of the EDC connector associated with the contract.

    Returns:
        dict: Confirmation message indicating successful deletion.

    Raises:
        HTTPException: 404 if the contract does not exist or cannot be deleted.

    Example:
        >>> DELETE /contracts/contract-001/edc-provider-01
    """
    
    success = await delete_contract(contract_id, edc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found or not deleted")
    return {"message": "Asset deleted successfully"}