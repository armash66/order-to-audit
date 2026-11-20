from django.core.exceptions import PermissionDenied
from .models import AuditLog

ROLES = ["salesman", "admin", "production", "accountant", "owner"]


def require_role(actor, roles):
    if not actor.is_authenticated or not actor.is_active or not (actor.is_staff or actor.groups.filter(name__in=roles).exists()):
        raise PermissionDenied("Your role cannot perform this action.")


# Audit is called within the same transaction as the mutation, so failure rolls both back.
def audit(actor, action, source, before, after):
    return AuditLog.objects.create(actor=actor, action=action, source_type=source._meta.label,
                                   source_id=source.pk, before=before, after=after)
