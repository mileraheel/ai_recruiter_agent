"""
Candidate document upload -- passport copy, visa copy, I-94, degree
certificate, etc. Same pending-until-admin-approved gate as resumes and
skills. Nothing here is usable by any future automated reply/document-
attachment engine until status='approved'.
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_app_storage, get_current_candidate, get_db
from db.models import Candidate, CandidateDocument, Organization
from services.candidate_directory import generated_storage_prefix
from services.storage import Storage

router = APIRouter(prefix="/api/me/documents", tags=["candidate-documents"], dependencies=[Depends(get_current_candidate)])

_MAX_DOCUMENT_BYTES = 15 * 1024 * 1024  # 15MB -- generous for scanned PDFs/images, still bounded


@router.get("")
def list_my_documents(candidate: Candidate = Depends(get_current_candidate), db: Session = Depends(get_db)):
    docs = db.query(CandidateDocument).filter_by(candidate_id=candidate.id).order_by(CandidateDocument.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "document_type": d.document_type,
            "file_name": d.file_name,
            "status": d.status,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.post("")
async def upload_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    candidate: Candidate = Depends(get_current_candidate),
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_app_storage),
):
    if not document_type.strip():
        raise HTTPException(status_code=422, detail="document_type is required (e.g. 'Passport Copy', 'I-94').")

    content = await file.read()
    if len(content) > _MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 15MB).")

    org = db.query(Organization).filter_by(id=candidate.organization_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=500, detail="Candidate has no organization on record.")

    file_hash = hashlib.sha256(content).hexdigest()[:10]
    safe_name = (file.filename or "document").replace("/", "_").replace("\\", "_")
    storage_key = f"{generated_storage_prefix(org.name, candidate.slug)}/documents/{file_hash}_{safe_name}"
    storage.save(storage_key, content)

    doc = CandidateDocument(
        candidate_id=candidate.id,
        document_type=document_type.strip(),
        file_name=safe_name,
        storage_key=storage_key,
        status="pending",
        uploaded_by="candidate",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {
        "id": doc.id,
        "document_type": doc.document_type,
        "status": doc.status,
        "message": "Document uploaded and pending admin approval.",
    }
