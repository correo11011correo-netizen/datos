from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse
from app.engine.commands.data_commands import data_commands


class SduiCommandHandler:
    """
    Gestor de UI Dirigida por Servidor (SDUI).
    Permite que el servidor defina la apariencia y estructura de la interfaz
    de forma dinámica y personalizada por Tenant.
    """

    @command(
        name="sdui.define_component",
        description="Defines a global UI component and its default properties.",
        params_model={
            "id": "string",
            "type": "string",
            "props": "dict",
        },
        required_plan="enterprise",  # Only high-level admins can define global components
    )
    def define_component(
        self, session: Session, context: TenantContext, id: str, type: str, props: dict
    ) -> ServiceResponse:
        try:
            # Guardamos el componente en la entidad 'ui_components'
            res = data_commands.upsert_record(
                session,
                context,
                entity="ui_components",
                unique_key="id",
                unique_value=id,
                data={"id": id, "type": type, "props": props},
            )
            return res
        except Exception as e:
            return ServiceResponse.error_res(
                f"Error defining component: {str(e)}", "SDUI_COMP_ERROR"
            )

    @command(
        name="sdui.set_theme",
        description="Sets the visual theme for the current tenant.",
        params_model={
            "primary_color": "string",
            "secondary_color": "string",
            "dark_mode": "boolean",
            "logo_url": "string",
        },
        required_plan="pro",
    )
    def set_theme(self, session: Session, context: TenantContext, **theme_data) -> ServiceResponse:
        try:
            # El theme es único por Tenant. Usamos el tenant_id como unique_key.
            # Primero verificamos si ya existe un theme para este tenant
            res_exists = data_commands.query_data(
                session, context, entity="ui_themes", filters={"tenant_id": context.tenant_id}
            )

            record_id = None
            if res_exists.success and res_exists.data:
                record_id = res_exists.data[0]["id"]

            # Insertamos o actualizamos el theme
            data = {**theme_data, "tenant_id": context.tenant_id}

            if record_id:
                res = data_commands.patch_record(
                    session, context, entity="ui_themes", id=record_id, updates=data
                )
            else:
                res = data_commands.insert_data(session, context, entity="ui_themes", data=data)

            return res if res.success else ServiceResponse.error_res(res.error, "SDUI_THEME_ERROR")
        except Exception as e:
            return ServiceResponse.error_res(f"Error setting theme: {str(e)}", "SDUI_THEME_ERROR")

    @command(
        name="sdui.set_layout",
        description="Defines the layout structure for a specific screen.",
        params_model={
            "screen_id": "string",
            "layout_json": "dict",
        },
        required_plan="pro",
    )
    def set_layout(
        self, session: Session, context: TenantContext, screen_id: str, layout_json: dict
    ) -> ServiceResponse:
        try:
            # Buscamos si ya existe el layout para esta pantalla y tenant
            res_exists = data_commands.query_data(
                session,
                context,
                entity="ui_layouts",
                filters={"screen_id": screen_id, "tenant_id": context.tenant_id},
            )

            record_id = None
            if res_exists.success and res_exists.data:
                record_id = res_exists.data[0]["id"]

            data = {
                "screen_id": screen_id,
                "layout_json": layout_json,
                "tenant_id": context.tenant_id,
            }

            if record_id:
                res = data_commands.patch_record(
                    session, context, entity="ui_layouts", id=record_id, updates=data
                )
            else:
                res = data_commands.insert_data(session, context, entity="ui_layouts", data=data)

            return (
                res if res.success else ServiceResponse.error_res(res.message, "SDUI_LAYOUT_ERROR")
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error setting layout: {str(e)}", "SDUI_LAYOUT_ERROR")

    @command(
        name="sdui.get_screen",
        description="Retrieves the theme and layout for a specific screen.",
        params_model={"screen_id": "string"},
        required_plan="free",
    )
    def get_screen(
        self, session: Session, context: TenantContext, screen_id: str
    ) -> ServiceResponse:
        try:
            # 1. Obtener el Theme del Tenant
            theme_res = data_commands.query_data(
                session, context, entity="ui_themes", filters={"tenant_id": context.tenant_id}
            )
            theme = theme_res.data[0] if theme_res.success and theme_res.data else {}

            # 2. Obtener el Layout de la pantalla
            layout_res = data_commands.query_data(
                session,
                context,
                entity="ui_layouts",
                filters={"screen_id": screen_id, "tenant_id": context.tenant_id},
            )

            # Si el tenant no tiene un layout personalizado,
            # podríamos devolver un layout por defecto
            layout = (
                layout_res.data[0]
                if layout_res.success and layout_res.data
                else {"layout_json": "DEFAULT_LAYOUT"}
            )

            return ServiceResponse.success_res(
                data={"theme": theme, "layout": layout["layout_json"], "screen_id": screen_id},
                message="Screen configuration retrieved.",
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error retrieving screen: {str(e)}", "SDUI_GET_ERROR")


sdui_commands = SduiCommandHandler()
