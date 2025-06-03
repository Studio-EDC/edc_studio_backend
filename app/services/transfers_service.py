from fastapi import HTTPException
import httpx
from app.db.client import get_db
from bson import ObjectId
import subprocess
from pathlib import Path

from app.models.transfer import Transfer

async def catalog_request_service(consumer_id: str, provider_id: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await catalog_request_curl(consumer, provider)
    

async def catalog_request_curl(consumer: dict, provider: dict):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        protocol_port = provider["ports"]["protocol"]
        management_url = f"http://localhost:{management_port}/management/v3/catalog/request"
        protocol_url = f"http://edc-provider-{provider['_id']}:{protocol_port}/protocol"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/catalog/request"
        protocol_url = f"{provider['endpoints_url']['protocol']}"
    else:
        raise ValueError("Invalid connector mode")
    
    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "counterPartyAddress": protocol_url,  
        "protocol": "dataspace-protocol-http"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Catalog request failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

async def negotiate_contract_service(consumer_id: str, provider_id: str, contract_offer_id: str, asset: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await negotiate_contract_curl(consumer, provider, contract_offer_id, asset)

async def negotiate_contract_curl(consumer: dict, provider: dict, contract_offer_id: str, asset: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        protocol_port = provider["ports"]["protocol"]
        management_url = f"http://localhost:{management_port}/management/v3/contractnegotiations"
        protocol_url = f"http://edc-provider-{provider['_id']}:{protocol_port}/protocol"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/contractnegotiations"
        protocol_url = f"{provider['endpoints_url']['protocol']}"
    else:
        raise ValueError("Invalid connector mode")
    
    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "ContractRequest",
        "counterPartyAddress": protocol_url,
        "protocol": "dataspace-protocol-http",
        "policy": {
            "@context": "http://www.w3.org/ns/odrl.jsonld",
            "@id": contract_offer_id,
            "@type": "Offer",
            "assigner": "provider",
            "target": asset
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Catalog request failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

async def get_contract_agreement_service(consumer_id: str, id_contract_negotiation: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await get_contract_agreement_curl(consumer, id_contract_negotiation)

async def get_contract_agreement_curl(consumer: dict, id_contract_negotiation: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        management_url = f"http://localhost:{management_port}/management/v3/contractnegotiations/{id_contract_negotiation}"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/contractnegotiations/{id_contract_negotiation}"
    else:
        raise ValueError("Invalid connector mode")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Catalog request failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

def start_http_server_service():
    project_root = Path(__file__).resolve().parent.parent
    dockerfile_path = project_root / "util" / "http-request-logger"

    try:
        result = subprocess.check_output(["docker", "ps", "--filter", "name=http-logger", "--filter", "status=running", "-q"])
        if result.strip():
            print("El contenedor 'http-logger' ya está corriendo.")
            return
    except subprocess.CalledProcessError:
        pass  

    try:
        result = subprocess.check_output(["docker", "ps", "-a", "--filter", "name=http-logger", "--filter", "status=exited", "-q"])
        if result.strip():
            subprocess.run(["docker", "start", "http-logger"], check=True)
            print("Contenedor 'http-logger' iniciado.")
            return
    except subprocess.CalledProcessError:
        pass

    subprocess.run(["docker", "build", "-t", "http-request-logger", str(dockerfile_path)], check=True)
    subprocess.run([
        "docker", "run", "-d", "--name", "http-logger", "--network", "edc-network", "-p", "4000:4000", "http-request-logger"
    ], check=True)
    print("Contenedor 'http-logger' creado y ejecutado.")

def stop_http_server_service():
    subprocess.run(["docker", "rm", "-f", "http-logger"], check=True)

async def start_transfer_service(consumer_id: str, provider_id: str, contract_agreement_id: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await start_transfer_curl(consumer, provider, contract_agreement_id)

async def start_transfer_curl(consumer: dict, provider: dict, contract_agreement_id: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        protocol_port = provider["ports"]["protocol"]
        management_url = f"http://localhost:{management_port}/management/v3/transferprocesses"
        protocol_url = f"http://edc-provider-{provider['_id']}:{protocol_port}/protocol"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/transferprocesses"
        protocol_url = f"{provider['endpoints_url']['protocol']}"
    else:
        raise ValueError("Invalid connector mode")
    
    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "TransferRequestDto",
        "connectorId": "provider",
        "counterPartyAddress": protocol_url,
        "contractId": contract_agreement_id,
        "protocol": "dataspace-protocol-http",
        "transferType": "HttpData-PUSH",
        "dataDestination": {
            "type": "HttpData",
            "baseUrl": "http://http-logger:4000/api/consumer/store"
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Start transfer failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

async def check_transfer_service(consumer_id: str, transfer_process_id: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await check_transfer_curl(consumer, transfer_process_id)

async def check_transfer_curl(consumer: dict, transfer_process_id: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        management_url = f"http://localhost:{management_port}/management/v3/transferprocesses/{transfer_process_id}"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/transferprocesses/{transfer_process_id}"
    else:
        raise ValueError("Invalid connector mode")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Start transfer failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

async def create_transfer_service(data: Transfer) -> str:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(data.consumer)})
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    provider = await db["connectors"].find_one({"_id": ObjectId(data.provider)})
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    asset = await db["assets"].find_one({"_id": ObjectId(data.asset)})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    transfer_dict = data.model_dump(by_alias=True)
    transfer_dict["consumer"] = consumer["_id"]
    transfer_dict["provider"] = provider["_id"]
    transfer_dict["asset"] = asset["_id"]

    result = await db["transfers"].insert_one(transfer_dict)
    return str(result.inserted_id)

async def get_all_transfers_service():
    db = get_db()
    transfers_cursor = db["transfers"].find()
    transfers = []

    async for transfer in transfers_cursor:
        transfer["id"] = str(transfer["_id"])
        del transfer["_id"]

        if "consumer" in transfer and isinstance(transfer["consumer"], ObjectId):
            consumer = await db["connectors"].find_one({"_id": transfer["consumer"]})
            transfer["consumer"] = convert_objectids(consumer) if consumer else None

        if "provider" in transfer and isinstance(transfer["provider"], ObjectId):
            provider = await db["connectors"].find_one({"_id": transfer["provider"]})
            transfer["provider"] = convert_objectids(provider) if provider else None

        if "asset" in transfer and isinstance(transfer["asset"], ObjectId):
            asset = await db["assets"].find_one({"_id": transfer["asset"]})
            transfer["asset"] = convert_objectids(asset) if asset else None

        transfers.append(transfer)

    return transfers

def convert_objectids(doc: dict) -> dict:
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        else:
            result[k] = v
    if "_id" in doc:
        result["id"] = str(doc["_id"])
    return result

async def start_transfer_service_pull(consumer_id: str, provider_id: str, contract_agreement_id: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})
    provider = await db["connectors"].find_one({"_id": ObjectId(provider_id)})

    if not consumer or not provider:
        raise ValueError("Consumer or provider connector not found")

    return await start_transfer_curl_pull(consumer, provider, contract_agreement_id)

async def start_transfer_curl_pull(consumer: dict, provider: dict, contract_agreement_id: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        protocol_port = provider["ports"]["protocol"]
        management_url = f"http://localhost:{management_port}/management/v3/transferprocesses"
        protocol_url = f"http://edc-provider-{provider['_id']}:{protocol_port}/protocol"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/transferprocesses"
        protocol_url = f"{provider['endpoints_url']['protocol']}"
    else:
        raise ValueError("Invalid connector mode")
    
    payload = {
        "@context": {
            "@vocab": "https://w3id.org/edc/v0.0.1/ns/"
        },
        "@type": "TransferRequestDto",
        "connectorId": "provider",
        "counterPartyAddress": protocol_url,
        "contractId": contract_agreement_id,
        "protocol": "dataspace-protocol-http",
        "transferType": "HttpData-PULL"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(management_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Start transfer failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise

async def check_transfer_data_pull_service(consumer_id: str, transfer_process_id: str) -> dict:
    db = get_db()

    consumer = await db["connectors"].find_one({"_id": ObjectId(consumer_id)})

    if not consumer:
        raise ValueError("Consumer or provider connector not found")

    return await check_transfer_data_curl_pull(consumer, transfer_process_id)

async def check_transfer_data_curl_pull(consumer: dict, transfer_process_id: str):
    if consumer["mode"] == "managed":
        management_port = consumer["ports"]["management"]
        management_url = f"http://localhost:{management_port}/management/v3/edrs/{transfer_process_id}/dataaddress"
    elif consumer["mode"] == "remote":
        management_url = f"{consumer['endpoints_url']['management'].rstrip('/')}/management/v3/edrs/{transfer_process_id}/dataaddress"
    else:
        raise ValueError("Invalid connector mode")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(management_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            print(f"Start transfer failed: {exc.response.status_code}")
            print(f"Response text: {exc.response.text}")
            raise