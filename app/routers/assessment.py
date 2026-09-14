from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Assessment, Indicator
from ..schemas import AssessmentIn
from ..security import current_user
from ..services import maturity, log_audit

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])

@router.post("")
def create_assessment(data: AssessmentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    indicator = db.get(Indicator, data.indicator_id)
    if not indicator:
        raise HTTPException(404, "Indicator not found")
    score = min(data.score, 100)
    row = Assessment(
        organization_id=user.organization_id,
        campus_id=data.campus_id,
        department_id=data.department_id,
        indicator_id=indicator.id,
        score=score,
        maturity=maturity(score),
        observation=data.observation,
        assessed_by=user.id
    )
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_assessment", "assessment", row.id,
              f"{indicator.code} scored {score}")
    return {"id": row.id, "indicator_id": row.indicator_id, "score": row.score, "maturity": row.maturity}

@router.put("/{assessment_id}")
def update_assessment(assessment_id: int, data: AssessmentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    row = db.query(Assessment).filter(
        Assessment.id == assessment_id,
        Assessment.organization_id == user.organization_id
    ).first()
    if not row:
        raise HTTPException(404, "Assessment not found")

    score = min(data.score, 100)
    row.score = score
    row.maturity = maturity(score)
    row.observation = data.observation

    db.commit()
    db.refresh(row)
    log_audit(db, user.organization_id, user.id, "update_assessment", "assessment", row.id,
              f"score changed to {score}")
    return {"id": row.id, "indicator_id": row.indicator_id, "score": row.score, "maturity": row.maturity}

@router.get("")
def assessments(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Assessment).filter(Assessment.organization_id == user.organization_id).order_by(Assessment.assessed_at.desc()).all()
    return [{
        "id": r.id,
        "indicator_id": r.indicator_id,
        "indicator": r.indicator.title,
        "score": r.score,
        "maturity": r.maturity,
        "observation": r.observation,
        "assessed_at": r.assessed_at
    } for r in rows]
