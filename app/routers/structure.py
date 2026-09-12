from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Campus, Department
from ..schemas import CampusIn, DepartmentIn
from ..security import current_user, require_roles
from ..services import log_audit

router = APIRouter(prefix="/api/structure", tags=["Institution Structure"])

@router.get("/campuses")
def list_campuses(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Campus).filter(Campus.organization_id == user.organization_id).all()
    return [{"id": c.id, "name": c.name, "departments": [{"id": d.id, "name": d.name} for d in c.departments]} for c in rows]

@router.post("/campuses")
def create_campus(data: CampusIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "principal"))):
    row = Campus(organization_id=user.organization_id, name=data.name)
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_campus", "campus", row.id, row.name)
    return {"id": row.id, "name": row.name}

@router.post("/departments")
def create_department(data: DepartmentIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "principal"))):
    campus = db.get(Campus, data.campus_id)
    if not campus or campus.organization_id != user.organization_id:
        raise HTTPException(404, "Campus not found")
    row = Department(campus_id=data.campus_id, name=data.name)
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "create_department", "department", row.id, row.name)
    return {"id": row.id, "name": row.name, "campus_id": row.campus_id}
