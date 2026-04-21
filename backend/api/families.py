from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from .. import schemas
from .auth import EditorSession, get_tree_db, require_editor, require_owner
from .api_utils import generate_gedcom_id
import database.models


router = APIRouter(prefix="/families", tags=["families"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_edit_permission(session: EditorSession, record_created_by: str | None) -> None:
    if session.is_contributor and record_created_by != session.editor_id:
        raise HTTPException(status_code=403, detail="Contributors can only edit their own records")


@router.post("", response_model=schemas.Family)
def create_family(
    family: schemas.FamilyCreate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Create a new family."""
    gedcom_id = family.gedcom_id
    if not gedcom_id:
        gedcom_id = f"F{generate_gedcom_id(db, database.models.Family)}"
    else:
        existing = db.query(database.models.Family).filter(
            database.models.Family.gedcom_id == gedcom_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="GEDCOM ID already exists")

    now = _now_iso()
    db_family = database.models.Family(
        gedcom_id=gedcom_id,
        marriage_date=family.marriage_date,
        marriage_date_approx=family.marriage_date_approx,
        marriage_place=family.marriage_place,
        divorce_date=family.divorce_date,
        divorce_date_approx=family.divorce_date_approx,
        family_type=family.family_type or "marriage",
        notes=family.notes,
        created_by=session.editor_id,
        created_at=now,
    )

    for member_in in family.members:
        db.add(database.models.FamilyMember(
            individual_id=member_in.individual_id,
            role=member_in.role,
            family=db_family,
        ))

    for child_in in family.children:
        db.add(database.models.FamilyChild(
            child_id=child_in.child_id,
            family=db_family,
        ))

    db.add(db_family)
    db.commit()
    db.refresh(db_family)
    return db_family


@router.get("", response_model=List[schemas.Family])
def read_families(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tree_db),
):
    return (
        db.query(database.models.Family)
        .options(
            joinedload(database.models.Family.members),
            joinedload(database.models.Family.children),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{family_id}", response_model=schemas.Family)
def read_family(
    family_id: int,
    db: Session = Depends(get_tree_db),
):
    family = (
        db.query(database.models.Family)
        .options(
            joinedload(database.models.Family.members),
            joinedload(database.models.Family.children),
        )
        .filter(database.models.Family.id == family_id)
        .first()
    )
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.put("/{family_id}", response_model=schemas.Family)
def update_family(
    family_id: int,
    family_update: schemas.FamilyUpdate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    family = db.query(database.models.Family).filter(
        database.models.Family.id == family_id
    ).first()
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    _check_edit_permission(session, family.created_by)

    update_data = family_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key == "members":
            if value is not None:
                family.members.clear()
                for member_in in value:
                    db.add(database.models.FamilyMember(
                        individual_id=member_in["individual_id"],
                        role=member_in.get("role"),
                        family=family,
                    ))
        elif key == "children":
            if value is not None:
                family.children.clear()
                for child_in in value:
                    db.add(database.models.FamilyChild(
                        child_id=child_in["child_id"],
                        family=family,
                    ))
        elif hasattr(family, key):
            setattr(family, key, value)

    db.commit()
    db.refresh(family)
    return family


@router.delete("/{family_id}")
def delete_family(
    family_id: int,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Delete a family. Contributors may only delete their own records."""
    family = db.query(database.models.Family).filter(
        database.models.Family.id == family_id
    ).first()
    if family is None:
        raise HTTPException(status_code=404, detail="Family not found")

    _check_edit_permission(session, family.created_by)
    db.delete(family)
    db.commit()
    return {"detail": "Family deleted"}
