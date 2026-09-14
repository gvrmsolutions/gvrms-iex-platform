from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Action, Domain
from ..schemas import ActionIn, ActionStatusIn
from ..security import current_user
from ..services import log_audit

router = APIRouter(prefix="/api/actions", tags=["Corrective Actions"])

@router.post("")
def create_action(data: ActionIn, db: Session = Depends(get_db), user=Depends(current_user)):
    row = Action(organization_id=user.organization_id, **data.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_action", "action", row.id, row.title)
    return {"id": row.id, "status": row.status}

@router.post("/seed-defaults")
def seed_default_actions(db: Session = Depends(get_db), user=Depends(current_user)):
    """Create one suggested corrective action for every domain that doesn't
    already have an action logged. Safe to call more than once."""
    existing_codes = {
        code for (code,) in db.query(Action.domain_code)
        .filter(Action.organization_id == user.organization_id).distinct()
    }
    domains = db.query(Domain).order_by(Domain.code).all()
    created = []
    for d in domains:
        if d.code in existing_codes:
            continue
        row = Action(
            organization_id=user.organization_id,
            domain_code=d.code,
            title=f"Strengthen {d.name}",
            description=f"Baseline improvement plan for {d.code} — {d.description}",
            priority="Medium",
            status="Not Started",
        )
        db.add(row)
        created.append(d.code)
    db.commit()
    log_audit(db, user.organization_id, user.id, "seed_default_actions", "action", None,
              f"created defaults for {len(created)} domains")
    return {"created_count": len(created), "domain_codes": created}

@router.patch("/{action_id}/status")
def update_action_status(action_id: int, data: ActionStatusIn, db: Session = Depends(get_db), user=Depends(current_user)):
    row = db.get(Action, action_id)
    if not row or row.organization_id != user.organization_id:
        raise HTTPException(404, "Action not found")
    row.status = data.status
    db.commit()
    log_audit(db, user.organization_id, user.id, "update_action_status", "action", row.id, data.status)
    return {"id": row.id, "status": row.status}

@router.get("")
def actions(db: Session = Depends(get_db), user=Depends(current_user)):
    rows=db.query(Action).filter(Action.organization_id==user.organization_id).order_by(Action.id.desc()).all()
    return [{
        "id":r.id,"domain_code":r.domain_code,"title":r.title,"description":r.description,
        "owner_id":r.owner_id,"due_date":r.due_date,"priority":r.priority,"status":r.status
    } for r in rows]
