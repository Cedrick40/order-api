from django.db import transaction

from apps.audit.services import record_audit


@transaction.atomic
def change_role(*, user, new_role, actor):
    before = user.role
    user.role = new_role
    user.save(update_fields=["role"])
    record_audit(
        actor=actor, action="user.role_changed", entity_type="user", entity_id=user.id,
        before={"role": before}, after={"role": new_role},
    )
    return user