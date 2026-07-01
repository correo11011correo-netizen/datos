import uuid

from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse
from app.engine.commands.data_commands import data_commands


class SalesCommandHandler:
    """
    Gestor de Ventas Empresariales.
    Implementa el flujo crítico de: Validación -> Registro -> Descuento de Stock.
    Incluye Idempotencia para evitar duplicados en transacciones.
    """

    @command(
        name="sales.cobrar",
        description="Processes a sale with idempotency check and atomic stock deduction.",
        params_model={
            "client_request_id": "string",
            "customer": "string",
            "items": "list",  # List of {"code": "PROD1", "qty": 2}
            "total": "float",
        },
        required_plan="free",
    )
    def process_sale(
        self,
        session: Session,
        context: TenantContext,
        client_request_id: str,
        customer: str,
        items: list[dict],
        total: float,
    ) -> ServiceResponse:
        try:
            # 1. CHEQUEO DE IDEMPOTENCIA
            # Evita que la misma petición se procese dos veces (ej: doble clic del usuario)
            idempotency_check = data_commands.query_data(
                session, context, entity="sales", filters={"client_request_id": client_request_id}
            )
            if idempotency_check.success and idempotency_check.data:
                return ServiceResponse.success_res(
                    data=idempotency_check.data[0],
                    message="Sale already processed (idempotency check). No duplicate created.",
                )

            # 2. VALIDACIÓN DE STOCK Y PRECIOS
            # Verificamos que TODOS los productos existan y tengan stock antes de empezar
            validated_items = []
            current_total = 0.0

            for item in items:
                code = item.get("code")
                qty = item.get("qty", 1)

                prod_res = data_commands.query_data(
                    session, context, entity="products", filters={"code": code}
                )
                if not prod_res.success or not prod_res.data:
                    return ServiceResponse.error_res(
                        f"Product {code} not found.", "PRODUCT_NOT_FOUND"
                    )

                product = prod_res.data[0]

                # Validación de cantidad
                available = product.get("quantity", 0)
                if available < qty:
                    return ServiceResponse.error_res(
                        f"Insufficient stock for {product.get('name', code)}. "
                        f"Available: {available}",
                        "INSUFFICIENT_STOCK",
                    )

                price = float(product.get("price", 0))
                subtotal = price * qty
                current_total += subtotal

                validated_items.append(
                    {
                        "id": product["id"],
                        "code": code,
                        "qty": qty,
                        "price": price,
                        "subtotal": subtotal,
                    }
                )

            # 3. REGISTRO DE LA VENTA (CABECERA)
            sale_id = str(uuid.uuid4())
            sale_data = {
                "id": sale_id,
                "customer": customer,
                "total": current_total,
                "client_request_id": client_request_id,
                "status": "completed",
            }

            insert_sale = data_commands.insert_data(
                session, context, entity="sales", data=sale_data
            )
            if not insert_sale.success:
                return insert_sale

            # 4. REGISTRO DE ITEMS Y DESCUENTO ATÓMICO DE STOCK
            for v_item in validated_items:
                # Registrar el item de la venta para auditoría
                data_commands.insert_data(
                    session,
                    context,
                    entity="sale_items",
                    data={
                        "sale_id": sale_id,
                        "product_code": v_item["code"],
                        "qty": v_item["qty"],
                        "price": v_item["price"],
                        "subtotal": v_item["subtotal"],
                    },
                )

                # DESCUENTO ATÓMICO: Usamos el nuevo motor de operaciones dinámicas
                # Pasamos el valor en negativo para restar usando la operación 'sum' del Mapa
                stock_res = data_commands.operate(
                    session,
                    context,
                    entity="products",
                    record_id=v_item["id"],
                    operation="sum",
                    value=-v_item["qty"],
                )
                if not stock_res.success:
                    # El Dispatcher hará el rollback de toda la transacción si lanzamos excepción
                    raise Exception(
                        f"Critical error updating stock for {v_item['code']}: {stock_res.error}"
                    )

            return ServiceResponse.success_res(
                data={"sale_id": sale_id, "total": current_total},
                message="Sale processed successfully with atomic stock deduction.",
            )

        except Exception as e:
            # Forzamos el rollback a través del dispatcher
            session.rollback()
            return ServiceResponse.error_res(f"Sale failed: {str(e)}", "SALES_ERROR")


sales_commands = SalesCommandHandler()
