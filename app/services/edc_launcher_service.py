import os
import subprocess
from pathlib import Path
import time
from app.db.client import get_db
from bson import ObjectId
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql

CONFIG_TEMPLATE = """
edc.hostname=localhost
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

# --- Vault (HashiCorp Dev) ---
edc.vault.hashicorp.url=http://localhost:8200
edc.vault.hashicorp.token=root
edc.vault.hashicorp.secrets.path=secret/data/

# --- Datasource: default (used by SqlAssetIndex and SqlDataPlaneStore) ---
edc.datasource.default.url=jdbc:postgresql://edc-postgres:5432/edc-{type}-{id}
edc.datasource.default.user=postgres
edc.datasource.default.password=admin
edc.datasource.default.driver=org.postgresql.Driver
edc.datasource.default.name=default

web.http.management.auth.type=tokenbased
web.http.management.auth.key={secret}
"""

DOCKER_COMPOSE_TEMPLATE = """
services:
  {type}:
    image: itziarmensaupc/connector:0.0.4
    platform: linux/amd64
    container_name: edc-{type}-{name}
    ports:
      - "{http}:{http}"
      - "{management}:{management}"
      - "{protocol}:{protocol}"
      - "{public}:{public}"
      - "{control}:{control}"
      - "{version}:{version}"
    volumes:
      - ./resources/configuration:/app/configuration

    networks:
      - edc-network

networks:
  edc-network:
    external: true
"""

DOCKER_COMPOSE_TEMPLATE_SQL = """
version: '3.8'

services:
  vault:
    image: hashicorp/vault:1.15
    container_name: edc-vault
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: root
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
    command: server -dev

    networks:
      - edc-network

  postgres:
    image: postgres:15
    container_name: edc-postgres
    environment:
      POSTGRES_DB: edc
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: admin
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

    networks:
      - edc-network

volumes:
  postgres_data:

networks:
  edc-network:
    external: true
"""

def _generate_files(connector: dict, base_path: Path):
  ports = connector["ports"]
  name = connector["name"]
  id = connector["_id"]
  ctype = connector["type"]
  secret = connector["api_key"]

  proxy_public_line = ""
  if ctype == "provider":
      proxy_public_line = f"\nedc.dataplane.proxy.public.endpoint=http://edc-{ctype}-{id}:{ports['public']}/public\n"

  # Create folders
  config_path = base_path / "resources" / "configuration"
  # certs_path = base_path / "resources" / "certs"
  config_path.mkdir(parents=True, exist_ok=True)
  # certs_path.mkdir(parents=True, exist_ok=True)

  # Write config.properties
  config_content = CONFIG_TEMPLATE.format(name=name, type=ctype, id=id, **ports, secret=secret) + proxy_public_line
  (config_path / "config.properties").write_text(config_content)

  # Generate real cert.pfx using keytool
  # cert_path = certs_path / "cert.pfx"
  """ if cert_path.exists():
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
      raise RuntimeError(f"keytool failed:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}") """


  # Write docker-compose.yml
  compose_file = base_path / "docker-compose.yml"
  compose_file.write_text(DOCKER_COMPOSE_TEMPLATE.format(
      type=ctype, name=id, **ports
  ))

  # Write docker-compose.yml sql and vault
  file_sql = Path("runtime") / "docker-compose.yml"
  file_sql.parent.mkdir(parents=True, exist_ok=True)

  if not file_sql.exists():
    file_sql.write_text(DOCKER_COMPOSE_TEMPLATE_SQL)

def _run_docker_compose(path: Path, db_name: str):
  runtime_path = Path("runtime")

  if not runtime_path.exists():
      raise ValueError("SQL path not found")

  # 1. Arrancar PostgreSQL
  try: 
    subprocess.run(["docker", "compose", "up", "-d"], cwd=runtime_path)
    conn = psycopg2.connect(dbname="postgres", user="postgres", password="admin", host="localhost")
    conn.close()
  except Exception as e:
    print(e)

  # 3. Crear la base de datos
  try:
    conn = psycopg2.connect(dbname="postgres", user="postgres", password="admin", host="localhost")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    exists = cur.fetchone()
    if not exists:
      cur.execute(sql.SQL("CREATE DATABASE {}").format(
        sql.Identifier(db_name)
      ))
      print(f"Base de datos '{db_name}' creada.")
    else:
      print(f"La base de datos '{db_name}' ya existe. No se crea de nuevo.")
  except Exception as e:
    print(e)

  # 4. Ejecutar init.sql en la nueva base de datos
  init_sql_path = Path("runtime") / "init.sql"
  with psycopg2.connect(dbname=db_name, user="postgres", password="admin", host="localhost") as conn:
      with conn.cursor() as cur:
          with open(init_sql_path, "r") as f:
              cur.execute(f.read())
              print("Script init.sql ejecutado correctamente.")

  # 5. Arrancar el resto del sistema
  subprocess.run(["docker", "compose", "up", "-d"], cwd=path)

def _run_docker_compose_down(path: Path):
  subprocess.run(["docker", "compose", "down"], cwd=path)

def _create_docker_network_if_not_exists(network_name: str):
    result = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    networks = result.stdout.strip().splitlines()
    if network_name not in networks:
        subprocess.run(["docker", "network", "create", network_name], check=True)