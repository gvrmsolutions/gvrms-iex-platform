from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Assessment, Indicator, Evidence
from ..schemas import AssessmentIn
from ..security import current_user
from ..services import maturity, compute_auto_score, log_audit

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])

@router.post("")
def create_assessment(data: AssessmentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    indicator = db.get(Indicator, data.indicator_id)
    if not indicator:
        raise HTTPException(404, "Indicator not found")
    # New assessment has no evidence attached yet (evidence is uploaded against
    # its id afterwards, which then triggers a score recalculation).
    score = compute_auto_score(data.criteria_met, data.observation, evidence_count=0)
    row = Assessment(
        organization_id=user.organization_id,
        campus_id=data.campus_id,
        department_id=data.department_id,
        indicator_id=indicator.id,
        score=score,
        criteria_met=data.criteria_met,
        maturity=maturity(score),
        observation=data.observation,
        assessed_by=user.id
    )
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_assessment", "assessment", row.id,
              f"{indicator.code} auto-scored {score} (criteria_met={data.criteria_met})")
    return {"id": row.id, "indicator_id": row.indicator_id, "score": row.score, "maturity": row.maturity}

@router.put("/{assessment_id}")
def update_assessment(assessment_id: int, data: AssessmentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    row = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.organization_id == user.organization_id
    ).first()
    if not row:
        raise HTTPException(404, "Assessment not found")

    evidence_count = db.query(Evidence).filter(Evidence.assessment_id == assessment_id).count()
    score = compute_auto_score(data.criteria_met, data.observation, evidence_count)
    row.criteria_met = data.criteria_met
    row.score = score
    row.maturity = maturity(score)
    row.observation = data.observation

    db.commit()
    db.refresh(row)
    log_audit(db, user.organization_id, user.id, "update_assessment", "assessment", row.id,
              f"re-scored to {score} (criteria_met={data.criteria_met}, evidence={evidence_count})")
    return {"id": row.id, "indicator_id": row.indicator_id, "score": row.score, "maturity": row.maturity}

@router.get("")
def assessments(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Assessment).filter(Assessment.organization_id == user.organization_id).order_by(Assessment.assessed_at.desc()).all()
    return [{
        "id": r.id,
        "indicator_id": r.indicator_id,
        "indicator": r.indicator.title,
        "score": r.score,
        "criteria_met": r.criteria_met,
        "maturity": r.maturity,
        "observation": r.observation,
        "assessed_at": r.assessed_at
    } for r in rows]
