from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Domain, Indicator
from ..security import current_user

router = APIRouter(prefix="/api/domains", tags=["Domains"])

@router.get("")
def domains(db: Session = Depends(get_db), user=Depends(current_user)):
    return [{
        "code": d.code,
        "name": d.name,
        "description": d.description,
        "indicator_count": len(d.indicators)
    } for d in db.query(Domain).order_by(Domain.code).all()]

@router.get("/{code}")
def domain_detail(code: str, db: Session = Depends(get_db), user=Depends(current_user)):
    d = db.query(Domain).filter(Domain.code == code.upper()).first()
    if not d:
        raise HTTPException(404, "Domain not found")
    return {
        "code": d.code, "name": d.name, "description": d.description,
        "indicators": [{
            "id": i.id, "code": i.code, "title": i.title,
            "description": i.description, "max_score": i.max_score
        } for i in d.indicators]
    }
