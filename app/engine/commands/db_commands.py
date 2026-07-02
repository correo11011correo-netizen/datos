import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse

logger = logging.getLogger("OmniCore.DBCommands")


class DBCommandHandler:
    """
    Gestor de Infraestructura de Base de Datos.
    Se encarga de la creación de tablas y mantenimiento del esquema.
    """

    @command(
        name="system.init_infra",
        description="Initializes the core system tables and the universal generic data store.",
        params_model={},
        required_level="SYSTEM",
    )
    def init_infra(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            # 1. Core System Tables
            core_tables = {
                "system_blueprints": (
                    "CREATE TABLE IF NOT EXISTS system_blueprints "
                    "(id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
                    "developer_name TEXT NOT NULL, "
                    "map_definition JSONB NOT NULL, "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                ),
                "tenants": (
                    "CREATE TABLE IF NOT EXISTS tenants "
                    "(id UUID PRIMARY KEY, name TEXT, plan TEXT DEFAULT 'free', "
                    "blueprint_id UUID REFERENCES system_blueprints(id))"
                ),
                "api_keys": (
                    "CREATE TABLE IF NOT EXISTS api_keys "
                    "(id SERIAL PRIMARY KEY, token TEXT UNIQUE, "
                    "tenant_id UUID REFERENCES tenants(id))"
                ),
                "plans": (
                    "CREATE TABLE IF NOT EXISTS plans "
                    "(plan_id TEXT PRIMARY KEY, name TEXT, price FLOAT, features JSONB)"
                ),
                "audit_logs": (
                    "CREATE TABLE IF NOT EXISTS audit_logs "
                    "(id SERIAL PRIMARY KEY, command TEXT, params JSONB, "
                    "executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                ),
                "dev_reports": (
                    "CREATE TABLE IF NOT EXISTS dev_reports "
                    "(id SERIAL PRIMARY KEY, "
                    "tenant_id UUID REFERENCES tenants(id), "
                    "category TEXT, title TEXT, description TEXT, "
                    "status TEXT DEFAULT 'open', "
                    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                ),
            }

            for sql in core_tables.values():
                session.execute(text(sql))

            # Ensure tenants table has blueprint_id if it already existed
            session.execute(
                text(
                    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
                    "blueprint_id UUID REFERENCES system_blueprints(id)"
                )
            )

            # 2. The Universal Generic Store
            session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS generic_data (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID REFERENCES tenants(id),
                    entity_type TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )

            # Index for high-performance filtering by tenant and entity type
            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_generic_data_tenant_type "
                    "ON generic_data(tenant_id, entity_type)"
                )
            )

            session.commit()
            return ServiceResponse.success_res(
                message=(
                    "Infrastructure initialized with Blueprint support. "
                    "Universal data store ready."
                )
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Init error: {str(e)}", "INIT_ERROR")


db_commands = DBCommandHandler()
