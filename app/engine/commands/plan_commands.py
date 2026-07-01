import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse


class PlanCommandHandler:
    """
    Gestor de Planes y Monetización Genérica.
    Permite definir qué puede hacer cada nivel de suscripción.
    """

    @command(
        name="plan.list",
        description="Lists all available plans and their features.",
        params_model={},
    )
    def list_plans(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            # Consultamos la tabla de planes
            result = (
                session.execute(text("SELECT * FROM plans ORDER BY price ASC")).mappings().all()
            )
            return ServiceResponse.success_res(
                data=[dict(row) for row in result], message=f"Retrieved {len(result)} plans."
            )
        except Exception as e:
            return ServiceResponse.error_res(f"Error listing plans: {str(e)}", "PLAN_LIST_ERROR")

    @command(
        name="plan.set",
        description="Assigns a specific plan to a tenant.",
        params_model={
            "tenant_id": "string",
            "plan_id": "string",
        },
    )
    def set_tenant_plan(
        self, session: Session, context: TenantContext, tenant_id: str, plan_id: str
    ) -> ServiceResponse:
        try:
            # Solo el Root Admin puede cambiar planes de otros
            if context.tenant_id != "00000000-0000-0000-0000-000000000000":
                return ServiceResponse.error_res(
                    "Only root administrators can change plans.", "UNAUTHORIZED"
                )

            # Validar que el plan existe
            plan_exists = session.execute(
                text("SELECT 1 FROM plans WHERE plan_id = :pid"), {"pid": plan_id}
            ).scalar()

            if not plan_exists:
                return ServiceResponse.error_res(
                    f"Plan {plan_id} does not exist.", "PLAN_NOT_FOUND"
                )

            # Actualizar el tenant
            session.execute(
                text("UPDATE tenants SET plan = :pid WHERE id = :tid"),
                {"pid": plan_id, "tid": tenant_id},
            )
            session.commit()
            return ServiceResponse.success_res(
                message=f"Tenant {tenant_id} updated to plan {plan_id}."
            )
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Error updating plan: {str(e)}", "PLAN_UPDATE_ERROR")

    @command(
        name="plan.define",
        description="Creates or updates a plan definition.",
        params_model={
            "plan_id": "string",
            "name": "string",
            "price": "float",
            "features": "dict",
        },
    )
    def define_plan(
        self,
        session: Session,
        context: TenantContext,
        plan_id: str,
        name: str,
        price: float,
        features: dict,
    ) -> ServiceResponse:
        try:
            if context.tenant_id != "00000000-0000-0000-0000-000000000000":
                return ServiceResponse.error_res(
                    "Only root administrators can define plans.", "UNAUTHORIZED"
                )

            # Upsert del plan
            existing = session.execute(
                text("SELECT 1 FROM plans WHERE plan_id = :pid"), {"pid": plan_id}
            ).scalar()

            if existing:
                session.execute(
                    text(
                        "UPDATE plans SET name = :name, price = :price, "
                        "features = :feat WHERE plan_id = :pid"
                    ),
                    {"name": name, "price": price, "feat": json.dumps(features), "pid": plan_id},
                )
            else:
                session.execute(
                    text(
                        "INSERT INTO plans (plan_id, name, price, features) "
                        "VALUES (:pid, :name, :price, :feat)"
                    ),
                    {"pid": plan_id, "name": name, "price": price, "feat": json.dumps(features)},
                )

            session.commit()
            return ServiceResponse.success_res(message=f"Plan {plan_id} defined successfully.")
        except Exception as e:
            session.rollback()
            return ServiceResponse.error_res(f"Error defining plan: {str(e)}", "PLAN_DEFINE_ERROR")


plan_commands = PlanCommandHandler()
