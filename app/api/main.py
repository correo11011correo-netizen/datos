from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.dispatcher import dispatcher
from app.engine.commands.data_commands import data_commands
from app.engine.commands.db_commands import db_commands

app = FastAPI(title=settings.APP_NAME)

# Register commands to dispatcher
dispatcher.register_handler(db_commands)
dispatcher.register_handler(data_commands)

# Serve static files from the 'frontend' directory
# We mount it at /static to avoid conflicts with API routes
app.mount("/static", StaticFiles(directory="frontend"), name="static")


async def get_current_tenant(x_api_key: str = Header(..., alias="x-admin-token")):
    """
    Self-Teaching Security: Validates the token.
    First checks against the root admin secret (independent of DB).
    Then checks against the api_keys table for tenant tokens.
    """
    # 1. Root Admin Override (Hardcoded in settings for emergency/init access)
    if x_api_key == settings.ADMIN_SECRET_TOKEN:
        return "00000000-0000-0000-0000-000000000000"

    # 2. DB-based token validation
    from app.core.db import execute_raw

    try:
        res = execute_raw(
            "SELECT tenant_id FROM api_keys WHERE token = :token", {"token": x_api_key}
        ).fetchone()
    except Exception:
        # If table doesn't exist, only root admin (already checked) can enter
        raise HTTPException(
            status_code=403, detail="System not initialized or invalid token"
        ) from None

    if not res:
        raise HTTPException(status_code=403, detail="Invalid or expired API Key")

    return str(res[0])


@app.get("/")
async def serve_index():
    """Serves the Admin Portal HTML page."""
    return FileResponse("frontend/index.html")


@app.get("/api/status")
async def status():
    """Health check endpoint for the API."""
    return {"status": "online", "engine": settings.APP_NAME}


@app.get("/api/commands")
async def list_commands():
    """
    Self-Teaching API: Returns all available commands, their descriptions and parameters.
    Allows developers to discover the API without documentation.
    """
    return dispatcher.get_all_commands()


def _raise_http_exception(status_code: int, detail: str):
    """Helper to raise HTTPException outside of a direct except block to satisfy Ruff B904."""
    raise HTTPException(status_code=status_code, detail=detail)


def _parse_dispatcher_error(e: Exception):
    """Helper to parse structured JSON errors from the dispatcher."""
    try:
        import json

        error_data = json.loads(str(e))
        return {
            "status": "error",
            "error": error_data.get("error"),
            "message": error_data.get("message"),
            "hint": error_data.get("hint"),
            "example": error_data.get("example"),
        }
    except (json.JSONDecodeError, TypeError):
        return None


@app.post("/exec")
async def execute_command(request: Request, cmd: str, tenant_id: str = Depends(get_current_tenant)):
    try:
        # Manejo seguro de body vacío para evitar "Expecting value: line 1 column 1"
        body = await request.body()
        params = {}
        if body:
            try:
                import json

                params = json.loads(body)
            except json.JSONDecodeError:
                _raise_http_exception(400, "Invalid JSON body")

        # Pass the authenticated tenant_id to the dispatcher
        result = await dispatcher.dispatch(cmd, params, tenant_id=tenant_id)

        # If the result is a ServiceResponse, handle its success/failure state
        if hasattr(result, "success"):
            if not result.success:
                return {
                    "status": "error",
                    "error": result.error_code,
                    "message": result.message,
                    "hint": result.hint,
                    "example": result.example,
                }
            return {"status": "success", "result": result.data, "message": result.message}

        return {"status": "success", "result": result}
    except ValueError as e:
        parsed_error = _parse_dispatcher_error(e)
        if parsed_error:
            return parsed_error
        _raise_http_exception(400, str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Engine Error: {str(e)}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec
