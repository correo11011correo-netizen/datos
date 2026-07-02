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

            session.execute(
                text(
                    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "
                    "blueprint_id UUID REFERENCES system_blueprints(id)"
                )
            )

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

            session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_generic_data_tenant_type "
                    "ON generic_data(tenant_id, entity_type)"
                )
            )

            session.commit()
            return ServiceResponse.success_res(
                message="Infrastructure initialized with Blueprint support. Universal data store ready."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Init error: {str(e)}", "INIT_ERROR")

    @command(
        name="system.tenant.list",
        description="Lists all registered tenants in the system.",
        params_model={},
        required_level="SYSTEM",
    )
    def list_tenants(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            result = session.execute(text("SELECT id, name, plan FROM tenants")).mappings().all()
            return ServiceResponse.success_res(data=[dict(row) for row in result])
        except Exception as e:
            return ServiceResponse.error_res(f"List error: {str(e)}", "TENANT_LIST_ERROR")

    @command(
        name="system.tenant.entities",
        description="Lists all entity types stored for a specific tenant.",
        params_model={"tenant_id": "str"},
        required_level="SYSTEM",
    )
    def list_tenant_entities(
        self, session: Session, context: TenantContext, tenant_id: str
    ) -> ServiceResponse:
        try:
            result = (
                session.execute(
                    text("SELECT DISTINCT entity_type FROM generic_data WHERE tenant_id = :tid"),
                    {"tid": tenant_id},
                )
                .scalars()
                .all()
            )
            return ServiceResponse.success_res(data=result)
        except Exception as e:
            return ServiceResponse.error_res(f"Entities error: {str(e)}", "ENTITY_LIST_ERROR")

    @command(
        name="system.db.format",
        description="Wipes all data from the universal store and tenants. Irreversible.",
        params_model={},
        required_level="SYSTEM",
    )
    def format_db(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            print("\n[RAW EVENT] STARTING DATABASE FORMATTING")

            tables = ["generic_data", "tenants", "api_keys", "dev_reports"]
            for table in tables:
                print(f"[RAW EVENT] Executing: TRUNCATE TABLE {table} CASCADE")
                session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))

            session.commit()
            print("[RAW EVENT] Transaction committed.")

            # --- VERIFICATION STEP ---
            print("[RAW EVENT] Verifying wipe...")
            verification_failed = False
            for table in tables:
                count = session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                print(f"[RAW EVENT] Table {table} count: {count}")
                if count > 0:
                    verification_failed = True

            if verification_failed:
                print("[RAW EVENT] CRITICAL: Wipe verification failed. Data still exists.")
                return ServiceResponse.error_res(
                    "Format command executed but verification failed: some data persists.",
                    "FORMAT_VERIFICATION_FAILED",
                )

            print("[RAW EVENT] DATABASE FORMATTED SUCCESSFULLY\n")
            return ServiceResponse.success_res(message="System database formatted successfully.")
        except Exception as e:
            session.rollback()
            print(f"[RAW EVENT] ERROR during format: {str(e)}")
            return ServiceResponse.error_res(f"Format error: {str(e)}", "FORMAT_ERROR")

    @command(
        name="system.tenant.create",
        description="Creates a new tenant and generates a unique API key.",
        params_model={"name": "str", "plan": "str (optional)", "blueprint_id": "str (optional)"},
        required_level="SYSTEM",
    )
    def create_tenant(
        self,
        session: Session,
        context: TenantContext,
        name: str,
        plan: str = "free",
        blueprint_id: str | None = None,
    ) -> ServiceResponse:
        try:
            import uuid

            tid = str(uuid.uuid4())
            # 1. Create Tenant
            session.execute(
                text(
                    "INSERT INTO tenants (id, name, plan, blueprint_id) VALUES (:id, :name, :plan, :bid)"
                ),
                {"id": tid, "name": name, "plan": plan, "bid": blueprint_id},
            )
            # 2. Create API Key
            import secrets

            token = secrets.token_urlsafe(32)
            session.execute(
                text("INSERT INTO api_keys (token, tenant_id) VALUES (:token, :tid)"),
                {"token": token, "tid": tid},
            )
            session.commit()
            return ServiceResponse.success_res(
                data={"tenant_id": tid, "api_key": token},
                message=f"Tenant '{name}' created successfully.",
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Creation error: {str(e)}", "TENANT_CREATE_ERROR")


db_commands = DBCommandHandler()
