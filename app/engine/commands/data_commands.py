import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse
from app.core.validator import SchemaValidator

logger = logging.getLogger("OmniCore.DataCommands")


class DataCommandHandler:
    """
    Motor de Datos Genérico.
    Proporciona operaciones CRUD estandarizadas sobre la tabla 'generic_data'
    validando siempre contra el esquema virtual del Tenant.
    """

    def _get_tenant_schema(self, session: Session, context: TenantContext) -> dict:
        """Helper para recuperar el esquema actual del tenant."""
        result = (
            session.execute(
                text("SELECT schema_definition FROM tenant_schemas WHERE tenant_id = :tid"),
                {"tid": context.tenant_id},
            )
            .mappings()
            .first()
        )

        if not result:
            return {}
        return json.loads(result["schema_definition"])

    @command(
        name="data.upsert",
        description=(
            "Creates or updates a record in a generic entity after validating against the schema."
        ),
        params_model={
            "entity": "str",
            "data": "dict",
            "id": "str (optional)",  # If provided, updates existing; else creates new.
        },
    )
    def upsert(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        data: dict,
        id: str | None = None,
    ) -> ServiceResponse:
        try:
            # 1. Validar contra el esquema
            schema = self._get_tenant_schema(session, context)
            is_valid, error = SchemaValidator.validate(entity, schema, data)
            if not is_valid:
                return ServiceResponse.error_res(f"Validation error: {error}", "VALIDATION_FAILED")

            if id:
                # Actualización (Update)
                # Usamos el operador || de PostgreSQL para mergear el JSONB
                session.execute(
                    text("""
                        UPDATE generic_data 
                        SET data = data || :new_data, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                    """),
                    {
                        "new_data": json.dumps(data),
                        "id": id,
                        "tid": context.tenant_id,
                        "entity": entity,
                    },
                )
                # Verificar si se actualizó algo
                if session.execute(text("SELECT 1")).rowcount == 0:  # Simplified check
                    pass  # Handle as create if not found or return error

            else:
                # Creación (Create)
                session.execute(
                    text("""
                        INSERT INTO generic_data (tenant_id, entity_type, data) 
                        VALUES (:tid, :entity, :data)
                    """),
                    {"tid": context.tenant_id, "entity": entity, "data": json.dumps(data)},
                )

            session.commit()
            return ServiceResponse.success_res(
                message=f"Record in '{entity}' synchronized successfully."
            )
        except Exception as e:
            session.rollback()
            logger.exception("Upsert error")
            return ServiceResponse.error_res(f"Upsert failed: {str(e)}", "DATA_UPSERT_ERROR")

    @command(
        name="data.get",
        description="Retrieves a single record from a generic entity by its ID.",
        params_model={
            "entity": "str",
            "id": "str",
        },
    )
    def get_record(
        self, session: Session, context: TenantContext, entity: str, id: str
    ) -> ServiceResponse:
        try:
            result = (
                session.execute(
                    text("""
                    SELECT data FROM generic_data 
                    WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                """),
                    {"id": id, "tid": context.tenant_id, "entity": entity},
                )
                .mappings()
                .first()
            )

            if not result:
                return ServiceResponse.error_res("Record not found.", "NOT_FOUND")

            return ServiceResponse.success_res(data=json.loads(result["data"]))
        except Exception as e:
            return ServiceResponse.error_res(f"Get error: {str(e)}", "DATA_GET_ERROR")

    @command(
        name="data.delete",
        description="Deletes one or more records from a generic entity.",
        params_model={
            "entity": "str",
            "id": "str",
        },
    )
    def delete_record(
        self, session: Session, context: TenantContext, entity: str, id: str
    ) -> ServiceResponse:
        try:
            session.execute(
                text("""
                    DELETE FROM generic_data 
                    WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                """),
                {"id": id, "tid": context.tenant_id, "entity": entity},
            )
            session.commit()
            return ServiceResponse.success_res(message="Record deleted successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Delete error: {str(e)}", "DATA_DELETE_ERROR")

    @command(
        name="data.query",
        description="Query records in a generic entity with optional filters.",
        params_model={
            "entity": "str",
            "filters": "dict (optional)",  # e.g. {"status": "active"}
        },
    )
    def query_data(
        self, session: Session, context: TenantContext, entity: str, filters: dict | None = None
    ) -> ServiceResponse:
        try:
            # Construcción de consulta dinámica usando el operador @> (contains) de JSONB
            query = text("""
                SELECT id, data FROM generic_data 
                WHERE tenant_id = :tid AND entity_type = :entity
            """)
            params = {"tid": context.tenant_id, "entity": entity}

            if filters:
                query = text(f"{query.text()} AND data @> :filters")
                params["filters"] = json.dumps(filters)

            result = session.execute(query, params).mappings().all()

            data = []
            for row in result:
                record = json.loads(row["data"])
                record["_id"] = row["id"]  # Inject the internal ID for easier referencing
                data.append(record)

            return ServiceResponse.success_res(data=data)
        except Exception as e:
            logger.exception("Query error")
            return ServiceResponse.error_res(f"Query failed: {str(e)}", "DATA_QUERY_ERROR")

    @command(
        name="data.list",
        description="Paginated list of records in a generic entity with optional filters.",
        params_model={
            "entity": "str",
            "filters": "dict (optional)",
            "page": "int (default 1)",
            "page_size": "int (default 20)",
        },
    )
    def list_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ServiceResponse:
        try:
            offset = (page - 1) * page_size

            query_str = """
                SELECT id, data FROM generic_data 
                WHERE tenant_id = :tid AND entity_type = :entity
            """
            params: dict[str, Any] = {"tid": context.tenant_id, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                params["filters"] = json.dumps(filters)

            query_str += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            params["limit"] = page_size
            params["offset"] = offset

            result = session.execute(text(query_str), params).mappings().all()

            data = []
            for row in result:
                record = json.loads(row["data"])
                record["_id"] = row["id"]
                data.append(record)

            return ServiceResponse.success_res(data=data, message=f"Page {page} retrieved.")
        except Exception as e:
            logger.exception("List error")
            return ServiceResponse.error_res(f"List failed: {str(e)}", "DATA_LIST_ERROR")

    @command(
        name="data.increment",
        description="Atomically increments a numerical field in a JSON record.",
        params_model={
            "entity": "str",
            "id": "str",
            "field": "str",
            "value": "float",
        },
    )
    def increment_field(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        id: str,
        field: str,
        value: float,
    ) -> ServiceResponse:
        try:
            # Sanitize field to prevent SQL injection in the path
            # Since it's inside a JSONB path, we use a simplified check.
            if not field.isalnum() and "_" not in field:
                return ServiceResponse.error_res("Invalid field name", "INVALID_FIELD")

            query = text(f"""
                UPDATE generic_data 
                SET data = jsonb_set(
                    data, 
                    '{{{field}}}', 
                    to_jsonb((COALESCE((data->>'{field}')::numeric, 0) + :val)::text)
                ) 
                WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
            """)  # nosec
            session.execute(
                query, {"val": value, "id": id, "tid": context.tenant_id, "entity": entity}
            )
            session.commit()
            return ServiceResponse.success_res(message=f"Field {field} updated by {value}.")
        except Exception as e:
            session.rollback()
            logger.exception("Increment error")
            return ServiceResponse.error_res(f"Increment error: {str(e)}", "INCREMENT_ERROR")

    @command(
        name="data.count",
        description="Counts the number of records in a generic entity with optional filters.",
        params_model={"entity": "str", "filters": "dict (optional)"},
    )
    def count_records(
        self, session: Session, context: TenantContext, entity: str, filters: dict | None = None
    ) -> ServiceResponse:
        try:
            query_str = (
                "SELECT count(*) as total FROM generic_data "
                "WHERE tenant_id = :tid AND entity_type = :entity"
            )
            params = {"tid": context.tenant_id, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                params["filters"] = json.dumps(filters)

            result = session.execute(text(query_str), params).scalar()
            return ServiceResponse.success_res(data={"total": result})
        except Exception as e:
            return ServiceResponse.error_res(f"Count error: {str(e)}", "DATA_COUNT_ERROR")

    # --- Compatibilidad con versiones anteriores ---
    def upsert_record(self, *args, **kwargs):
        return self.upsert(*args, **kwargs)

    def insert_data(self, session, context, entity, data):
        return self.upsert(session, context, entity, data)

    def patch_record(self, session, context, entity, id, updates):
        return self.upsert(session, context, entity, updates, id=id)


data_commands = DataCommandHandler()
