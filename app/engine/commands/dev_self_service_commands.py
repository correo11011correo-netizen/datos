import logging
import secrets
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse

logger = logging.getLogger("OmniCore.DevSelfService")


class DeveloperSelfServiceHandler:
    """
    Gestor de Auto-Servicio para Desarrolladores.
    Permite a los desarrolladores crear sus propios espacios de trabajo autónomos.
    """

    @command(
        name="dev.setup.workspace",
        description=(
            "Creates a new isolated workspace for a developer, including "
            "Tenant, API Token, and a default Blueprint."
        ),
        params_model={
            "developer_name": "str",
            "workspace_name": "str",
        },
        required_level="TENANT",
    )
    def setup_workspace(
        self, session: Session, context: TenantContext, developer_name: str, workspace_name: str
    ) -> ServiceResponse:
        try:
            # 1. Crear el Blueprint básico (vacío)
            blueprint_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO system_blueprints (id, developer_name, map_definition) 
                    VALUES (:id, :dev, :map)
                """),
                {"id": blueprint_id, "dev": developer_name, "map": "{}"},
            )

            # 2. Crear el Tenant vinculado al Blueprint
            tenant_id = str(uuid.uuid4())
            session.execute(
                text("""
                    INSERT INTO tenants (id, name, blueprint_id, plan) 
                    VALUES (:id, :name, :bid, 'free')
                """),
                {"id": tenant_id, "name": workspace_name, "bid": blueprint_id},
            )

            # 3. Generar Token API único para este Tenant
            api_token = f"sk_{secrets.token_urlsafe(32)}"
            session.execute(
                text("INSERT INTO api_keys (token, tenant_id) VALUES (:token, :tid)"),
                {"token": api_token, "tid": tenant_id},
            )

            session.commit()

            return ServiceResponse.success_res(
                message=f"Workspace '{workspace_name}' created successfully for {developer_name}.",
                data={
                    "tenant_id": tenant_id,
                    "api_token": api_token,
                    "blueprint_id": blueprint_id,
                    "instructions": (
                        "Use the provided api_token to authenticate your future requests. "
                        "You can now define your blueprint using 'dev.blueprint.define'."
                    ),
                },
            )
        except Exception as e:
            session.rollback()
            logger.exception("Error during workspace setup")
            return ServiceResponse.error_res(f"Setup error: {str(e)}", "WORKSPACE_SETUP_ERROR")


dev_self_service_commands = DeveloperSelfServiceHandler()
