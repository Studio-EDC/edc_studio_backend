import os
import subprocess
from pathlib import Path
from app.db.client import get_db
from bson import ObjectId

CONFIG_TEMPLATE = """
edc.participant.id={type}
edc.dsp.callback.address=http://edc-{type}-{id}:{protocol}/protocol
web.http.port={http}
web.http.path=/api
web.http.management.port={management}
web.http.management.path=/management
web.http.protocol.port={protocol}
web.http.protocol.path=/protocol
edc.transfer.proxy.token.signer.privatekey.alias=private-key
edc.transfer.proxy.token.verifier.publickey.alias=public-key
web.http.public.port={public}
web.http.public.path=/public
web.http.control.port={control}
web.http.control.path=/control
web.http.version.port={version}
web.http.version.path=/version
edc.dataplane.api.public.baseurl=http://edc-{type}-{id}:{public}/public
"""

DOCKER_COMPOSE_TEMPLATE = """
services:
  {type}:
    image: itziarmensaupc/connector:0.0.1
    platform: linux/amd64
    container_name: edc-{type}-{name}
    ports:
      - "{http}:{http}"
      - "{management}:{management}"
      - "{protocol}:{protocol}"
      - "{public}:{public}"
      - "{control}:{control}"
      - "{version}:{version}"
    environment:
      - EDC_KEYSTORE_PASSWORD={keystore_password}
    volumes:
      - ./resources/configuration:/app/configuration
      - ./resources/certs:/app/certs

    networks:
      - edc-network

networks:
  edc-network:
    external: true
"""

def _generate_files(connector: dict, base_path: Path):
    ports = connector["ports"]
    name = connector["name"]
    id = connector["_id"]
    ctype = connector["type"]
    password = connector["keystore_password"]

    # Create folders
    config_path = base_path / "resources" / "configuration"
    certs_path = base_path / "resources" / "certs"
    config_path.mkdir(parents=True, exist_ok=True)
    certs_path.mkdir(parents=True, exist_ok=True)

    # Write config.properties
    config_file = config_path / "config.properties"
    config_file.write_text(CONFIG_TEMPLATE.format(name=name, type=ctype, id=id, **ports))

    # Generate real cert.pfx using keytool
    cert_path = certs_path / "cert.pfx"
    if cert_path.exists():
        cert_path.unlink()
    try:
        result = subprocess.run([
            "keytool", "-genkeypair",
            "-alias", "private-key",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-keystore", str(cert_path),
            "-storetype", "PKCS12",
            "-storepass", password,
            "-keypass", password,
            "-dname", f"CN={id}"
        ], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"keytool failed:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")


    # Write docker-compose.yml
    compose_file = base_path / "docker-compose.yml"
    compose_file.write_text(DOCKER_COMPOSE_TEMPLATE.format(
        type=ctype, name=id, keystore_password=password, **ports
    ))

def _run_docker_compose(path: Path):
    subprocess.run(["docker", "compose", "up", "-d"], cwd=path)

def _run_docker_compose_down(path: Path):
    subprocess.run(["docker", "compose", "down"], cwd=path)

def _create_docker_network_if_not_exists(network_name: str):
    result = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    networks = result.stdout.strip().splitlines()
    if network_name not in networks:
        subprocess.run(["docker", "network", "create", network_name], check=True)