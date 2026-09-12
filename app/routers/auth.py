from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Organization, User
from ..schemas import RegisterIn, LoginIn
from ..security import hash_password, verify_password, create_token, current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.get("/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "organization_id": user.organization_id}

@router.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(409, "Email already registered")
    if db.query(Organization).filter(Organization.code == data.organization_code).first():
        raise HTTPException(409, "Organization code already exists")
    org = Organization(name=data.organization_name, code=data.organization_code)
    db.add(org); db.flush()
    user = User(
        organization_id=org.id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="admin"
    )
    db.add(user); db.commit(); db.refresh(user)
    from ..services import log_audit
    log_audit(db, org.id, user.id, "register", "organization", org.id, data.organization_name)
    return {"access_token": create_token(user), "token_type": "bearer", "role": user.role, "name": user.name}

@router.post("/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    from ..services import log_audit
    log_audit(db, user.organization_id, user.id, "login", "user", user.id)
    return {"access_token": create_token(user), "token_type": "bearer", "role": user.role, "name": user.name}
