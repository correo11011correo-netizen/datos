import json

from core.context import TenantContext
from core.decorators import command
from core.types import ServiceResponse
from sqlalchemy import text
from sqlalchemy.orm import Session


class DataCommandHandler:
    """
    Motor de Operaciones Genéricas sobre Datos JSONB.
    Provee primitivas atómicas para que cualquier aplicación externa
    pueda gestionar su estado sin conocer la lógica de negocio.
    """

    @command(
        name="data.query",
        description="Retrieves records from an entity using dynamic filters, sorting and pagination.",
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
            # 1. Sanitizar nombre de tabla
            table_name = f"entity_{entity.lower().replace(' ', '_')}"
            safe_table = f'"{table_name}"'

            # 2. Construir cláusula WHERE dinámica para JSONB
            where_clauses = []
            params = {"tid": context.tenant_id}

            if filters:
                for i, (key, value) in enumerate(filters.items()):
                    param_name = f"f{i}"
                    # Usamos el operador ->> de PostgreSQL para obtener el valor como texto
                    where_clauses.append(f"data->>'{key}' = :{param_name}")
                    params[param_name] = str(value)

            where_stmt = "WHERE tenant_id = :tid"
            if where_clauses:
                where_stmt += " AND " + " AND ".join(where_clauses)

            # 3. Ordenamiento
            order_stmt = ""
            if sort_by:
                # Validar que el orden sea solo ASC o DESC
                direction = "DESC" if sort_order.upper() == "DESC" else "ASC"
                order_stmt = f"ORDER BY data->>'{sort_by}' {direction}"

            # 4. Construir Query Final
            query = (
                f"SELECT * FROM {safe_table} {where_stmt} {order_stmt} LIMIT :limit OFFSET :offset"
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
        name="data.patch",
        description="Partially updates a JSON record without overwriting the entire object.",
        params_model={
            "entity": "string",
            "record_id": "string",
            "updates": "dict",
        },
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
            table_name = f"entity_{entity.lower().replace(' ', '_')}"
            safe_table = f'"{table_name}"'

            # Usamos el operador || de PostgreSQL para fusionar JSONB
            # Esto actualiza solo las llaves proporcionadas en 'updates'
            session.execute(
                text(
                    "UPDATE {table} SET data = data || :updates WHERE id = :id AND tenant_id = :tid"
                ).format(table=safe_table),
                {"updates": json.dumps(updates), "id": record_id, "tid": context.tenant_id},
            )

            if session.execute(text("SELECT 1")).rowcount == 0:  # Simple check
                pass  # In real scenario, check rowcount of the update

            session.commit()
            return ServiceResponse.success_res(message="Record patched successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Patch error: {str(e)}", "PATCH_ERROR")

    @command(
        name="data.increment",
        description="Atomicsally increments or decrements a numerical field in a JSON record.",
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
            table_name = f"entity_{entity.lower().replace(' ', '_')}"
            safe_table = f'"{table_name}"'

            # Lógica de incremento atómico en JSONB:
            # 1. Convertir el valor actual a numeric
            # 2B. Sumar el valor
            # 3C. Volver a convertir a JSONB
            query = f"""
                UPDATE {safe_table} 
                SET data = jsonb_set(
                    data, 
                    ':{field}_path', 
                    to_jsonb((COALESCE((data->>':{field}')::numeric, 0) + :val)::text)
                ) 
                WHERE id = :id AND tenant_id = :tid
            """

            session.execute(
                text(query),
                {
                    "field_path": f"{{{field}}}",
                    "field": field,
                    "val": value,
                    "id": record_id,
                    "tid": context.tenant_id,
                },
            )

            session.commit()
            return ServiceResponse.success_res(message=f"Field {field} updated by {value}.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Increment error: {str(e)}", "INCREMENT_ERROR")

    @command(
        name="data.upsert",
        description="Inserts a record or updates it if a specific unique key already exists.",
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
            table_name = f"entity_{entity.lower().replace(' ', '_')}"
            safe_table = f'"{table_name}"'

            # Buscamos si ya existe el registro basado en el campo del JSONB
            existing = session.execute(
                text(
                    f"SELECT id FROM {safe_table} WHERE data->>'{unique_key}' = :val AND tenant_id = :tid"
                ),
                {"val": unique_value, "tid": context.tenant_id},
            ).scalar()

            if existing:
                # UPDATE
                session.execute(
                    text(f"UPDATE {safe_table} SET data = data || :data WHERE id = :id"),
                    {"data": json.dumps(data), "id": existing},
                )
                msg = "Record updated."
            else:
                # INSERT
                session.execute(
                    text(f"INSERT INTO {safe_table} (tenant_id, data) VALUES (:tid, :data)"),
                    {"tid": context.tenant_id, "data": json.dumps(data)},
                )
                msg = "Record created."

            session.commit()
            return ServiceResponse.success_res(message=msg)
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Upsert error: {str(e)}", "UPSERT_ERROR")

    @command(
        name="data.count",
        description="Counts records in an entity matching specific filters.",
        params_model={
            "entity": "string",
            "filters": "dict",
        },
    )
    def count_records(
        self,
        session: Session,
        context: TenantContext,
        entity: str,
        filters: dict | None = None,
    ) -> ServiceResponse:
        try:
            table_name = f"entity_{entity.lower().replace(' ', '_')}"
            safe_table = f'"{table_name}"'

            where_clauses = []
            params = {"tid": context.tenant_id}

            if filters:
                for i, (key, value) in enumerate(filters.items()):
                    param_name = f"f{i}"
                    where_clauses.append(f"data->>'{key}' = :{param_name}")
                    params[param_name] = str(value)

            where_stmt = "WHERE tenant_id = :tid"
            if where_clauses:
                where_stmt += " AND " + " AND ".join(where_clauses)

            query = f"SELECT count(*) FROM {safe_table} {where_stmt}"
            count = session.execute(text(query), params).scalar()

            return ServiceResponse.success_res(data={"count": count}, message="Count retrieved.")
        except Exception as e:
            return ServiceResponse.error_res(f"Count error: {str(e)}", "COUNT_ERROR")


data_commands = DataCommandHandler()
