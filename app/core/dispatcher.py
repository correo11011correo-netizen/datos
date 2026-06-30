from typing import Any, Dict, Callable
from app.core.db import execute_raw
from app.core.redis_core import clear_cache
from datetime import datetime
import json

class CommandDispatcher:
    def __init__(self):
        self._commands: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        self._commands[name] = func

    async def dispatch(self, cmd_name: str, params: Dict[str, Any] = None) -> Any:
        if cmd_name not in self._commands:
            raise ValueError(f"Command {cmd_name} not found")
        
        # Audit logging
        self._log_audit(cmd_name, params)
        
        return await self._commands[cmd_name](params or {})

    def _log_audit(self, cmd_name: str, params: Dict[str, Any]):
        # Ensure audit table exists (simplified for core)
        execute_raw("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                command TEXT,
                params JSONB,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        execute_raw(
            "INSERT INTO audit_logs (command, params) VALUES (:cmd, :params)",
            {"cmd": cmd_name, "params": json.dumps(params)}
        )

dispatcher = CommandDispatcher()
