from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Organization
from ..schemas import OrgProfileIn
from ..security import current_user, require_roles
from ..services import log_audit

router = APIRouter(prefix="/api/org", tags=["Institution Profile"])

def _org_view(org: Organization):
    return {
        "id": org.id,
        "name": org.name,
        "code": org.code,
        "address": org.address,
        "phone": org.phone,
        "principal_name": org.principal_name,
        "academic_year": org.academic_year,
        "student_strength": org.student_strength,
    }

@router.get("")
def get_org(db: Session = Depends(get_db), user=Depends(current_user)):
    org = db.get(Organization, user.organization_id)
    return _org_view(org)

@router.patch("")
def update_org(data: OrgProfileIn, db: Session = Depends(get_db), user=Depends(require_roles("admin", "principal"))):
    org = db.get(Organization, user.organization_id)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(org, key, value)
    db.commit()
    log_audit(db, user.organization_id, user.id, "update_org_profile", "organization", org.id,
               ", ".join(updates.keys()))
    return _org_view(org)
