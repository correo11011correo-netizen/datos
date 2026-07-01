import functools
from collections.abc import Callable


def command(name: str, description: str, params_model: dict[str, str] | None = None):
    """
    Decorator to mark a method as a command executable by the dispatcher.
    Adds metadata to the function for automatic registration.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Attach metadata for the dispatcher to find
        wrapper._command_meta = { # type: ignore
            "name": name,
            "description": description,
            "params_model": params_model or {},
        }
        return wrapper
    return decorator
