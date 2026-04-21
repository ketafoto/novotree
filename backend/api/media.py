import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from datetime import datetime, timezone

from .. import schemas
import database.models
from database.owner_info import OwnerInfo
from .auth import EditorSession, get_tree_db, get_tree_owner_info, get_viewer_tree_db, get_viewer_owner_info, require_editor, require_owner


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_edit_permission(session: EditorSession, record_created_by: str | None) -> None:
    if session.is_contributor and record_created_by != session.editor_id:
        raise HTTPException(status_code=403, detail="Contributors can only edit their own records")

logger = logging.getLogger("novotree.backend")

router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
MAX_PHOTO_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/upload", response_model=schemas.Media)
async def upload_photo(
    file: UploadFile = File(...),
    individual_id: int = Form(...),
    age_on_photo: int = Form(...),
    is_default: bool = Form(False),
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
    owner: OwnerInfo = Depends(get_tree_owner_info),
):
    """Upload a cropped photo for an individual.

    The frontend sends the already-cropped JPEG regardless of the original
    format.  The file is stored under ``<media_dir>/<GEDCOM_ID>_<age>.jpg``.
    """
    individual = (
        db.query(database.models.Individual)
        .filter(database.models.Individual.id == individual_id)
        .first()
    )
    if not individual:
        raise HTTPException(status_code=404, detail="Individual not found")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: JPEG, PNG, WebP, HEIC/HEIF",
        )

    data = await file.read()
    if len(data) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    media_dir = Path(owner.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)

    gedcom_id = individual.gedcom_id or f"ID{individual.id}"
    base_name = f"{gedcom_id}_{age_on_photo}"
    file_path = media_dir / f"{base_name}.jpg"
    counter = 2
    while file_path.exists():
        file_path = media_dir / f"{base_name}_{counter}.jpg"
        counter += 1

    file_path.write_bytes(data)

    if is_default:
        _clear_defaults(db, individual_id)

    db_media = database.models.Media(
        individual_id=individual_id,
        file_path=file_path.name,
        media_type_code="photo",
        is_default=1 if is_default else 0,
        age_on_photo=age_on_photo,
        created_by=session.editor_id,
        created_at=_now_iso(),
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media


@router.get("/{media_id}/file")
def serve_media_file(
    media_id: int,
    db: Session = Depends(get_viewer_tree_db),
    owner: OwnerInfo = Depends(get_viewer_owner_info),
):
    """Serve a media file by its database ID."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if not media or not media.file_path:
        raise HTTPException(status_code=404, detail="Media file not found")

    file_path = Path(owner.media_dir) / media.file_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type="image/jpeg",
        filename=file_path.name,
    )


@router.put("/{media_id}/set-default", response_model=schemas.Media)
def set_default_photo(
    media_id: int,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Mark a photo as the default for its individual."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    if not media.individual_id:
        raise HTTPException(status_code=400, detail="Media is not linked to an individual")

    _clear_defaults(db, media.individual_id)
    media.is_default = 1
    db.commit()
    db.refresh(media)
    return media


@router.put("/{media_id}/re-crop", response_model=schemas.Media)
async def recrop_photo(
    media_id: int,
    file: UploadFile = File(...),
    age_on_photo: int = Form(...),
    is_default: bool = Form(False),
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
    owner: OwnerInfo = Depends(get_tree_owner_info),
):
    """Replace an existing photo file with a newly cropped version."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    if media.media_type_code != "photo":
        raise HTTPException(status_code=400, detail="Media is not a photo")
    if not media.file_path:
        raise HTTPException(status_code=400, detail="Media has no file path")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: JPEG, PNG, WebP, HEIC/HEIF",
        )

    data = await file.read()
    if len(data) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit")

    file_path = Path(owner.media_dir) / media.file_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(data)

    if media.individual_id:
        if is_default:
            _clear_defaults(db, media.individual_id)
        media.is_default = 1 if is_default else 0

    media.age_on_photo = age_on_photo
    db.commit()
    db.refresh(media)
    return media


# ── Standard CRUD ────────────────────────────────────────────────────────────

@router.post("", response_model=schemas.Media)
def create_media(
    media: schemas.MediaCreate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Create a new media record."""
    db_media = database.models.Media(
        individual_id=media.individual_id,
        family_id=media.family_id,
        file_path=media.file_path,
        media_type_code=media.media_type_code,
        media_date=media.media_date,
        description=media.description,
        is_default=1 if media.is_default else 0,
        age_on_photo=media.age_on_photo,
        created_by=session.editor_id,
        created_at=_now_iso(),
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media


@router.get("", response_model=List[schemas.Media])
def read_media(
    skip: int = 0,
    limit: int = 100,
    individual_id: Optional[int] = None,
    family_id: Optional[int] = None,
    db: Session = Depends(get_viewer_tree_db),
):
    """Read list of media with optional filtering."""
    query = db.query(database.models.Media)
    if individual_id:
        query = query.filter(database.models.Media.individual_id == individual_id)
    if family_id:
        query = query.filter(database.models.Media.family_id == family_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{media_id}", response_model=schemas.Media)
def read_media_by_id(
    media_id: int,
    db: Session = Depends(get_viewer_tree_db),
):
    """Read a single media record by ID."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return media


@router.put("/{media_id}", response_model=schemas.Media)
def update_media(
    media_id: int,
    media_update: schemas.MediaUpdate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Update a media record."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    _check_edit_permission(session, media.created_by)

    update_data = media_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(media, key):
            setattr(media, key, value)

    db.commit()
    db.refresh(media)
    return media


@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
    owner: OwnerInfo = Depends(get_tree_owner_info),
):
    """Delete a media record and its file on disk. Contributors may only delete their own records."""
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.id == media_id)
        .first()
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    _check_edit_permission(session, media.created_by)

    if media.file_path:
        file_path = Path(owner.media_dir) / media.file_path
        if file_path.exists():
            file_path.unlink()

    db.delete(media)
    db.commit()
    return {"detail": "Media deleted"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clear_defaults(db: Session, individual_id: int):
    """Clear the is_default flag on all photos of the given individual."""
    db.query(database.models.Media).filter(
        database.models.Media.individual_id == individual_id,
        database.models.Media.is_default == 1,
    ).update({"is_default": 0})
