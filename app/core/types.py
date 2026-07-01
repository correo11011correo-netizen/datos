from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceResponse:
    """
    Respuesta estandarizada para todos los comandos del motor.
    """

    success: bool
    data: Any | None = None
    message: str | None = None
    error_code: str | None = None
    hint: str | None = None
    example: Any | None = None

    @classmethod
    def success_res(cls, data: Any = None, message: str = "Operation successful"):
        return cls(success=True, data=data, message=message)

    @classmethod
    def error_res(
        cls,
        message: str,
        code: str = "INTERNAL_ERROR",
        hint: str | None = None,
        example: Any = None,
    ):
        return cls(success=False, message=message, error_code=code, hint=hint, example=example)
