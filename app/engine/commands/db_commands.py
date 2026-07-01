import json
from typing import Any

from app.core.context import TenantContext
from app.core.db import execute_raw
from app.core.decorators import command
from app.core.redis_core import clear_cache
from app.core.types import ServiceResponse


class DbCommandHandler:
    """
    Gestor de Comandos de Infraestructura de Base de Datos.
    Provee control sobre el esquema, metadatos y ciclo de vida del sistema.
    """

    @command(
        name="create_tenant",
        description="Creates a new tenant platform in the system.",
        params_model={"name": "string", "plan": "string"},
        required_level="SYSTEM",
    )
    async def create_tenant(
        self,
        session: Any,
        context: TenantContext,
        name: str,
        plan: str = "free",
    ) -> ServiceResponse:
        if not name:
            return ServiceResponse.error_res("Tenant name is required", "MISSING_PARAMS")

        tenant_id = execute_raw(
            "INSERT INTO tenants (name, plan) VALUES (:name, :plan) RETURNING id",
            {"name": name, "plan": plan},
        ).scalar()

        return ServiceResponse.success_res(
            data={"tenant_id": tenant_id}, message=f"Tenant '{name}' created successfully."
        )

    @command(
        name="create_api_key",
        description="Generates a new API key for a specific tenant.",
        params_model={"tenant_id": "string", "label": "string"},
        required_level="SYSTEM",
    )
    async def create_api_key(
        self,
        session: Any,
        context: TenantContext,
        tenant_id: str,
        label: str = "Default Key",
    ) -> ServiceResponse:
        if not tenant_id:
            return ServiceResponse.error_res("tenant_id is required", "MISSING_PARAMS")

        import secrets

        token = secrets.token_urlsafe(32)

        execute_raw(
            "INSERT INTO api_keys (tenant_id, token, label) VALUES (:tid, :token, :label)",
            {"tid": tenant_id, "token": token, "label": label},
        )

        return ServiceResponse.success_res(
            data={"token": token, "tenant_id": tenant_id}, message="API Key generated successfully."
        )

    @command(
        name="list_tenants",
        description="Lists all registered tenants in the system.",
        params_model={},
        required_level="SYSTEM",
    )
    async def list_tenants(
        self,
        session: Any,
        context: TenantContext,
    ) -> ServiceResponse:
        try:
            result = execute_raw(
                "SELECT id, name, plan, status, created_at FROM tenants ORDER BY created_at DESC"
            ).fetchall()
            data = [
                {
                    "id": row[0],
                    "name": row[1],
                    "plan": row[2],
                    "status": row[3],
                    "created_at": str(row[4]),
                }
                for row in result
            ]
            return ServiceResponse.success_res(data=data, message="Tenants retrieved.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error retrieving tenants: {str(e)}", "DB_ERROR")

    @command(
        name="list_api_keys",
        description="Lists all API keys generated in the system.",
        params_model={},
        required_level="SYSTEM",
    )
    async def list_api_keys(
        self,
        session: Any,
        context: TenantContext,
    ) -> ServiceResponse:
        try:
            result = execute_raw(
                "SELECT id, tenant_id, token, label, created_at FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
            data = [
                {
                    "id": row[0],
                    "tenant_id": row[1],
                    "token": row[2],
                    "label": row[3],
                    "created_at": str(row[4]),
                }
                for row in result
            ]
            return ServiceResponse.success_res(data=data, message="API Keys retrieved.")
        except Exception as e:
            return ServiceResponse.error_res(f"Error retrieving API keys: {str(e)}", "DB_ERROR")

    @command(
        name="list_entities",
        description="Lists all generic entities registered in the system.",
        params_model={},
        required_level="SYSTEM",
    )
    async def list_entities(
        self,
        session: Any,
        context: TenantContext,
    ) -> ServiceResponse:
        # Verificar si la tabla existe primero para evitar Error 500 post-formateo
        check_table = execute_raw(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'metadata_entities')"
        ).scalar()

        if not check_table:
            return ServiceResponse.success_res(
                data=[], message="No entities found (system is currently empty)."
            )

        result = execute_raw(
            "SELECT name, schema FROM metadata_entities ORDER BY name ASC"
        ).fetchall()
        return ServiceResponse.success_res(
            data=[{"name": row[0], "schema": row[1]} for row in result],
            message="Entities retrieved.",
        )

    @command(
        name="seed_system",
        description="Populates the system with basic initial data.",
        params_model={"seed_data": "dict"},
        required_level="SYSTEM",
    )
    async def seed_system(
        self,
        session: Any,
        context: TenantContext,
        seed_data: dict | None = None,
    ) -> ServiceResponse:
        if not seed_data:
            return ServiceResponse.error_res("seed_data is required", "MISSING_PARAMS")

        for entity_name, records in seed_data.items():
            # We use the internal logic to create and insert
            await self.create_entity(session, context, name=entity_name)
            for record in records:
                await self.insert_data(session, context, entity=entity_name, data=record)

        return ServiceResponse.success_res(message="System seeded successfully.")

    @command(
        name="format_all",
        description="NUCLEAR COMMAND: Total wipe of PostgreSQL public schema and Redis.",
        required_level="SYSTEM",
    )
    async def format_all(self, session: Any, context: TenantContext) -> ServiceResponse:
        execute_raw("""
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """)
        clear_cache()
        return ServiceResponse.success_res(message="System fully formatted.")

    @command(
        name="init_system",
        description="Initializes the generic structure and seeds the baseline admin configuration.",
        required_level="SYSTEM",
    )
    async def init_system(self, session: Any, context: TenantContext) -> ServiceResponse:
        # 1. Core Metadata Table
        execute_raw("""
            CREATE TABLE IF NOT EXISTS metadata_entities (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                schema JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Multi-tenant Security Infrastructure
        execute_raw("""
            CREATE TABLE IF NOT EXISTS tenants (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                plan TEXT DEFAULT 'free',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        execute_raw("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                token TEXT UNIQUE NOT NULL,
                label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Seed Baseline Data
        baseline_data = {
            "roles": [
                {"name": "SuperAdmin", "permissions": ["all"], "description": "Acceso total"},
                {
                    "name": "Editor",
                    "permissions": ["read", "write"],
                    "description": "Gestión de datos",
                },
            ],
            "admins": [
                {
                    "username": "root_admin",
                    "role": "SuperAdmin",
                    "status": "active",
                    "created_at": "2026-06-30",
                },
            ],
        }
        await self.seed_system(session, context, seed_data=baseline_data)

        # 4. Create Default Root Tenant and Token
        # We use a fixed UUID for the root tenant to ensure consistency
        root_tenant_id = "00000000-0000-0000-0000-000000000000"
        execute_raw(
            "INSERT INTO tenants (id, name, plan, status) VALUES "
            "(:id, :name, :plan, :status) ON CONFLICT (id) DO NOTHING",
            {"id": root_tenant_id, "name": "Root Admin", "plan": "enterprise", "status": "active"},
        )

        # Default token from settings (or a fallback)
        from app.core.config import settings

        execute_raw(
            "INSERT INTO api_keys (tenant_id, token, label) VALUES "
            "(:tid, :token, :label) ON CONFLICT (token) DO NOTHING",
            {
                "tid": root_tenant_id,
                "token": settings.ADMIN_SECRET_TOKEN,
                "label": "Main Admin Token",
            },
        )

        return ServiceResponse.success_res(message="System initialized with multi-tenant security.")

    @command(
        name="create_entity",
        description="Creates a new generic entity table.",
        params_model={"name": "string", "schema": "dict"},
    )
    async def create_entity(
        self,
        session: Any,
        context: TenantContext,
        name: str,
        schema: dict | None = None,
    ) -> ServiceResponse:
        if not name:
            return ServiceResponse.error_res("Entity name is required", "MISSING_PARAMS")

        execute_raw(
            "INSERT INTO metadata_entities (name, schema) VALUES (:name, :schema)",
            {"name": name, "schema": json.dumps(schema or {})},
        )

        table_name = f"entity_{name.lower().replace(' ', '_')}"
        execute_raw(f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id TEXT,
                entity_id INTEGER REFERENCES metadata_entities(id),
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        return ServiceResponse.success_res(message=f"Entity '{name}' created successfully.")

    @command(
        name="insert_data",
        description="Inserts a JSON record into a generic entity.",
        params_model={"entity": "string", "data": "dict"},
    )
    async def insert_data(
        self,
        session: Any,
        context: TenantContext,
        entity: str,
        data: dict,
    ) -> ServiceResponse:
        if not entity or data is None:
            return ServiceResponse.error_res("Entity name and data are required", "MISSING_PARAMS")

        res = execute_raw(
            "SELECT id FROM metadata_entities WHERE name = :name", {"name": entity}
        ).fetchone()
        if not res:
            return ServiceResponse.error_res(f"Entity {entity} not found", "NOT_FOUND")

        entity_id = res[0]
        table_name = f"entity_{entity.lower().replace(' ', '_')}"
        safe_table = f'"{table_name}"'

        execute_raw(
            f"INSERT INTO {safe_table} (entity_id, data) " f"VALUES (:eid, :data)",  # nosec
            {"eid": entity_id, "data": json.dumps(data)},
        )
        return ServiceResponse.success_res(message="Data inserted successfully.")

    @command(
        name="query_entity",
        description="Queries records from a generic entity.",
        params_model={"entity": "string"},
    )
    async def query_entity(
        self,
        session: Any,
        context: TenantContext,
        entity: str,
    ) -> ServiceResponse:
        if not entity:
            return ServiceResponse.error_res("Entity name is required", "MISSING_PARAMS")

        table_name = f"entity_{entity.lower().replace(' ', '_')}"
        safe_table = f'"{table_name}"'

        query = "SELECT data FROM " + safe_table + " ORDER BY created_at DESC"  # nosec
        result = execute_raw(query).fetchall()
        return ServiceResponse.success_res(data=[row[0] for row in result])


db_commands = DbCommandHandler()
