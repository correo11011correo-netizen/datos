import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("OmniCore.MapExecutor")


class MapExecutor:
    """
    Motor de Ejecución por Mapa.
    Traduce las definiciones de un Blueprint JSONB en operaciones SQL nativas de JSONB en PostgreSQL.
    """

    @staticmethod
    def _resolve_path(path: str) -> list[str]:
        """
        Convierte una ruta de punto (ej: 'finances.balance')
        en una lista compatible con el operador #> de Postgres.
        """
        return path.split(".")

    @classmethod
    def execute_operation(
        cls,
        session: Session,
        tenant_id: str,
        entity_type: str,
        record_id: str,
        operation_name: str,
        value: Any,
        blueprint: dict,
    ) -> bool:
        """
        Busca una operación en el mapa y la ejecuta sobre el registro indicado.
        """
        # 1. Localizar la entidad en el mapa
        entity_def = blueprint.get("entities", {}).get(entity_type)
        if not entity_def:
            logger.error(f"Entity {entity_type} not defined in blueprint.")
            return False

        # 2. Localizar la operación en la entidad
        op_def = entity_def.get("operations", {}).get(operation_name)
        if not op_def:
            logger.error(f"Operation {operation_name} not defined for entity {entity_type}.")
            return False

        # 3. Extraer la ruta de almacenamiento y el tipo de operación
        storage_path = entity_def.get("storage_path")
        op_type = op_def.get("type")

        if not storage_path or not op_type:
            logger.error(f"Blueprint missing storage_path or op_type for {operation_name}.")
            return False

        # 4. Traducir a SQL según el tipo de operación
        # Usamos jsonb_set y operadores aritméticos de Postgres
        path_list = cls._resolve_path(storage_path)

        if op_type == "sum":
            # Suma: current_value + value
            sql = text("""
                UPDATE generic_data 
                SET data = jsonb_set(
                    data, 
                    :path, 
                    to_jsonb((COALESCE((data #>> :path)::numeric, 0) + :val)::text)
                ) 
                WHERE id = :rid AND tenant_id = :tid AND entity_type = :entity
            """)
            params = {
                "path": path_list,
                "val": value,
                "rid": record_id,
                "tid": tenant_id,
                "entity": entity_type,
            }

        elif op_type == "subtract":
            # Resta: current_value - value
            sql = text("""
                UPDATE generic_data 
                SET data = jsonb_set(
                    data, 
                    :path, 
                    to_jsonb((COALESCE((data #>> :path)::numeric, 0) - :val)::text)
                ) 
                WHERE id = :rid AND tenant_id = :tid AND entity_type = :entity
            """)
            params = {
                "path": path_list,
                "val": value,
                "rid": record_id,
                "tid": tenant_id,
                "entity": entity_type,
            }

        elif op_type == "increment":
            # Incremento simple (+1 o valor dado)
            sql = text("""
                UPDATE generic_data 
                SET data = jsonb_set(
                    data, 
                    :path, 
                    to_jsonb((COALESCE((data #>> :path)::numeric, 0) + :val)::text)
                ) 
                WHERE id = :rid AND tenant_id = :tid AND entity_type = :entity
            """)
            params = {
                "path": path_list,
                "val": value,
                "rid": record_id,
                "tid": tenant_id,
                "entity": entity_type,
            }

        else:
            logger.error(f"Unsupported operation type: {op_type}")
            return False

        try:
            session.execute(sql, params)
            session.commit()
            return True
        except Exception:
            logger.exception(f"SQL Execution error for op {operation_name}")
            return False


map_executor = MapExecutor()
