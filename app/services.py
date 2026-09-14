def compute_auto_score(criteria_met: int, observation: str, evidence_count: int) -> int:
    """Auto-generate the score from three signals, instead of manual entry:
    - Checklist: how many of the 5 standard criteria are satisfied (60 pts max)
    - Evidence: how many supporting documents are attached (25 pts max, caps at 4 docs)
    - Note quality: how detailed the observation note is (15 pts max, caps at 50 words)
    """
    criteria_met = max(0, min(criteria_met, 5))
    checklist_pts = (criteria_met / 5) * 60

    evidence_count = max(0, evidence_count)
    evidence_pts = (min(evidence_count, 4) / 4) * 25

    word_count = len((observation or "").split())
    note_pts = (min(word_count, 50) / 50) * 15

    return round(checklist_pts + evidence_pts + note_pts)

def maturity(score: int) -> str:
    if score < 40:
        return "Critical / Initial"
    if score < 60:
        return "Needs Improvement"
    if score < 75:
        return "Developing"
    if score < 90:
        return "Proficient"
    return "Excellent / Advanced"

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
