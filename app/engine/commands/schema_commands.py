import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse


class SchemaCommandHandler:
    """
    Gestor de Esquemas Virtuales.
    Permite a cada Tenant definir su propia estructura de 'tablas' y campos
    dentro de la base de datos genérica.
    """

    @command(
        name="schema.define",
        description="Defines the virtual schema for the current tenant (tables and their fields).",
        params_model={
            "schema": "dict",  # e.g., {"products": {"name": "text", "price": "float"}}
        },
    )
    def define_schema(
        self, session: Session, context: TenantContext, schema: dict
    ) -> ServiceResponse:
        try:
            # Guardamos el esquema en una tabla dedicada 'tenant_schemas'
            # Usamos el tenant_id como llave primaria
            session.execute(
                text("""
                    INSERT INTO tenant_schemas (tenant_id, schema_definition) 
                    VALUES (:tid, :schema)
                    ON CONFLICT (tenant_id) 
                    DO UPDATE SET schema_definition = EXCLUDED.schema_definition
                """),
                {"tid": context.tenant_id, "schema": json.dumps(schema)},
            )
            session.commit()
            return ServiceResponse.success_res(message="Virtual schema updated successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Schema error: {str(e)}", "SCHEMA_DEFINE_ERROR")

    @command(
        name="schema.get",
        description="Retrieves the virtual schema definition for the current tenant.",
        params_model={},
    )
    def get_schema(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            result = (
                session.execute(
                    text("SELECT schema_definition FROM tenant_schemas WHERE tenant_id = :tid"),
                    {"tid": context.tenant_id},
                )
                .mappings()
                .first()
            )

            if not result:
                return ServiceResponse.error_res(
                    "No schema defined for this tenant.", "SCHEMA_NOT_FOUND"
                )

            return ServiceResponse.success_res(
                data=json.loads(result["schema_definition"]),
                message="Schema retrieved successfully.",
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Schema error: {str(e)}", "SCHEMA_GET_ERROR")


schema_commands = SchemaCommandHandler()
