"""
API routes for federated participants.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.security import get_current_user
from app.models.federated_participant import FederatedParticipant
from app.schemas.federated_participant import (
    DidDocumentResponse,
    DidValidationResponse,
    FederatedParticipantResponse,
    ManualRegistrationResponse,
)
from app.services.federated_participants_service import (
    create_federated_participant,
    delete_federated_participant,
    generate_did_document,
    generate_manual_registration,
    get_federated_participant,
    list_federated_participants,
    resolve_public_did_document,
    update_federated_participant,
    validate_did_web,
)

router = APIRouter()
public_router = APIRouter()


@router.post("", status_code=201)
async def create_federated_participant_route(
    data: FederatedParticipant, current_user: dict = Depends(get_current_user)
):
    inserted_id = await create_federated_participant(data, current_user)
    return {"id": inserted_id}


@router.get("", response_model=list[FederatedParticipantResponse])
async def list_federated_participants_route(
    current_user: dict = Depends(get_current_user),
):
    return await list_federated_participants(current_user)


@router.get("/{participant_id}", response_model=FederatedParticipantResponse)
async def get_federated_participant_route(
    participant_id: str, current_user: dict = Depends(get_current_user)
):
    return await get_federated_participant(participant_id, current_user)


@router.put("/{participant_id}")
async def update_federated_participant_route(
    participant_id: str,
    data: FederatedParticipant,
    current_user: dict = Depends(get_current_user),
):
    await update_federated_participant(participant_id, data, current_user)
    return {"message": "Federated participant updated successfully"}


@router.delete("/{participant_id}")
async def delete_federated_participant_route(
    participant_id: str, current_user: dict = Depends(get_current_user)
):
    await delete_federated_participant(participant_id, current_user)
    return {"message": "Federated participant deleted successfully"}


@router.get("/{participant_id}/did-document", response_model=DidDocumentResponse)
async def generate_did_document_route(
    participant_id: str, current_user: dict = Depends(get_current_user)
):
    return await generate_did_document(participant_id, current_user)


@router.get(
    "/{participant_id}/manual-registration",
    response_model=ManualRegistrationResponse,
)
async def generate_manual_registration_route(
    participant_id: str, current_user: dict = Depends(get_current_user)
):
    return await generate_manual_registration(participant_id, current_user)


@router.get("/{participant_id}/validate-did", response_model=DidValidationResponse)
async def validate_did_route(
    participant_id: str, current_user: dict = Depends(get_current_user)
):
    return await validate_did_web(participant_id, current_user)


@public_router.get("/.well-known/did.json", include_in_schema=False)
async def get_root_did_document_route(request: Request):
    did_document = await resolve_public_did_document(
        request.headers.get("host", ""),
        [],
    )
    return JSONResponse(content=did_document, media_type="application/did+ld+json")


@public_router.get("/{did_path:path}/did.json", include_in_schema=False)
async def get_path_did_document_route(did_path: str, request: Request):
    path_segments = [segment for segment in did_path.split("/") if segment]
    if not path_segments or path_segments == [".well-known"]:
        raise HTTPException(status_code=404, detail="DID document not found")

    did_document = await resolve_public_did_document(
        request.headers.get("host", ""),
        path_segments,
    )
    return JSONResponse(content=did_document, media_type="application/did+ld+json")
