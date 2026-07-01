import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("OmniCore.Blueprints")


class BlueprintManager:
    """
    Gestor de Mapas (Blueprints) del Sistema.
    Se encarga de recuperar la definición de administración JSONB
    asignada a un tenant específico.
    """

    def __init__(self):
        # Cache simple para evitar consultas repetitivas a la DB en el mismo request
        self._cache: dict[str, dict] = {}

    def get_blueprint_for_tenant(self, session: Session, tenant_id: str) -> dict | None:
        """
        Recupera el mapa JSONB vinculado al tenant a través de su blueprint_id.
        """
        if tenant_id in self._cache:
            return self._cache[tenant_id]

        try:
            query = text("""
                SELECT b.map_definition 
                FROM system_blueprints b
                JOIN tenants t ON t.blueprint_id = b.id
                WHERE t.id = :tid
            """)
            result = session.execute(query, {"tid": tenant_id}).mappings().first()

            if not result:
                return None

            # map_definition ya viene como dict si SQLAlchemy está configurado para JSONB,
            # pero nos aseguramos de que sea un diccionario.
            map_def = result["map_definition"]
            if isinstance(map_def, str):
                map_def = json.loads(map_def)

            self._cache[tenant_id] = map_def
            return map_def

        except Exception:
            logger.exception(f"Error retrieving blueprint for tenant {tenant_id}")
            return None

    def clear_cache(self, tenant_id: str | None = None):
        """Limpia la cache de mapas."""
        if tenant_id:
            self._cache.pop(tenant_id, None)
        else:
            self._cache.clear()


blueprint_manager = BlueprintManager()
