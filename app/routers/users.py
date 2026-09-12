from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User
from ..schemas import UserIn
from ..security import hash_password, require_roles, current_user
from ..services import log_audit

router = APIRouter(prefix="/api/users", tags=["Users & Roles"])

ROLES = ["admin", "principal", "iqac", "consultant"]

@router.get("")
def list_users(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(User).filter(User.organization_id == user.organization_id).order_by(User.id).all()
    return [{"id": r.id, "name": r.name, "email": r.email, "role": r.role, "is_active": r.is_active} for r in rows]

@router.post("")
def create_user(data: UserIn, db: Session = Depends(get_db), user=Depends(require_roles("admin"))):
    if data.role not in ROLES:
        raise HTTPException(400, f"role must be one of {ROLES}")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(409, "Email already registered")
    row = User(
        organization_id=user.organization_id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_user", "user", row.id, f"{row.email} as {row.role}")
    return {"id": row.id, "name": row.name, "email": row.email, "role": row.role}
