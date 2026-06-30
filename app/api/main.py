from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.dispatcher import dispatcher
from app.engine.commands.db_commands import cmd_format_all, cmd_init_system, cmd_create_entity

app = FastAPI(title=settings.APP_NAME)

# Register commands to dispatcher
dispatcher.register("format_all", cmd_format_all)
dispatcher.register("init_system", cmd_init_system)
dispatcher.register("create_entity", cmd_create_entity)
dispatcher.register("insert_data", cmd_insert_data)
dispatcher.register("query_entity", cmd_query_entity)
dispatcher.register("seed_system", cmd_seed_system)

async def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid Admin Token")
    return True

@app.get("/")
async def root():
    return {"status": "online", "engine": settings.APP_NAME}

@app.post("/exec")
async def execute_command(
    request: Request, 
    cmd: str, 
    admin: bool = Depends(verify_admin)
):
    try:
        params = await request.json() if request.body() else {}
        result = await dispatcher.dispatch(cmd, params)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Engine Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
