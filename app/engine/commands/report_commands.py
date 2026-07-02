import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import TenantContext
from app.core.decorators import command
from app.core.types import ServiceResponse

logger = logging.getLogger("OmniCore.ReportHandler")


class ReportCommandHandler:
    """
    Gestor de Reportes Técnicos.
    Permite a los desarrolladores notificar bugs e mejoras de infraestructura al admin.
    """

    @command(
        name="dev.report.submit",
        description=(
            "Submits a technical report, bug, or improvement "
            "suggestion to the system administrator."
        ),
        params_model={
            "category": "str (BUG | IMPROVEMENT | CRITICAL)",
            "title": "str",
            "description": "str",
        },
        required_level="TENANT",
    )
    def submit_report(
        self, session: Session, context: TenantContext, category: str, title: str, description: str
    ) -> ServiceResponse:
        try:
            # Validar categoría
            valid_categories = ["BUG", "IMPROVEMENT", "CRITICAL"]
            if category.upper() not in valid_categories:
                return ServiceResponse.error_res(
                    f"Invalid category. Must be one of {valid_categories}", "INVALID_CATEGORY"
                )

            # Insertar reporte en la tabla de base de datos
            session.execute(
                text("""
                    INSERT INTO dev_reports (tenant_id, category, title, description) 
                    VALUES (:tid, :cat, :title, :desc)
                """),
                {
                    "tid": context.tenant_id,
                    "cat": category.upper(),
                    "title": title,
                    "desc": description,
                },
            )

            session.commit()
            return ServiceResponse.success_res(
                message="Technical report submitted successfully. The admin will review it soon."
            )
        except Exception as e:
            session.rollback()
            logger.exception("Error submitting report")
            return ServiceResponse.error_res(f"Report error: {str(e)}", "REPORT_SUBMIT_ERROR")

    @command(
        name="system.report.list",
        description="Lists all submitted developer reports. Root Only.",
        params_model={},
        required_level="SYSTEM",
    )
    def list_reports(self, session: Session, context: TenantContext) -> ServiceResponse:
        try:
            result = (
                session.execute(text("SELECT * FROM dev_reports ORDER BY created_at DESC"))
                .mappings()
                .all()
            )

            reports = [dict(row) for row in result]
            # Convert timestamps to string for JSON
            for r in reports:
                r["created_at"] = str(r["created_at"])

            return ServiceResponse.success_res(
                data=reports, message=f"Retrieved {len(reports)} reports."
            )
        except Exception as e:
            logger.exception("Error listing reports")
            return ServiceResponse.error_res(f"List error: {str(e)}", "REPORT_LIST_ERROR")


report_commands = ReportCommandHandler()
