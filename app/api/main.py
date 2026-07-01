from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.dispatcher import dispatcher
from app.engine.commands.data_commands import data_commands
from app.engine.commands.db_commands import (
    cmd_create_entity,
    cmd_format_all,
    cmd_init_system,
    cmd_insert_data,
    cmd_list_entities,
    cmd_query_entity,
    cmd_seed_system,
)

app = FastAPI(title=settings.APP_NAME)

# Register commands to dispatcher
dispatcher.register("format_all", cmd_format_all)
dispatcher.register("init_system", cmd_init_system)
dispatcher.register("create_entity", cmd_create_entity)
dispatcher.register("insert_data", cmd_insert_data)
dispatcher.register("query_entity", cmd_query_entity)
dispatcher.register("seed_system", cmd_seed_system)
dispatcher.register("list_entities", cmd_list_entities)
dispatcher.register_handler(data_commands)

# Serve static files from the 'frontend' directory
# We mount it at /static to avoid conflicts with API routes
app.mount("/static", StaticFiles(directory="frontend"), name="static")


async def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid Admin Token")
    return True


@app.get("/")
async def serve_index():
    """Serves the Admin Portal HTML page."""
    return FileResponse("frontend/index.html")


@app.get("/api/status")
async def status():
    """Health check endpoint for the API."""
    return {"status": "online", "engine": settings.APP_NAME}


@app.post("/exec")
async def execute_command(request: Request, cmd: str, admin: bool = Depends(verify_admin)):
    try:
        # Manejo seguro de body vacío para evitar "Expecting value: line 1 column 1"
        body = await request.body()
        params = {}
        if body:
            try:
                import json

                params = json.loads(body)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

        result = await dispatcher.dispatch(cmd, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Engine Error: {str(e)}") from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec
