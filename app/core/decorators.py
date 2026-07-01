import asyncio
import functools
from collections.abc import Callable


def command(
    name: str,
    description: str,
    params_model: dict[str, str] | None = None,
    required_level: str = "TENANT",
):
    """
    Decorator to mark a method as a command executable by the dispatcher.
    Adds metadata to the function for automatic registration.

    required_level:
      - 'SYSTEM': Only the root admin can execute.
      - 'TENANT': Any authenticated tenant can execute.
    """

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

        # Attach metadata for the dispatcher to find
        wrapper._command_meta = {  # type: ignore
            "name": name,
            "description": description,
            "params_model": params_model or {},
            "required_level": required_level,
        }
        return wrapper

    return decorator
