"""
EDC Launcher service.

This module manages the local lifecycle of EDC connectors by generating
runtime configuration files, certificates, and Docker Compose setups.

It handles:
    - File and certificate generation
    - PostgreSQL database initialization
    - Docker Compose orchestration
    - Docker network creation

These utilities are used when launching managed connectors through
the EDC Studio Backend.
"""

import os
import secrets
import subprocess
from pathlib import Path
import time
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2 import sql
import sqlparse

# -----------------------------------------------------------------------------
# Templates and global configuration
# -----------------------------------------------------------------------------

keystore_password = secrets.token_urlsafe(16)
"""Randomly generated keystore password for EDC connector certificates."""

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


# --- Datasource: default (used by SqlAssetIndex and SqlDataPlaneStore) ---
edc.datasource.default.url=jdbc:postgresql://edc_postgres:{port_postgress}/edc_{type}_{id}
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
    image: itziarmensaupc/connector:0.0.6
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
      - {runtime_path}/{name}/resources/configuration:/app/configuration
      - {runtime_path}/{name}/resources/certs:/app/certs

    environment:
      - EDC_KEYSTORE_PASSWORD={keystore_password}
      - VIRTUAL_HOST={virtual_host}
      - VIRTUAL_PORT={virtual_port}

    networks:
      - {network_name}

networks:
  {network_name}:
    external: true
"""

# -----------------------------------------------------------------------------
# Core utility functions
# -----------------------------------------------------------------------------

def _generate_files(connector: dict, base_path: Path):
    """
    Generates configuration files, certificates, and Docker Compose setup
    for a given EDC connector.

    This function creates:
        - `config.properties` for EDC runtime configuration
        - PKCS#12 certificate keystore (`cert.pfx`)
        - `docker-compose.yml` for launching the connector

    Args:
        connector (dict): MongoDB connector document.
        base_path (Path): Base directory where runtime files are stored.

    Raises:
        RuntimeError: If keytool fails to generate the certificate.
    """
  
    ports = connector["ports"]
    name = connector["name"]
    id = connector["_id"]
    ctype = connector["type"]
    secret = connector["api_key"]
    virtual_host = connector["domain"]

    proxy_public_line = ""
    if ctype == "provider":
        proxy_public_line = f"\nedc.dataplane.proxy.public.endpoint=http://edc-{ctype}-{id}:{ports['public']}/public\n"

    # Create folders
    config_path = base_path / "resources" / "configuration"
    certs_path = base_path / "resources" / "certs"
    config_path.mkdir(parents=True, exist_ok=True)
    certs_path.mkdir(parents=True, exist_ok=True)

    load_dotenv()
    port_postgress=os.getenv("POSTGRES_PORT", 5432)

    # Write config.properties
    config_content = CONFIG_TEMPLATE.format(name=name, type=ctype, id=id, **ports, secret=secret, port_postgress=port_postgress) + proxy_public_line
    (config_path / "config.properties").write_text(config_content)

    # Generate real cert.pfx using keytool
    cert_path = certs_path / "cert.pfx"
    if cert_path.exists():
        cert_path.unlink()
    try:
        subprocess.run([
            "keytool", "-genkeypair",
            "-alias", "private-key",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-keystore", str(cert_path),
            "-storetype", "PKCS12",
            "-storepass", keystore_password,
            "-keypass", keystore_password,
            "-dname", f"CN={id}"
        ], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"keytool failed:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")


    load_dotenv()
    
    # Write docker-compose.yml
    compose_file = base_path / "docker-compose.yml"
    compose_file.write_text(DOCKER_COMPOSE_TEMPLATE.format(
        type=ctype, name=id, **ports, runtime_path=os.getenv("RUNTIME_PATH", "/Volumes/DISK/Projects/Work/EDC/edc_studio_backend/runtime"), keystore_password=keystore_password, 
        virtual_host=virtual_host, virtual_port=ports['http'],
        network_name=os.getenv("NETWORK_NAME", "edc-network")
    ))

def _wait_for_postgres():
    """
    Waits until the PostgreSQL service becomes available.

    The function attempts to connect to PostgreSQL periodically until a timeout
    of 30 seconds is reached.

    Raises:
        TimeoutError: If PostgreSQL is not available within 30 seconds.
    """

    load_dotenv()
    host=os.getenv("POSTGRES_HOST", "localhost")
    port=os.getenv("POSTGRES_PORT", 5432)
    user=os.getenv("POSTGRES_USER", "postgres")
    password=os.getenv("POSTGRES_PASS", "admin")
    timeout=30
    """Espera a que PostgreSQL esté disponible hasta un timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(dbname="postgres", user=user, password=password, host=host, port=port)
            conn.close()
            return True
        except Exception:
            time.sleep(1)
    raise TimeoutError("PostgreSQL no está disponible tras esperar 30 segundos.")

def _run_docker_compose(path: Path, db_name: str):
    """
    Initializes PostgreSQL, prepares the database schema, and starts Docker Compose.

    This function:
        1. Waits for PostgreSQL availability.
        2. Creates a database for the connector if it does not exist.
        3. Executes the initialization SQL script.
        4. Launches the Docker Compose stack for the connector.

    Args:
        path (Path): Path to the connector’s runtime directory.
        db_name (str): Name of the database to create.

    Raises:
        ValueError: If the runtime folder does not exist.
        FileNotFoundError: If `init.sql` is missing.
        Exception: If database creation or Docker startup fails.
    """

    load_dotenv()

    runtime_path = Path("runtime")
    config_path = Path("config")

    if not runtime_path.exists():
        raise ValueError("El directorio 'runtime' no existe.")

    """ # 1. Arrancar PostgreSQL

    port_postgres = os.getenv("POSTGRES_PORT", "5432")
    network_name = os.getenv("NETWORK_NAME", "edc-network")

    compose_file = os.path.join(config_path, "docker-compose.yml")
    with open(compose_file, "r") as f:
        compose = yaml.safe_load(f)
    compose["services"]["postgres"]["networks"] = [network_name]
    compose["networks"] = {network_name: {"external": True}}

    print(f"Arrancando contenedor de PostgreSQL en el puerto {port_postgres}...")
    env = os.environ.copy()
    env["POSTGRES_PORT"] = str(port_postgres)

    subprocess.run(["docker", "compose", "up", "-d"], cwd=config_path, check=True, env=env) """

    # 2. Esperar a que PostgreSQL esté disponible
    print("Esperando a que PostgreSQL esté disponible...")
    _wait_for_postgres()

    # 3. Crear la base de datos si no existe
    try:
        conn = psycopg2.connect(dbname="postgres", user=os.getenv("POSTGRES_USER", "postgres"), password=os.getenv("POSTGRES_PASS", "admin"), host=os.getenv("POSTGRES_HOST", "localhost"))
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
            print(f"Base de datos '{db_name}' creada.")
        else:
            print(f"La base de datos '{db_name}' ya existe. No se crea de nuevo.")
    except Exception as e:
        print(f"Error creando la base de datos: {e}")
        raise

    # 4. Ejecutar init.sql
    init_sql_path = config_path / "init.sql"
    if not init_sql_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo {init_sql_path}")
    try:
        conn = psycopg2.connect(dbname=db_name, user=os.getenv("POSTGRES_USER", "postgres"), password=os.getenv("POSTGRES_PASS", "admin"), host=os.getenv("POSTGRES_HOST", "localhost"))
        cur = conn.cursor()
        with open(init_sql_path, "r") as f:
            script = f.read()
        
        statements = sqlparse.split(script)

        for statement in statements:
            cleaned = statement.strip()
            if cleaned:
                try:
                    cur.execute(cleaned)
                except Exception as e:
                    print(f"⚠️  Error ejecutando: {e}")

        conn.commit()
        cur.close()
        conn.close()
        print("Script init.sql ejecutado correctamente.")

    except Exception as e:
        print(f"Error ejecutando init.sql: {e}")
        raise

    # 5. Arrancar el resto del sistema
    print("Arrancando el resto del sistema...")
    subprocess.run(["docker", "compose", "up", "-d"], cwd=path, check=True)
    print("Sistema arrancado correctamente.")

def _run_docker_compose_down(path: Path):
    """
    Stops and removes Docker Compose services for a connector.

    Args:
        path (Path): Path to the connector’s runtime directory.
    """
    subprocess.run(["docker", "compose", "down"], cwd=path)

def _create_docker_network_if_not_exists(network_name: str):
    """
    Ensures that a given Docker network exists, creating it if necessary.

    Args:
        network_name (str): Name of the Docker network to validate or create.
    """
    result = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    networks = result.stdout.strip().splitlines()
    if network_name not in networks:
        subprocess.run(["docker", "network", "create", network_name], check=True)