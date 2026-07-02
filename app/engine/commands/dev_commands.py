import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse

logger = logging.getLogger("OmniCore.DevCommands")


class DevCommandHandler:
    """
    Gestor de Comandos para Desarrolladores.
    Permite la definición y gestión de Blueprints (Mapas de Operaciones)
    que rigen el comportamiento de los Tenants.
    """

    @command(
        name="dev.blueprint.define",
        description=(
            "Defines or updates the Blueprint (JSONB Map) " "for the current tenant's workspace."
        ),
        params_model={
            "developer_name": "str",
            "map_definition": "dict",
        },
        required_level="TENANT",
    )
    def define_blueprint(
        self, session: Session, context: TenantContext, developer_name: str, map_definition: dict
    ) -> ServiceResponse:
        try:
            # 1. Find the blueprint linked to the current tenant
            result = session.execute(
                text("SELECT blueprint_id FROM tenants WHERE id = :tid"),
                {"tid": context.tenant_id},
            ).fetchone()

            if not result or not result[0]:
                return ServiceResponse.error_res(
                    "No blueprint assigned to this tenant. "
                    "Please use 'dev.setup.workspace' first.",
                    "NO_BLUEPRINT_ASSIGNED",
                )

            bp_id = result[0]

            # 2. Update the blueprint definition and the developer name
            session.execute(
                text(
                    "UPDATE system_blueprints SET map_definition = :map, "
                    "developer_name = :dev WHERE id = :id"
                ),
                {"map": json.dumps(map_definition), "dev": developer_name, "id": bp_id},
            )

            # Clear cache to ensure the new blueprint is used immediately
            from app.core.blueprints import blueprint_manager

            blueprint_manager.clear_cache(context.tenant_id)

            session.commit()
            return ServiceResponse.success_res(
                message=f"Blueprint for tenant {context.tenant_id} updated successfully."
            )
        except Exception as e:
            session.rollback()
            if "system_blueprints" in str(e).lower():
                return ServiceResponse.error_res(
                    "Infrastructure not initialized. "
                    "Please run 'system.init_infra' to create required tables.",
                    "INFRASTRUCTURE_NOT_READY",
                )
            logger.exception("Error defining blueprint")
            return ServiceResponse.error_res(f"Blueprint error: {str(e)}", "BLUEPRINT_DEFINE_ERROR")

    @command(
        name="dev.blueprint.assign",
        description="Assigns a specific Blueprint to a tenant.",
        params_model={
            "tenant_id": "str",
            "blueprint_id": "str",
        },
        required_level="SYSTEM",
    )
    def assign_blueprint(
        self, session: Session, context: TenantContext, tenant_id: str, blueprint_id: str
    ) -> ServiceResponse:
        try:
            # Validar que el blueprint exista
            bp_exists = session.execute(
                text("SELECT 1 FROM system_blueprints WHERE id = :bid"), {"bid": blueprint_id}
            ).scalar()

            if not bp_exists:
                return ServiceResponse.error_res(
                    f"Blueprint {blueprint_id} not found.", "BLUEPRINT_NOT_FOUND"
                )

            # Asignar al tenant
            session.execute(
                text("UPDATE tenants SET blueprint_id = :bid WHERE id = :tid"),
                {"bid": blueprint_id, "tid": tenant_id},
            )
            session.commit()
            return ServiceResponse.success_res(
                message=f"Blueprint {blueprint_id} assigned to tenant {tenant_id}."
            )
        except Exception as e:
            session.rollback()
            logger.exception("Error assigning blueprint")
            return ServiceResponse.error_res(f"Assign error: {str(e)}", "BLUEPRINT_ASSIGN_ERROR")

    @command(
        name="dev.blueprint.list",
        description="Lists all available Blueprints in the system.",
        params_model={},
        required_level="SYSTEM",
    )
    def list_blueprints(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            result = (
                session.execute(
                    text("SELECT id, developer_name, created_at FROM system_blueprints")
                )
                .mappings()
                .all()
            )

            blueprints = [
                {
                    "id": row["id"],
                    "developer": row["developer_name"],
                    "created_at": str(row["created_at"]),
                }
                for row in result
            ]

            return ServiceResponse.success_res(
                data=blueprints, message=f"Retrieved {len(blueprints)} blueprints."
            )
        except Exception as e:
            if "system_blueprints" in str(e).lower():
                return ServiceResponse.error_res(
                    "Infrastructure not initialized. "
                    "Please run 'system.init_infra' to create required tables.",
                    "INFRASTRUCTURE_NOT_READY",
                )
            logger.exception("Error listing blueprints")
            return ServiceResponse.error_res(f"List error: {str(e)}", "BLUEPRINT_LIST_ERROR")

    @command(
        name="dev.cache.clear",
        description=(
            "Clears the blueprint cache for the current tenant "
            "to force a refresh from the database."
        ),
        params_model={},
        required_level="TENANT",
    )
    def clear_tenant_cache(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            from app.core.blueprints import blueprint_manager

            blueprint_manager.clear_cache(context.tenant_id)
            return ServiceResponse.success_res(
                message=(
                    f"Blueprint cache cleared for tenant {context.tenant_id}. "
                    "New changes will be applied."
                )
            )
        except Exception as e:
            logger.exception("Error clearing cache")
            return ServiceResponse.error_res(f"Cache error: {str(e)}", "CACHE_CLEAR_ERROR")


dev_commands = DevCommandHandler()
