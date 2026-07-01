import uuid

from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse
from app.engine.commands.data_commands import data_commands


class ChatInfraCommandHandler:
    """
    Motor de Infraestructura para Chats y Bots.
    Se enfoca en la administración técnica de sesiones, flujos de mensajes
    y la orquestación de grafos de bots, sin implementar lógica de negocio.
    """

    # --- GESTIÓN DE SESIONES (Real-time Performance) ---

    @command(
        name="chat.session.sync",
        description="Synchronizes or creates a chat session for a user. Optimized for high-frequency updates.",
        params_model={
            "identifier": "string",  # phone or user_id
            "meta": "dict",
        },
    )
    def sync_session(
        self, session: Session, context: TenantContext, identifier: str, meta: dict
    ) -> ServiceResponse:
        try:
            # Usamos upsert para mantener la sesión actualizada en tiempo real
            # Entidad: 'chat_sessions'
            res = data_commands.upsert_record(
                session,
                context,
                entity="chat_sessions",
                unique_key="identifier",
                unique_value=identifier,
                data={
                    "identifier": identifier,
                    "last_seen": "NOW()",  # Simplificado, el DB lo maneja o se pasa timestamp
                    "session_data": meta,
                    "tenant_id": context.tenant_id,
                },
            )
            return res
        except Exception as e:
            return ServiceResponse.error_res(f"Session sync error: {str(e)}", "SESSION_SYNC_ERROR")

    @command(
        name="chat.messages.stream",
        description="Inserts a batch of messages into the stream. Optimized for high volume.",
        params_model={
            "messages": "list",  # List of {"sender": "...", "text": "...", "type": "..."}
        },
    )
    def stream_messages(
        self, session: Session, context: TenantContext, messages: list[dict]
    ) -> ServiceResponse:
        try:
            # Inserción masiva para reducir round-trips a la DB
            for msg in messages:
                data_commands.insert_data(
                    session,
                    context,
                    entity="chat_history",
                    data={
                        "tenant_id": context.tenant_id,
                        "payload": msg,
                        "timestamp": "CURRENT_TIMESTAMP",
                    },
                )
            session.commit()
            return ServiceResponse.success_res(
                message=f"Streamed {len(messages)} messages successfully."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Stream error: {str(e)}", "STREAM_ERROR")

    # --- ADMINISTRACIÓN DE GRAFOS DE BOTS (Orquestación Genérica) ---

    @command(
        name="bot.graph.set_node",
        description="Sets or updates a node in the bot's conversation graph.",
        params_model={
            "node_id": "string",
            "config": "dict",
        },
    )
    def set_node(
        self, session: Session, context: TenantContext, node_id: str, config: dict
    ) -> ServiceResponse:
        try:
            # Administramos la estructura del bot como datos puros en 'bot_nodes'
            return data_commands.upsert_record(
                session,
                context,
                entity="bot_nodes",
                unique_key="node_id",
                unique_value=node_id,
                data={"node_id": node_id, "config": config},
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Node update error: {str(e)}", "BOT_GRAPH_ERROR")

    @command(
        name="bot.graph.link",
        description="Creates a directed edge between two nodes in the bot's graph.",
        params_model={
            "from_node": "string",
            "to_node": "string",
            "trigger": "string",
        },
    )
    def link_nodes(
        self, session: Session, context: TenantContext, from_node: str, to_node: str, trigger: str
    ) -> ServiceResponse:
        try:
            # Almacenamos la conexión en 'bot_edges'
            return data_commands.insert_data(
                session,
                context,
                entity="bot_edges",
                data={"from_node": from_node, "to_node": to_node, "trigger": trigger},
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Link error: {str(e)}", "BOT_GRAPH_ERROR")

    # --- FIABILIDAD Y BACKUPS (Data Safety) ---

    @command(
        name="infra.backup.snapshot",
        description="Creates a JSON snapshot of a specific entity for a tenant.",
        params_model={
            "entity": "string",
        },
    )
    def snapshot_entity(
        self, session: Session, context: TenantContext, entity: str
    ) -> ServiceResponse:
        try:
            # Extraemos todos los datos de la entidad para el tenant
            res = data_commands.query_data(session, context, entity=entity, limit=10000)
            if not res.success:
                return res

            # Guardamos el snapshot en una tabla de backups
            snapshot_id = str(uuid.uuid4())
            data_commands.insert_data(
                session,
                context,
                entity="backups",
                data={"id": snapshot_id, "entity": entity, "data": res.data, "timestamp": "NOW()"},
            )
            return ServiceResponse.success_res(
                data={"snapshot_id": snapshot_id}, message="Snapshot created successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Backup error: {str(e)}", "BACKUP_ERROR")

    @command(
        name="infra.backup.restore",
        description="Restores an entity from a snapshot.",
        params_model={
            "snapshot_id": "string",
        },
    )
    def restore_snapshot(
        self, session: Session, context: TenantContext, snapshot_id: str
    ) -> ServiceResponse:
        try:
            # Recuperamos el snapshot
            res = data_commands.query_data(
                session, context, entity="backups", filters={"id": snapshot_id}
            )
            if not res.success or not res.data:
                return ServiceResponse.error_res("Snapshot not found", "RESTORE_ERROR")

            snapshot = res.data[0]
            entity = snapshot["entity"]
            data_to_restore = snapshot["data"]

            # Restauramos cada registro
            for record in data_to_restore:
                # Usamos upsert para restaurar el estado
                # Asumimos que cada registro tiene un 'id'
                if "id" in record:
                    data_commands.upsert_record(
                        session,
                        context,
                        entity=entity,
                        unique_key="id",
                        unique_value=record["id"],
                        data=record,
                    )

            return ServiceResponse.success_res(
                message=f"Entity {entity} restored successfully from snapshot."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Restore failed: {str(e)}", "RESTORE_ERROR")


chat_infra_commands = ChatInfraCommandHandler()
