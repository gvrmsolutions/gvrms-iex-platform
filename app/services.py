def compute_auto_score(criteria_met: int, observation: str, evidence_count: int) -> int:
    """Automatically generate an assessment score from 1 to 5.

    Signals:
    - Checklist completion: 60%
    - Evidence documents: 25%
    - Observation note detail: 15%

    No manual score entry is required.
    """

    criteria_met = max(0, min(criteria_met, 5))
    evidence_count = max(0, evidence_count)

    # Checklist: 60 points
    checklist_pts = (criteria_met / 5) * 60

    # Evidence: 25 points, maximum 4 documents
    evidence_pts = (min(evidence_count, 4) / 4) * 25

    # Observation: 15 points, maximum 50 words
    word_count = len((observation or "").split())
    note_pts = (min(word_count, 50) / 50) * 15

    # Total automatic score: 0–100
    total_score = checklist_pts + evidence_pts + note_pts

    # Convert 0–100 into final 1–5 assessment score
    if total_score <= 20:
        return 1
    elif total_score <= 40:
        return 2
    elif total_score <= 60:
        return 3
    elif total_score <= 80:
        return 4
    else:
        return 5

def maturity(score: int) -> str:
    if score <= 1:
        return "Critical / Initial"
    if score == 2:
        return "Needs Improvement"
    if score == 3:
        return "Developing"
    if score == 4:
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
