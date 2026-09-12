from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Action
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
