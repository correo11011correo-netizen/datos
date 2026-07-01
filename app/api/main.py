from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.dispatcher import dispatcher
from app.engine.commands.chat_infra_commands import chat_infra_commands
from app.engine.commands.data_commands import data_commands
from app.engine.commands.db_commands import db_commands
from app.engine.commands.dev_commands import dev_commands
from app.engine.commands.financial_infra_commands import financial_infra_commands
from app.engine.commands.plan_commands import plan_commands
from app.engine.commands.sales_commands import sales_commands
from app.engine.commands.sdui_commands import sdui_commands

app = FastAPI(title=settings.APP_NAME)

# Register ALL commands to dispatcher
dispatcher.register_handler(db_commands)
dispatcher.register_handler(data_commands)
dispatcher.register_handler(plan_commands)
dispatcher.register_handler(sales_commands)
dispatcher.register_handler(sdui_commands)
dispatcher.register_handler(chat_infra_commands)
dispatcher.register_handler(financial_infra_commands)
dispatcher.register_handler(dev_commands)

# Serve static files from the 'frontend' directory
app.mount("/static", StaticFiles(directory="frontend"), name="static")


async def get_current_tenant(x_api_key: str = Header(..., alias="x-admin-token")):
    """
    Self-Teaching Security: Validates the token.
    """
    if x_api_key == settings.ADMIN_SECRET_TOKEN:
        return "00000000-0000-0000-0000-000000000000"

    from app.core.db import execute_raw

    try:
        res = execute_raw(
            "SELECT tenant_id FROM api_keys WHERE token = :token", {"token": x_api_key}
        ).fetchone()
    except Exception:
        raise HTTPException(
            status_code=403, detail="System not initialized or invalid token"
        ) from None

    if not res:
        raise HTTPException(status_code=403, detail="Invalid or expired API Key")

    return str(res[0])


@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")


@app.get("/api/status")
async def status():
    return {"status": "online", "engine": settings.APP_NAME}


@app.get("/api/commands")
async def list_commands():
    return dispatcher.get_all_commands()


@app.get("/api/guide")
async def get_guide():
    try:
        with open("API_GUIDE.md", encoding="utf-8") as f:
            return {"guide": f.read()}
    except FileNotFoundError:
        return {"error": "Guide not found on server"}


def _raise_http_exception(status_code: int, detail: str):
    raise HTTPException(status_code=status_code, detail=detail)


def _parse_dispatcher_error(e: Exception):
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
        body = await request.body()
        params = {}
        if body:
            try:
                import json

                params = json.loads(body)
            except json.JSONDecodeError:
                _raise_http_exception(400, "Invalid JSON body. Please send a valid JSON object.")

        result = await dispatcher.dispatch(cmd, params, tenant_id=tenant_id)

        if hasattr(result, "success"):
            if not result.success:
                return {
                    "status": "error",
                    "error": result.error_code,
                    "message": result.message,
                    "hint": result.hint,
                    "example": result.example,
                    "documentation": (
                        "Check /api/commands for the correct parameter schema for this command."
                    ),
                }
            return {"status": "success", "result": result.data, "message": result.message}

        return {"status": "success", "result": result}
    except ValueError as e:
        parsed_error = _parse_dispatcher_error(e)
        if parsed_error:
            # Enrich the error with general usage instructions
            parsed_error["usage_guide"] = {
                "endpoint": "/exec",
                "method": "POST",
                "required_header": "x-admin-token",
                "discovery_endpoint": "/api/commands",
            }
            return parsed_error
        _raise_http_exception(400, str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Engine Error: {str(e)}") from e


if __name__ == "__main__":
    import uvicorn

    # host="0.0.0.0" is required for deployment in containerized environments (Railway/Docker)
    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec
