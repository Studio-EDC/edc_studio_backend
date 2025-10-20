# EDC Studio Backend

EDC Studio Backend is a **FastAPI-based system** that manages the lifecycle of EDC (Eclipse Data Connector) components.  
It allows users to create and manage connectors, assets, policies, and data transfers through a REST API and a web interface.

---

## 📚 Documentation

The full project documentation is available on **Read the Docs**:

👉 [https://edc-studio-backend.readthedocs.io/en/latest/](https://edc-studio-backend.readthedocs.io/en/latest/)

[![Documentation Status](https://readthedocs.org/projects/edc-studio-backend/badge/?version=latest)](https://edc-studio-backend.readthedocs.io/en/latest/?badge=latest)

---

## ⚙️ Main Features

- Management of **EDC connectors** (provider & consumer)
- Creation of **assets** and **policies** based on ODRL structure
- Execution and monitoring of **data transfers** (push/pull)
- **MongoDB** integration for persistence
- **Docker Compose** deployment of connectors