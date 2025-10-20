EDC Studio Backend Documentation
================================

**EDC Studio Backend** is a RESTful API built with *FastAPI* and *MongoDB*, designed to automate the lifecycle management of **Eclipse Dataspace Connectors (EDC)**.  
It enables secure and efficient data exchange between providers and consumers in a federated dataspace ecosystem.

The backend is part of the **EDC Studio** suite, which provides a complete environment for managing dataspace connectors, assets, and policies without using the terminal.

Main Features
--------------

- Create and configure **EDC connectors** (provider / consumer).
- Manage **assets**, **policies**, and **data transfers**.
- Launch, monitor, and stop EDC instances in Docker.
- Execute data transfers in **PUSH** and **PULL** modes.
- Retrieve catalogs and manage contract agreements.
- Store connector and transfer metadata in MongoDB.

.. note::
   This backend operates as the core service of **EDC Studio**, supporting graphical tools and dashboards for managing EDC components in a user-friendly way.

----

.. toctree::
   :maxdepth: 2
   :caption: Contents

   app

----

**Author:** Itziar Mensa Minguito  

**Version:** 1.0  

**License:** MIT  

**© 2025 Itziar Mensa Minguito. All rights reserved.**
