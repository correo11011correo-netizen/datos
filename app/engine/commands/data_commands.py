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

    def _get_effective_tid(self, context: TenantContext, params: dict) -> str:
        """
        Determines the tenant ID to use for the operation.
        If impersonate_tid is provided and the current user is root, it uses that.
        """
        impersonate_tid = params.get("impersonate_tid")
        if impersonate_tid:
            if context.tenant_id == "00000000-0000-0000-0000-000000000000":
                return impersonate_tid
            # If not root, impersonation is forbidden
            raise ValueError(
                json.dumps(
                    {
                        "error": "FORBIDDEN",
                        "message": "Impersonation is restricted to system administrators.",
                        "hint": "Use your own API key for your tenant's data.",
                    }
                )
            )
        return context.tenant_id

    @command(
        name="data.upsert",
        description=(
            "Creates or updates a record in a generic entity. "
            "Supports updates via primary ID or a unique key in the data."
        ),
        params_model={
            "entity": "str",
            "data": "dict",
            "id": "str (optional)",
            "unique_key": "str (optional)",
            "unique_value": "any (optional)",
            "impersonate_tid": "str (optional)",
        },
    )
    def upsert(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        data: dict,
        id: str | None = None,
        unique_key: str | None = None,
        unique_value: Any | None = None,
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)

            # 1. Validar que la entidad exista en el mapa del desarrollador
            blueprint = blueprint_manager.get_blueprint_for_tenant(session, tid)
            if not blueprint or entity not in blueprint.get("entities", {}):
                return ServiceResponse.error_res(
                    f"Entity '{entity}' is not defined in the assigned Blueprint for tenant {tid}.",
                    "BLUEPRINT_ENTITY_NOT_FOUND",
                )

            # --- Resolve Identity ---
            target_id = id
            if not target_id and unique_key and unique_value is not None:
                # Search for the record ID using the unique key in JSONB
                unique_filter = {unique_key: unique_value}
                res = session.execute(
                    text("""
                        SELECT id FROM generic_data 
                        WHERE tenant_id = :tid AND entity_type = :entity AND data @> :filter 
                        LIMIT 1
                    """),
                    {
                        "tid": tid,
                        "entity": entity,
                        "filter": json.dumps(unique_filter),
                    },
                ).scalar()
                target_id = res

            if target_id:
                # Actualización (Merge JSONB)
                session.execute(
                    text("""
                        UPDATE generic_data 
                        SET data = data || :new_data, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                    """),
                    {
                        "new_data": json.dumps(data),
                        "id": target_id,
                        "tid": tid,
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
                    {"tid": tid, "entity": entity, "data": json.dumps(data)},
                )

            session.commit()
            return ServiceResponse.success_res(
                message=f"Record in '{entity}' synchronized successfully for tenant {tid}."
            )
        except Exception as e:
            session.rollback()
            logger.exception("Upsert error")
            return ServiceResponse.error_res(f"Upsert failed: {str(e)}", "DATA_UPSERT_ERROR")

    @command(
        name="data.operate",
        description=(
            "Executes a dynamic operation (sum, subtract, etc.) " "defined in the Blueprint map."
        ),
        params_model={
            "entity": "str",
            "id": "str",
            "operation": "str",
            "value": "float",
            "impersonate_tid": "str (optional)",
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
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)

            # 1. Recuperar el mapa del tenant
            blueprint = blueprint_manager.get_blueprint_for_tenant(session, tid)
            if not blueprint:
                return ServiceResponse.error_res(
                    "No Blueprint assigned to this tenant.", "BLUEPRINT_NOT_FOUND"
                )

            # 2. Ejecutar la operación mediante el MapExecutor
            success = map_executor.execute_operation(
                session=session,
                tenant_id=tid,
                entity_type=entity,
                record_id=id,
                operation_name=operation,
                value=value,
                blueprint=blueprint,
            )

            if not success:
                return ServiceResponse.error_res(
                    f"Operation '{operation}' failed or is not "
                    f"defined in the map for entity '{entity}'.",
                    "OPERATION_FAILED",
                )

            return ServiceResponse.success_res(
                message=f"Operation '{operation}' executed successfully for tenant {tid}."
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
            "impersonate_tid": "str (optional)",
        },
    )
    def get_record(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        id: str,
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)
            result = (
                session.execute(
                    text("""
                    SELECT data FROM generic_data 
                    WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                """),
                    {"id": id, "tid": tid, "entity": entity},
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
            "impersonate_tid": "str (optional)",
        },
    )
    def delete_record(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        id: str,
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)
            session.execute(
                text("""
                    DELETE FROM generic_data 
                    WHERE id = :id AND tenant_id = :tid AND entity_type = :entity
                """),
                {"id": id, "tid": tid, "entity": entity},
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
            "impersonate_tid": "str (optional)",
        },
    )
    def query_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)
            query_str = """
                SELECT id, data FROM generic_data 
                WHERE tenant_id = :tid AND entity_type = :entity
            """
            db_params = {"tid": tid, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                db_params["filters"] = json.dumps(filters)

            result = session.execute(text(query_str), db_params).mappings().all()

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
            "impersonate_tid": "str (optional)",
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
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)
            offset = (page - 1) * page_size

            query_str = """
                SELECT id, data FROM generic_data 
                WHERE tenant_id = :tid AND entity_type = :entity
            """
            db_params: dict[str, Any] = {"tid": tid, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                db_params["filters"] = json.dumps(filters)

            query_str += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            db_params["limit"] = page_size
            db_params["offset"] = offset

            result = session.execute(text(query_str), db_params).mappings().all()

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
        params_model={
            "entity": "str",
            "filters": "dict (optional)",
            "impersonate_tid": "str (optional)",
        },
    )
    def count_records(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
        impersonate_tid: str | None = None,
    ) -> ServiceResponse:
        try:
            params = {"impersonate_tid": impersonate_tid}
            tid = self._get_effective_tid(context, params)
            query_str = (
                "SELECT count(*) as total FROM generic_data "
                "WHERE tenant_id = :tid AND entity_type = :entity"
            )
            db_params = {"tid": tid, "entity": entity}

            if filters:
                query_str += " AND data @> :filters"
                db_params["filters"] = json.dumps(filters)

            result = session.execute(text(query_str), db_params).scalar()
            return ServiceResponse.success_res(data={"total": result})
        except Exception as e:
            return ServiceResponse.error_res(f"Count error: {str(e)}", "DATA_COUNT_ERROR")


data_commands = DataCommandHandler()
