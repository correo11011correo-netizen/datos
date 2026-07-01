import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse


class DataCommandHandler:
    """
    Universal Data Motor.
    Operates on a single 'generic_data' table to provide a truly
    entity-agnostic storage system for any SaaS platform.
    """

    def _sanitize_identifier(self, identifier: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "", identifier)

    def _validate_schema(
        self, session: Session, context: TenantContext, entity: str, data: dict
    ) -> tuple[bool, str | None]:
        """Internal helper to validate data against the tenant's virtual schema."""
        res = (
            session.execute(
                text("SELECT schema_definition FROM tenant_schemas WHERE tenant_id = :tid"),
                {"tid": context.tenant_id},
            )
            .mappings()
            .first()
        )

        if not res:
            return False, "No virtual schema defined for this tenant. Use 'schema.define' first."

        schema = json.loads(res["schema_definition"])
        if entity not in schema:
            return False, f"Entity '{entity}' is not defined in your virtual schema."

        entity_fields = schema[entity]
        for field, expected_type in entity_fields.items():
            if field not in data:
                return False, f"Missing required field: {field}"

            val = data[field]
            if expected_type == "int" and not isinstance(val, int):
                return False, f"Field {field} must be an integer."
            if expected_type == "float" and not isinstance(val, int | float):
                return False, f"Field {field} must be a number."
            if expected_type == "text" and not isinstance(val, str):
                return False, f"Field {field} must be text."

        return True, None

    @command(
        name="data.query",
        description="Retrieves records from a generic entity using dynamic filters.",
        params_model={
            "entity": "string",
            "filters": "dict",
            "limit": "int",
            "offset": "int",
            "sort_by": "string",
            "sort_order": "string",
        },
    )
    def query_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "ASC",
    ) -> ServiceResponse:
        try:
            where_clauses = []
            params: dict[str, Any] = {"tid": context.tenant_id, "etype": entity}

            if filters:
                for i, (key, value) in enumerate(filters.items()):
                    param_name = f"f{i}"
                    safe_key = self._sanitize_identifier(key)
                    where_clauses.append(f"data->>'{safe_key}' = :{param_name}")
                    params[param_name] = value

            where_stmt = "WHERE tenant_id = :tid AND entity_type = :etype"
            if where_clauses:
                where_stmt += " AND " + " AND ".join(where_clauses)

            order_stmt = ""
            if sort_by:
                direction = "DESC" if sort_order.upper() == "DESC" else "ASC"
                safe_sort = self._sanitize_identifier(sort_by)
                order_stmt = f"ORDER BY data->>'{safe_sort}' {direction}"

            query = (
                f"SELECT * FROM generic_data {where_stmt} {order_stmt} LIMIT :limit OFFSET :offset"
            )
            params["limit"] = limit
            params["offset"] = offset

            result = session.execute(text(query), params).mappings().all()
            return ServiceResponse.success_res(
                data=[dict(row) for row in result], message=f"Retrieved {len(result)} records."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Query error: {str(e)}", "QUERY_ERROR")

    @command(
        name="data.insert",
        description="Inserts a new record into a generic entity, validated against the tenant's virtual schema.",
        params_model={"entity": "string", "data": "dict"},
    )
    def insert_data(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        data: dict,
    ) -> ServiceResponse:
        try:
            valid, error = self._validate_schema(session, context, entity, data)
            if not valid:
                return ServiceResponse.error_res(error, "VALIDATION_ERROR")

            query = "INSERT INTO generic_data (tenant_id, entity_type, data) VALUES (:tid, :etype, :data) RETURNING id"
            result = session.execute(
                text(query), {"tid": context.tenant_id, "etype": entity, "data": json.dumps(data)}
            ).scalar()

            session.commit()
            return ServiceResponse.success_res(
                data={"id": result}, message="Record inserted successfully."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Insert error: {str(e)}", "INSERT_ERROR")

    @command(
        name="data.upsert",
        description="Inserts or updates a record based on a unique key inside the JSON data.",
        params_model={
            "entity": "string",
            "unique_key": "string",
            "unique_value": "string",
            "data": "dict",
        },
    )
    def upsert_record(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        unique_key: str,
        unique_value: str,
        data: dict,
    ) -> ServiceResponse:
        try:
            safe_key = self._sanitize_identifier(unique_key)
            existing = session.execute(
                text(
                    f"SELECT id FROM generic_data WHERE data->>'{safe_key}' = :val AND tenant_id = :tid AND entity_type = :etype"
                ),
                {"val": unique_value, "tid": context.tenant_id, "etype": entity},
            ).scalar()

            if existing:
                session.execute(
                    text("UPDATE generic_data SET data = data || :data WHERE id = :id"),
                    {"data": json.dumps(data), "id": existing},
                )
                msg = "Record updated."
            else:
                # Validate schema for new inserts
                valid, error = self._validate_schema(session, context, entity, data)
                if not valid:
                    return ServiceResponse.error_res(error, "VALIDATION_ERROR")

                session.execute(
                    text(
                        "INSERT INTO generic_data (tenant_id, entity_type, data) VALUES (:tid, :etype, :data)"
                    ),
                    {"tid": context.tenant_id, "etype": entity, "data": json.dumps(data)},
                )
                msg = "Record created."

            session.commit()
            return ServiceResponse.success_res(message=msg)
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Upsert error: {str(e)}", "UPSERT_ERROR")

    @command(
        name="data.patch",
        description="Partially updates a JSON record.",
        params_model={"entity": "string", "record_id": "string", "updates": "dict"},
    )
    def patch_record(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        record_id: str,
        updates: dict,
    ) -> ServiceResponse:
        try:
            session.execute(
                text(
                    "UPDATE generic_data SET data = data || :updates WHERE id = :id AND tenant_id = :tid AND entity_type = :etype"
                ),
                {
                    "updates": json.dumps(updates),
                    "id": record_id,
                    "tid": context.tenant_id,
                    "etype": entity,
                },
            )
            session.commit()
            return ServiceResponse.success_res(message="Record patched successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Patch error: {str(e)}", "PATCH_ERROR")

    @command(
        name="data.increment",
        description="Atomicsally increments a numerical field in a JSON record.",
        params_model={
            "entity": "string",
            "record_id": "string",
            "field": "string",
            "value": "float",
        },
    )
    def increment_field(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        record_id: str,
        field: str,
        value: float,
    ) -> ServiceResponse:
        try:
            safe_field = self._sanitize_identifier(field)
            query = f"""
                UPDATE generic_data 
                SET data = jsonb_set(
                    data, 
                    :field_path, 
                    to_jsonb((COALESCE((data->>'{safe_field}')::numeric, 0) + :val)::text)
                ) 
                WHERE id = :id AND tenant_id = :tid AND entity_type = :etype
            """
            session.execute(
                text(query),
                {
                    "field_path": f"{{{safe_field}}}",
                    "val": value,
                    "id": record_id,
                    "tid": context.tenant_id,
                    "etype": entity,
                },
            )
            session.commit()
            return ServiceResponse.success_res(message=f"Field {field} updated by {value}.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Increment error: {str(e)}", "INCREMENT_ERROR")

    @command(
        name="data.count",
        description="Counts records in a generic entity.",
        params_model={"entity": "string", "filters": "dict"},
    )
    def count_records(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
    ) -> ServiceResponse:
        try:
            where_clauses = []
            params: dict[str, Any] = {"tid": context.tenant_id, "etype": entity}

            if filters:
                for i, (key, value) in enumerate(filters.items()):
                    param_name = f"f{i}"
                    safe_key = self._sanitize_identifier(key)
                    where_clauses.append(f"data->>'{safe_key}' = :{param_name}")
                    params[param_name] = value

            where_stmt = "WHERE tenant_id = :tid AND entity_type = :etype"
            if where_clauses:
                where_stmt += " AND " + " AND ".join(where_clauses)

            query = f"SELECT count(*) FROM generic_data {where_stmt}"
            count = session.execute(text(query), params).scalar()

            return ServiceResponse.success_res(data={"count": count}, message="Count retrieved.")
        except Exception as e:
            return ServiceResponse.error_res(f"Count error: {str(e)}", "COUNT_ERROR")


data_commands = DataCommandHandler()
ommands = DataCommandHandler()
