import logging
from typing import Any

logger = logging.getLogger("OmniCore.Validator")


class SchemaValidator:
    """
    Motor de validación dinámica para datos almacenados en JSONB.
    Compara la data entrante contra la definición de esquema del Tenant.
    """

    # Mapa de tipos soportados
    TYPE_MAP: dict[str, type | tuple[type, ...]] = {
        "text": str,
        "float": (float, int),
        "int": int,
        "bool": bool,
        "json": (dict, list),
    }

    @classmethod
    def validate(
        cls, entity_type: str, schema_definition: dict[str, Any], data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Valida que la data cumpla con el esquema definido para la entidad.

        Args:
            entity_type: Nombre de la entidad (ej: 'products')
            schema_definition: Diccionario completo de esquemas del tenant
            data: Datos a validar

        Returns:
            (True, None) si es válido, (False, error_message) si no lo es.
        """
        if entity_type not in schema_definition:
            return False, f"La entidad '{entity_type}' no está definida en el esquema del tenant."

        entity_schema = schema_definition[entity_type]

        if not isinstance(entity_schema, dict):
            return False, (
                f"La definición de esquema para '{entity_type}' debe ser un objeto de campos."
            )

        for field, expected_type_str in entity_schema.items():
            if field not in data:
                # Permitimos campos opcionales por defecto,
                # pero podríamos añadir una marca de 'required' en el esquema futuro.
                continue

            value = data[field]
            expected_type = cls.TYPE_MAP.get(expected_type_str.lower())

            if not expected_type:
                return False, (
                    f"Tipo de dato '{expected_type_str}' no soportado en el campo '{field}'."
                )

            if not isinstance(value, expected_type):
                actual_type = type(value).__name__
                return False, (
                    f"Tipo inválido en campo '{field}': se esperaba {expected_type_str} "
                    f"({expected_type}), se recibió {actual_type}."
                )

        return True, None
