from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Assessment, Domain, Indicator, Action
from ..security import current_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)

@router.get("")
def dashboard(
    db: Session = Depends(get_db),
    user=Depends(current_user)
):
    scores = [
        x[0]
        for x in db.query(Assessment.score)
        .filter(Assessment.organization_id == user.organization_id)
        .all()
    ]

    # Overall score is now calculated on a 1–5 scale
    overall = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "overall_score": overall,

        "assessments": len(scores),

        # 1–5 maturity bands
        "critical": sum(x <= 1 for x in scores),

        "needs_improvement": sum(x == 2 for x in scores),

        "good": sum(x == 3 or x == 4 for x in scores),

        "excellent": sum(x >= 5 for x in scores),

        "open_actions": db.query(
            func.count(Action.id)
        ).filter(
            Action.organization_id == user.organization_id,
            Action.status != "Completed"
        ).scalar()
    }
