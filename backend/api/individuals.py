from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from .. import schemas
from . import api_utils
from .api_utils import fetch_display_names, enrich_created_by
from .auth import EditorSession, get_tree_db, get_tree_owner_info, require_editor, require_owner
from database.owner_info import OwnerInfo
from database.system_db import get_system_db
import database.models


router = APIRouter(prefix="/individuals", tags=["individuals"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _check_edit_permission(session: EditorSession, record_created_by: str | None) -> None:
    """Contributors can only edit records they created themselves."""
    if session.is_contributor and record_created_by != session.editor_id:
        raise HTTPException(status_code=403, detail="Contributors can only edit their own records")


@router.post("", response_model=schemas.Individual)
def create_individual(
    individual: schemas.IndividualCreate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Create a new individual with associated names."""
    gedcom_id = individual.gedcom_id
    if not gedcom_id:
        gedcom_id = f"I{api_utils.generate_gedcom_id(db, database.models.Individual)}"
    else:
        existing = db.query(database.models.Individual).filter(
            database.models.Individual.gedcom_id == gedcom_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="GEDCOM ID already exists")

    now = _now_iso()
    db_individual = database.models.Individual(
        gedcom_id=gedcom_id,
        sex_code=individual.sex_code,
        birth_date=individual.birth_date,
        birth_date_approx=individual.birth_date_approx,
        birth_place=individual.birth_place,
        death_date=individual.death_date,
        death_date_approx=individual.death_date_approx,
        death_place=individual.death_place,
        notes=individual.notes,
        created_by=session.editor_id,
        created_at=now,
    )

    for name_in in individual.names:
        db_name = database.models.IndividualName(
            given_name=name_in.given_name,
            family_name=name_in.family_name,
            name_type=name_in.name_type,
            prefix=name_in.prefix,
            suffix=name_in.suffix,
            name_order=name_in.name_order,
            individual=db_individual,
            created_by=session.editor_id,
            created_at=now,
        )
        db.add(db_name)

    db.add(db_individual)
    db.commit()
    db.refresh(db_individual)
    result = schemas.Individual.model_validate(db_individual)
    return result.model_copy(update={"created_by_display_name": session.display_name})


@router.get("", response_model=List[schemas.Individual])
def read_individuals(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tree_db),
    db_sys: Session = Depends(get_system_db),
):
    """Read list of individuals with pagination."""
    db_rows = (
        db.query(database.models.Individual)
        .options(joinedload(database.models.Individual.names))
        .offset(skip)
        .limit(limit)
        .all()
    )
    name_map = fetch_display_names({i.created_by for i in db_rows if i.created_by}, db_sys)
    return [enrich_created_by(schemas.Individual.model_validate(i), name_map) for i in db_rows]


@router.delete("/all")
def delete_all_individuals(
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_tree_db),
    owner: OwnerInfo = Depends(get_tree_owner_info),
):
    """Delete all individuals and related families, events, media for the current tree.

    Owner-only. Helper/lookup tables are preserved. Media files on disk are removed.
    """
    media_dir = Path(owner.media_dir)
    media_files = [
        m.file_path for m in db.query(database.models.Media).all() if m.file_path
    ]

    individual_count = db.query(database.models.Individual).count()
    family_count = db.query(database.models.Family).count()
    event_count = db.query(database.models.Event).count()
    media_count = db.query(database.models.Media).count()

    # Cascade rules drop names, family-memberships, events, media tied to individuals.
    # Families themselves and family-only events/media are not cascaded — delete explicitly.
    db.query(database.models.Individual).delete(synchronize_session=False)
    db.query(database.models.Family).delete(synchronize_session=False)
    db.commit()

    for rel_path in media_files:
        try:
            file_path = media_dir / rel_path
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    return {
        "detail": "Tree reset",
        "deleted": {
            "individuals": individual_count,
            "families": family_count,
            "events": event_count,
            "media": media_count,
        },
    }


@router.get("/{individual_id}", response_model=schemas.Individual)
def read_individual_by_id(
    individual_id: int,
    db: Session = Depends(get_tree_db),
    db_sys: Session = Depends(get_system_db),
):
    """Read a single individual by ID."""
    individual = (
        db.query(database.models.Individual)
        .options(joinedload(database.models.Individual.names))
        .filter(database.models.Individual.id == individual_id)
        .first()
    )
    if individual is None:
        raise HTTPException(status_code=404, detail="Individual not found")
    name_map = fetch_display_names({individual.created_by} if individual.created_by else set(), db_sys)
    return enrich_created_by(schemas.Individual.model_validate(individual), name_map)


@router.put("/{individual_id}", response_model=schemas.Individual)
def update_individual(
    individual_id: int,
    individual_update: schemas.IndividualUpdate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Update an individual."""
    individual = db.query(database.models.Individual).filter(
        database.models.Individual.id == individual_id
    ).first()
    if individual is None:
        raise HTTPException(status_code=404, detail="Individual not found")

    _check_edit_permission(session, individual.created_by)

    update_data = individual_update.model_dump(exclude_unset=True)

    if "birth_date" in update_data and update_data["birth_date"] is not None:
        update_data["birth_date_approx"] = None
    if "birth_date_approx" in update_data and update_data["birth_date_approx"] is not None:
        update_data["birth_date"] = None
    if "death_date" in update_data and update_data["death_date"] is not None:
        update_data["death_date_approx"] = None
    if "death_date_approx" in update_data and update_data["death_date_approx"] is not None:
        update_data["death_date"] = None

    now = _now_iso()
    for key, value in update_data.items():
        if key == "names":
            if value is not None:
                individual.names.clear()
                for idx, name_in in enumerate(value):
                    db_name = database.models.IndividualName(
                        given_name=name_in.get("given_name"),
                        family_name=name_in.get("family_name"),
                        name_type=name_in.get("name_type"),
                        prefix=name_in.get("prefix"),
                        suffix=name_in.get("suffix"),
                        name_order=name_in.get("name_order", idx),
                        individual=individual,
                        created_by=session.editor_id,
                        created_at=now,
                    )
                    db.add(db_name)
        elif hasattr(individual, key):
            setattr(individual, key, value)

    db.commit()
    db.refresh(individual)
    return individual


@router.delete("/{individual_id}")
def delete_individual(
    individual_id: int,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Delete an individual. Contributors may only delete their own records."""
    individual = db.query(database.models.Individual).filter(
        database.models.Individual.id == individual_id
    ).first()
    if individual is None:
        raise HTTPException(status_code=404, detail="Individual not found")

    _check_edit_permission(session, individual.created_by)
    db.delete(individual)
    db.commit()
    return {"detail": "Individual deleted"}
