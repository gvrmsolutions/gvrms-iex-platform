def maturity(score: int) -> str:
    if score < 50:
        return "Critical"
    if score < 75:
        return "Needs Improvement"
    if score < 90:
        return "Good"
    return "Excellent"

def log_audit(db, organization_id, user_id, action, entity="", entity_id=None, details=""):
    from .models import AuditLog
    row = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
    )
    db.add(row)
    db.commit()
