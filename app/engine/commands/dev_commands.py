import json
import logging
import uuid

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
        description="Defines or updates a Blueprint (JSONB Map) for a specific developer.",
        params_model={
            "developer_name": "str",
            "map_definition": "dict",
        },
        required_level="SYSTEM",
    )
    def define_blueprint(
        self, session: Session, context: TenantContext, developer_name: str, map_definition: dict
    ) -> ServiceResponse:
        try:
            # Buscamos si el desarrollador ya tiene un mapa activo
            result = (
                session.execute(
                    text("SELECT id FROM system_blueprints WHERE developer_name = :dev"),
                    {"dev": developer_name},
                )
                .mappings()
                .first()
            )

            if result:
                # Actualizamos el mapa existente
                session.execute(
                    text("UPDATE system_blueprints SET map_definition = :map WHERE id = :id"),
                    {"map": json.dumps(map_definition), "id": result["id"]},
                )
                message = f"Blueprint for developer '{developer_name}' updated successfully."
            else:
                # Creamos un nuevo mapa
                bp_id = str(uuid.uuid4())
                session.execute(
                    text("""
                        INSERT INTO system_blueprints (id, developer_name, map_definition) 
                        VALUES (:id, :dev, :map)
                    """),
                    {"id": bp_id, "dev": developer_name, "map": json.dumps(map_definition)},
                )
                message = (
                    f"New Blueprint for developer '{developer_name}' created with ID: {bp_id}."
                )

            session.commit()
            return ServiceResponse.success_res(message=message)
        except Exception as e:
            session.rollback()
            # Capturar error de tabla inexistente para dar guía clara al desarrollador
            if "system_blueprints" in str(e).lower():
                return ServiceResponse.error_res(
                    "Infrastructure not initialized. Please run 'system.init_infra' to create required tables.",
                    "INFRASTRUCTURE_NOT_READY"
                )
            logger.exception("Error defining blueprint")
            return ServiceResponse.error_res(f"Blueprint error: {str(e)}", "BLUEPRINT_DEFINE_ERROR")

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
            # Capturar error de tabla inexistente para dar guía clara al desarrollador
            if "system_blueprints" in str(e).lower():
                return ServiceResponse.error_res(
                    "Infrastructure not initialized. Please run 'system.init_infra' to create required tables.",
                    "INFRASTRUCTURE_NOT_READY"
                )
            logger.exception("Error listing blueprints")
            return ServiceResponse.error_res(f"List error: {str(e)}", "BLUEPRINT_LIST_ERROR")


dev_commands = DevCommandHandler()
