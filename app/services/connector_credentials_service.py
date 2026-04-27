"""
Credential bundle import helpers for managed connectors.

This service validates a ZIP bundle downloaded from UPCxels/edc-manager,
stores the extracted credentials under the connector runtime folder, and
persists a summary status on the connector document.
"""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, UploadFile

from app.db.client import get_db

MAX_BUNDLE_SIZE = 5 * 1024 * 1024  # 5 MB

REQUIRED_CREDENTIAL_FILES = {
    "participantjson": "participant.json",
    "legalrnjson": "legalRN.json",
    "membershipjson": "membership.json",
    "termsconditionsjson": "terms&conditions.json",
}


def _normalize_archive_name(name: str) -> str:
    filename = PurePosixPath(name or "").name.strip().lower()
    return "".join(char for char in filename if char.isalnum())


def _safe_upload_name(name: str | None) -> str:
    filename = PurePosixPath(name or "credentials.zip").name.strip()
    return filename or "credentials.zip"


def _extract_string(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return None


def _extract_issuer_id(payload: dict[str, Any]) -> str | None:
    issuer = payload.get("issuer")
    if isinstance(issuer, dict):
        return _extract_string(issuer.get("id") or issuer.get("@id"))
    return _extract_string(issuer)


def _extract_subject_id(payload: dict[str, Any]) -> str | None:
    subject = payload.get("credentialSubject")
    if isinstance(subject, dict):
        return _extract_string(subject.get("id") or subject.get("@id"))
    if isinstance(subject, list):
        for item in subject:
            if isinstance(item, dict):
                found = _extract_string(item.get("id") or item.get("@id"))
                if found:
                    return found
    return None


def _extract_credential_type(payload: dict[str, Any]) -> str | None:
    raw_type = payload.get("type")
    if isinstance(raw_type, str):
        return raw_type.strip() or None
    if isinstance(raw_type, list):
        for item in raw_type:
            if not isinstance(item, str):
                continue
            if item != "VerifiableCredential":
                return item.strip() or None
        for item in raw_type:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _build_manifest_payload(identity_hub: dict[str, Any]) -> dict[str, Any]:
    manifest = dict(identity_hub)
    imported_at = manifest.get("imported_at")
    if isinstance(imported_at, datetime):
        manifest["imported_at"] = imported_at.isoformat()
    return manifest


def _runtime_paths(connector_id: str) -> dict[str, Path]:
    identity_root = Path("runtime") / "identity-hub" / "participants" / connector_id
    return {
        "identity_root": identity_root,
        "credentials_dir": identity_root / "credentials",
        "imports_dir": identity_root / "imports",
        "shared_credentials_dir": Path("runtime") / "identity-hub" / "shared" / "credentials",
        "vault_bootstrap_dir": Path("runtime") / "identity-hub" / "vault-bootstrap",
    }


def _ensure_identity_directories(connector_id: str) -> dict[str, Path]:
    paths = _runtime_paths(connector_id)
    for path in paths.values():
        if path.suffix:
            continue
        path.mkdir(parents=True, exist_ok=True)
    return paths


async def import_connector_credentials_bundle(
    connector_id: str,
    current_user: dict,
    file: UploadFile,
) -> dict[str, Any]:
    db = get_db()
    connector = await db["connectors"].find_one({"_id": ObjectId(connector_id)})
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if connector.get("mode") != "managed":
        raise HTTPException(
            status_code=400,
            detail="Credential import is only supported for managed connectors",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty credential bundle")
    if len(content) > MAX_BUNDLE_SIZE:
        raise HTTPException(status_code=413, detail="Credential bundle is too large")

    upload_name = _safe_upload_name(file.filename)
    files_by_name: dict[str, dict[str, Any]] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue

                normalized = _normalize_archive_name(entry.filename)
                if normalized not in REQUIRED_CREDENTIAL_FILES:
                    continue

                with archive.open(entry) as handle:
                    try:
                        payload = json.load(handle)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Credential file '{entry.filename}' is not valid JSON",
                        ) from exc

                canonical_name = REQUIRED_CREDENTIAL_FILES[normalized]
                files_by_name[canonical_name] = {
                    "payload": payload,
                    "summary": {
                        "file_name": canonical_name,
                        "credential_type": _extract_credential_type(payload),
                        "credential_id": _extract_string(payload.get("id")),
                        "issuer_id": _extract_issuer_id(payload),
                        "subject_id": _extract_subject_id(payload),
                    },
                }
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

    missing = [
        canonical
        for canonical in REQUIRED_CREDENTIAL_FILES.values()
        if canonical not in files_by_name
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Credential bundle is missing required files: {', '.join(missing)}",
        )

    subject_ids = {
        item["summary"]["subject_id"]
        for item in files_by_name.values()
        if item["summary"].get("subject_id")
    }
    if len(subject_ids) > 1:
        raise HTTPException(
            status_code=400,
            detail="Credential bundle contains multiple participant DIDs",
        )

    federated_participant = await db["federated_participants"].find_one(
        {"connector_id": connector_id}
    )
    expected_did = None
    if federated_participant:
        expected_did = _extract_string(federated_participant.get("participant_did"))

    participant_context_did = next(iter(subject_ids), None) or expected_did
    if expected_did and participant_context_did and expected_did != participant_context_did:
        raise HTTPException(
            status_code=400,
            detail="Credential bundle DID does not match the federated participant DID",
        )

    now = datetime.now(timezone.utc)
    username = _extract_string(current_user.get("username")) or "unknown"
    paths = _ensure_identity_directories(connector_id)

    shutil.rmtree(paths["credentials_dir"], ignore_errors=True)
    paths["credentials_dir"].mkdir(parents=True, exist_ok=True)

    for canonical_name, data in files_by_name.items():
        target = paths["credentials_dir"] / canonical_name
        target.write_text(json.dumps(data["payload"], indent=2), encoding="utf-8")

    for stale_file in paths["shared_credentials_dir"].glob(f"{connector_id}-*.json"):
        stale_file.unlink(missing_ok=True)

    for canonical_name, data in files_by_name.items():
        shared_target = paths["shared_credentials_dir"] / f"{connector_id}-{canonical_name}"
        shared_target.write_text(json.dumps(data["payload"], indent=2), encoding="utf-8")

    bundle_target = paths["imports_dir"] / "credentials.zip"
    bundle_target.write_bytes(content)

    identity_hub = {
        "enabled": True,
        "vault_enabled": True,
        "participant_context_did": participant_context_did,
        "bundle_file_name": upload_name,
        "imported_at": now,
        "imported_by": username,
        "credential_count": len(files_by_name),
        "credentials": [data["summary"] for data in files_by_name.values()],
        "runtime_prepared": True,
        "restart_required": connector.get("state") == "running",
        "last_error": None,
    }

    manifest = _build_manifest_payload(identity_hub)
    (paths["identity_root"] / "manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    (paths["vault_bootstrap_dir"] / "credentials-manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    await db["connectors"].update_one(
        {"_id": ObjectId(connector_id)},
        {"$set": {"identity_hub": identity_hub}},
    )

    identity_hub["imported_at"] = now.isoformat()
    return identity_hub
