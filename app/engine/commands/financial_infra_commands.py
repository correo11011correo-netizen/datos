import uuid

from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse
from app.engine.commands.data_commands import data_commands


class FinancialInfraCommandHandler:
    """
    Motor de Infraestructura Financiera Genérica.
    Gestiona la persistencia de transacciones, transferencias y movimientos
    de fondos sin implementar reglas de negocio ni depender de proveedores específicos.
    """

    # --- CONFIGURACIÓN DE PROVEEDORES (Gateways) ---

    @command(
        name="fin.gateway.configure",
        description="Configures a financial provider gateway (API keys, endpoints, etc.).",
        params_model={
            "provider_id": "string",
            "config": "dict",
        },
    )
    def configure_gateway(
        self, session: Session, context: TenantContext, provider_id: str, config: dict
    ) -> ServiceResponse:
        try:
            # Guardamos la configuración en la entidad 'financial_gateways'
            return data_commands.upsert_record(
                session,
                context,
                entity="financial_gateways",
                unique_key="provider_id",
                unique_value=provider_id,
                data={"provider_id": provider_id, "config": config},
            )
        except Exception as e:
            return ServiceResponse.error_res(
                f"Gateway config error: {str(e)}", "GATEWAY_CONFIG_ERROR"
            )

    # --- GESTIÓN DE TRANSACCIONES (Ciclo de Vida) ---

    @command(
        name="fin.transaction.create",
        description=(
            "Registers a new financial transaction request and generates a tracking reference."
        ),
        params_model={
            "amount": "float",
            "currency": "string",
            "reference_id": "string",  # External ID from provider
            "metadata": "dict",
        },
    )
    def create_transaction(
        self,
        session: Session,
        context: TenantContext,
        amount: float,
        currency: str,
        reference_id: str,
        metadata: dict,
    ) -> ServiceResponse:
        try:
            transaction_id = str(uuid.uuid4())
            data = {
                "id": transaction_id,
                "amount": amount,
                "currency": currency,
                "reference_id": reference_id,
                "status": "pending",
                "metadata": metadata,
                "created_at": "NOW()",
            }

            res = data_commands.insert_data(session, context, entity="transactions", data=data)
            return (
                res if res.success else ServiceResponse.error_res(res.message, "TRANS_CREATE_ERROR")
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Transaction error: {str(e)}", "TRANS_CREATE_ERROR")

    @command(
        name="fin.transaction.update_status",
        description="Updates the status of a transaction (e.g., pending -> confirmed/failed).",
        params_model={
            "transaction_id": "string",
            "new_status": "string",
            "provider_response": "dict",
        },
    )
    def update_status(
        self,
        session: Session,
        context: TenantContext,
        transaction_id: str,
        new_status: str,
        provider_response: dict,
    ) -> ServiceResponse:
        try:
            # Actualizamos el estado y guardamos la respuesta del proveedor para auditoría
            updates = {
                "status": new_status,
                "last_update": "NOW()",
                "provider_log": provider_response,
            }

            return data_commands.patch_record(
                session, context, entity="transactions", id=transaction_id, updates=updates
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Status update error: {str(e)}", "TRANS_STATUS_ERROR")

    # --- REGISTRO de MOVIMIENTOS Y TRANSFERENCIAS (Ledger) ---

    @command(
        name="fin.movement.log",
        description="Records a financial movement (inflow, outflow, transfer).",
        params_model={
            "amount": "float",
            "type": "string",  # 'inflow', 'outflow', 'transfer'
            "source": "string",
            "destination": "string",
            "transaction_id": "string",  # Link to a transaction if applicable
            "metadata": "dict",
        },
    )
    def log_movement(
        self,
        session: Session,
        context: TenantContext,
        amount: float,
        type: str,
        source: str,
        destination: str,
        transaction_id: str | None = None,
        metadata: dict | None = None,
    ) -> ServiceResponse:
        try:
            movement_data = {
                "amount": amount,
                "type": type,
                "source": source,
                "destination": destination,
                "transaction_id": transaction_id,
                "metadata": metadata or {},
                "timestamp": "NOW()",
            }

            return data_commands.insert_data(
                session, context, entity="financial_movements", data=movement_data
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Movement log error: {str(e)}", "MOV_LOG_ERROR")

    @command(
        name="fin.ledger.balance",
        description="Calculates the current balance for a specific source/destination.",
        params_model={"identifier": "string"},
    )
    def get_balance(
        self, session: Session, context: TenantContext, identifier: str
    ) -> ServiceResponse:
        try:
            # Sumamos inflows y restamos outflows para el identificador
            # Implementación genérica vía query_data y cálculo en memoria
            # (para mantener simplicidad)
            res = data_commands.query_data(
                session,
                context,
                entity="financial_movements",
                filters={"source": identifier},  # Simplificado: solo busca salidas
            )

            # En una implementación real, haríamos un SUM() en SQL.
            # Aquí usamos la infraestructura genérica para demostrar el flujo.
            total_out = sum([float(m.get("amount", 0)) for m in res.data]) if res.success else 0

            res_in = data_commands.query_data(
                session, context, entity="financial_movements", filters={"destination": identifier}
            )
            total_in = (
                sum([float(m.get("amount", 0)) for m in res_in.data]) if res_in.success else 0
            )

            return ServiceResponse.success_res(
                data={"balance": total_in - total_out}, message="Balance calculated successfully."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Balance error: {str(e)}", "BALANCE_ERROR")


financial_infra_commands = FinancialInfraCommandHandler()
