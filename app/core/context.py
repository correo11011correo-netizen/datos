from dataclasses import dataclass


@dataclass
class TenantContext:
    """
    Contexto del inquilino actual para operaciones multi-tenant.
    """

    tenant_id: str
