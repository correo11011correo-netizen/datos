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
                "tenants": "CREATE TABLE IF NOT EXISTS tenants (id UUID PRIMARY KEY, name TEXT, plan TEXT DEFAULT 'free')",
                "api_keys": "CREATE TABLE IF NOT EXISTS api_keys (id SERIAL PRIMARY KEY, token TEXT UNIQUE, tenant_id UUID REFERENCES tenants(id))",
                "plans": "CREATE TABLE IF NOT EXISTS plans (plan_id TEXT PRIMARY KEY, name TEXT, price FLOAT, features JSONB)",
                "audit_logs": "CREATE TABLE IF NOT EXISTS audit_logs (id SERIAL PRIMARY KEY, command TEXT, params JSONB, executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
                "tenant_schemas": "CREATE TABLE IF NOT EXISTS tenant_schemas (tenant_id UUID PRIMARY KEY REFERENCES tenants(id), schema_definition JSONB NOT NULL)",
            }

            for table, sql in core_tables.items():
                session.execute(text(sql))

            # 2. The Universal Generic Store
            # This table replaces all 'entity_{name}' tables.
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
                    "CREATE INDEX IF NOT EXISTS idx_generic_data_tenant_type ON generic_data(tenant_id, entity_type)"
                )
            )

            session.commit()
            return ServiceResponse.success_res(
                message="Infrastructure initialized. Universal data store ready."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Init error: {str(e)}", "INIT_ERROR")


db_commands = DBCommandHandler()
