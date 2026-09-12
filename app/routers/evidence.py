import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Evidence
from ..schemas import EvidenceIn
from ..security import current_user
from ..config import settings
from ..services import log_audit

router = APIRouter(prefix="/api/evidence", tags=["Evidence"])

@router.post("")
def add_evidence(data: EvidenceIn, db: Session = Depends(get_db), user=Depends(current_user)):
    row = Evidence(organization_id=user.organization_id, uploaded_by=user.id, **data.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "add_evidence", "evidence", row.id, row.file_name)
    return {"id": row.id, "file_name": row.file_name, "storage_key": row.storage_key}

@router.post("/upload")
async def upload_evidence(assessment_id: int | None = None, file: UploadFile = File(...),
                           db: Session = Depends(get_db), user=Depends(current_user)):
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix
    storage_key = f"org{user.organization_id}/{uuid.uuid4().hex}{ext}"
    dest = upload_dir / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    row = Evidence(
        organization_id=user.organization_id,
        assessment_id=assessment_id,
        file_name=file.filename,
        storage_key=storage_key,
        mime_type=file.content_type or "",
        uploaded_by=user.id,
    )
    db.add(row); db.commit(); db.refresh(row)
    log_audit(db, user.organization_id, user.id, "upload_evidence", "evidence", row.id, row.file_name)
    return {"id": row.id, "file_name": row.file_name, "storage_key": row.storage_key}

@router.get("")
def list_evidence(db: Session = Depends(get_db), user=Depends(current_user)):
    rows = db.query(Evidence).filter(Evidence.organization_id == user.organization_id).order_by(Evidence.id.desc()).all()
    return [{"id": r.id, "assessment_id": r.assessment_id, "file_name": r.file_name,
             "storage_key": r.storage_key, "mime_type": r.mime_type, "uploaded_at": r.uploaded_at} for r in rows]

@router.get("/{evidence_id}/download")
def download_evidence(evidence_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    row = db.get(Evidence, evidence_id)
    if not row or row.organization_id != user.organization_id:
        raise HTTPException(404, "Evidence not found")
    path = Path(settings.upload_dir) / row.storage_key
    if not path.exists():
        raise HTTPException(404, "File not found on disk (metadata-only record)")
    return FileResponse(str(path), filename=row.file_name)
