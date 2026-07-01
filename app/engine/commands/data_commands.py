import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.blueprints import blueprint_manager
from app.core.context import TenantContext
from app.core.decorators import command
from app.core.executor import map_executor
from app.core.types import ServiceResponse

logger = logging.getLogger("OmniCore.DataCommands")


class DataCommandHandler:
    """
    Motor de Datos Basado en Mapas.
    Proporciona operaciones CRUD y ejecución de lógica dinámica sobre JSONB
    siguiendo el Blueprint asignado al Tenant.
    """

    @command(
        name="data.upsert",
        description=(
            "Creates or updates a record in a generic entity. Validates entity existence in the blueprint."
        ),
        params_model={
            "entity": "str",
            "data": "dict",
            "id": "str (optional)",
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
            # 1. Validar que la entidad exista en el mapa del desarrollador
            blueprint = blueprint_manager.get_blueprint_for_tenant(session, context.tenant_id)
            if not blueprint or entity not in blueprint.get("entities", {}):
                return ServiceResponse.error_res(
                    f"Entity '{entity}' is not defined in the assigned Blueprint.",
                    "BLUEPRINT_ENTITY_NOT_FOUND",
                )

            if id:
                # Actualización (Merge JSONB)
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
            else:
                # Creación
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
        name="data.operate",
        description="Executes a dynamic operation (sum, subtract, etc.) defined in the Blueprint map.",
        params_model={
            "entity": "str",
            "id": "str",
            "operation": "str",
            "value": "float",
        },
    )
    def operate(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        id: str,
        operation: str,
        value: float,
    ) -> ServiceResponse:
        try:
            # 1. Recuperar el mapa del tenant
            blueprint = blueprint_manager.get_blueprint_for_tenant(session, context.tenant_id)
            if not blueprint:
                return ServiceResponse.error_res(
                    "No Blueprint assigned to this tenant.", "BLUEPRINT_NOT_FOUND"
                )

            # 2. Ejecutar la operación mediante el MapExecutor
            success = map_executor.execute_operation(
                session=session,
                tenant_id=context.tenant_id,
                entity_type=entity,
                record_id=id,
                operation_name=operation,
                value=value,
                blueprint=blueprint,
            )

            if not success:
                return ServiceResponse.error_res(
                    f"Operation '{operation}' failed or is not defined in the map for entity '{entity}'.",
                    "OPERATION_FAILED",
                )

            return ServiceResponse.success_res(
                message=f"Operation '{operation}' executed successfully."
            )
        except Exception as e:
            session.rollback()
            logger.exception("Operation error")
            return ServiceResponse.error_res(f"Operation failed: {str(e)}", "DATA_OPERATE_ERROR")

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

            data = result["data"]
            if isinstance(data, str):
                data = json.loads(data)

            return ServiceResponse.success_res(data=data)
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
            "filters": "dict (optional)",
        },
    )
    def query_data(
        self, session: Session, context: TenantContext, entity: str, filters: dict | None = None
    ) -> ServiceResponse:
        try:
            query_str = """
                SELECT id, data FROM generic_data 
                WHERE tenant_id = :tid AND entity_type = :entity
            """
            params = {"tid": context.tenant_id, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                params["filters"] = json.dumps(filters)

            result = session.execute(text(query_str), params).mappings().all()

            data = []
            for row in result:
                record = row["data"]
                if isinstance(record, str):
                    record = json.loads(record)

                if record:
                    record["_id"] = row["id"]
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
                record = row["data"]
                if isinstance(record, str):
                    record = json.loads(record)

                if record:
                    record["_id"] = row["id"]
                    data.append(record)

            return ServiceResponse.success_res(data=data, message=f"Page {page} retrieved.")
        except Exception as e:
            logger.exception("List error")
            return ServiceResponse.error_res(f"List failed: {str(e)}", "DATA_LIST_ERROR")

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
