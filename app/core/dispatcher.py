import difflib
import json
from collections.abc import Callable
from typing import Any

from app.core.db import execute_raw, text


class CommandDispatcher:
    def __init__(self):
        self._commands: dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        self._commands[name] = func

    def register_handler(self, handler: Any):
        """
        Automatically registers all methods of a handler class that are decorated with @command.
        """
        for attr_name in dir(handler):
            attr = getattr(handler, attr_name)
            if callable(attr) and hasattr(attr, "_command_meta"):
                meta = attr._command_meta
                self.register(meta["name"], attr)

    def get_all_commands(self) -> list[dict[str, Any]]:
        """
        Returns a catalog of all registered commands and their metadata.
        This is the core of the API's self-teaching capability.
        """
        catalog = []
        for name, func in self._commands.items():
            meta = getattr(func, "_command_meta", {})
            catalog.append(
                {
                    "command": name,
                    "description": meta.get("description", "No description provided."),
                    "params": meta.get("params_model", {}),
                }
            )
        return catalog

    async def dispatch(
        self, cmd_name: str, params: dict[str, Any] | None = None, tenant_id: str | None = None
    ) -> Any:
        if cmd_name not in self._commands:
            # --- Self-Teaching Logic: Fuzzy Matching ---
            all_cmds = list(self._commands.keys())
            closest_matches = difflib.get_close_matches(cmd_name, all_cmds, n=1, cutoff=0.6)

            error_msg = f"Command '{cmd_name}' not found."
            hint = "Check the available commands using /api/commands"
            example = None

            if closest_matches:
                suggested = closest_matches[0]
                meta = getattr(self._commands[suggested], "_command_meta", {})
                error_msg = f"Command '{cmd_name}' not found. Did you mean '{suggested}'?"
                hint = f"The command '{suggested}' does the following: {meta.get('description')}"
                example = {"cmd": suggested, "params": meta.get("params_model", {})}

            raise ValueError(
                json.dumps(
                    {
                        "error": "COMMAND_NOT_FOUND",
                        "message": error_msg,
                        "hint": hint,
                        "example": example,
                    }
                )
            )

        # --- Access Control: Level Verification ---
        func = self._commands[cmd_name]
        meta = getattr(func, "_command_meta", {})
        required_level = meta.get("required_level", "TENANT")
        required_plan = meta.get("required_plan", "free")

        # Root tenant (00000000...) has absolute power
        is_root = tenant_id == "00000000-0000-0000-0000-000000000000"

        if required_level == "SYSTEM" and not is_root:
            raise ValueError(
                json.dumps(
                    {
                        "error": "INSUFFICIENT_PERMISSIONS",
                        "message": (
                            f"The command '{cmd_name}' is a system-level operation "
                            "and is restricted to the root administrator."
                        ),
                        "hint": (
                            "You cannot execute infrastructure commands "
                            "(like formatting or seeding) using a tenant API key."
                        ),
                        "example": None,
                    }
                )
            )

        # --- Plan-Based Access Control (PBAC) ---
        if not is_root:
            # Basic hierarchy: free < pro < enterprise
            plan_hierarchy = {"free": 0, "pro": 1, "enterprise": 2}

            # Fetch tenant's actual plan from DB
            from app.core.db import SessionLocal

            with SessionLocal() as session:
                tenant_plan = (
                    session.execute(
                        text("SELECT plan FROM tenants WHERE id = :tid"), {"tid": tenant_id}
                    ).scalar()
                    or "free"
                )

            tenant_plan_level = plan_hierarchy.get(tenant_plan.lower(), 0)
            required_plan_level = plan_hierarchy.get(required_plan.lower(), 0)

            if tenant_plan_level < required_plan_level:
                raise ValueError(
                    json.dumps(
                        {
                            "error": "PLAN_REQUIRED",
                            "message": f"This command requires a {required_plan} plan or higher.",
                            "hint": "Upgrade your plan to unlock this feature.",
                            "example": None,
                        }
                    )
                )

        # Audit logging
        self._log_audit(cmd_name, params)

        # Inject session and context
        from app.core.context import TenantContext
        from app.core.db import SessionLocal

        with SessionLocal() as session:
            tid = tenant_id or "admin_root"
            context = TenantContext(tenant_id=tid)

            # Merge injected deps with params
            full_params = {"session": session, "context": context, **(params or {})}

            print(f"DEBUG: Dispatching {cmd_name} for tenant {tid} with params: {full_params}")

            # Handle both sync and async commands
            if callable(func):
                import inspect

                if inspect.iscoroutinefunction(func):
                    return await func(**full_params)
                return func(**full_params)

            raise TypeError(f"Command {cmd_name} is not callable")

    def _log_audit(self, cmd_name: str, params: dict[str, Any] | None):
        # Audit log entry
        execute_raw(
            "INSERT INTO audit_logs (command, params) VALUES (:cmd, :params)",
            {"cmd": cmd_name, "params": json.dumps(params)},
        )


dispatcher = CommandDispatcher()
