from core.request_context import request_id_var

from .models import AuditLog


def record_audit(*, actor, action, entity_type, entity_id, before=None, after=None):
    """Call this INSIDE the same transaction as the change it describes."""
    is_user = actor is not None and getattr(actor, "is_authenticated", False)
    return AuditLog.objects.create(
        actor=actor if is_user else None,
        actor_email=actor.email if is_user else "",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        request_id=request_id_var.get(),
    )