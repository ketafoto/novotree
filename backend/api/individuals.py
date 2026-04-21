from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from .. import schemas
from . import api_utils
from .auth import EditorSession, get_tree_db, require_editor, require_owner
from database.system_db import get_system_db
from database.system_models import AuthEditor
import database.models


router = APIRouter(prefix="/individuals", tags=["individuals"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_display_names(editor_ids: set, db_sys: Session) -> dict:
    """Batch-fetch editor display names from the system DB."""
    if not editor_ids:
        return {}
    rows = db_sys.query(AuthEditor.editor_id, AuthEditor.display_name).filter(
        AuthEditor.editor_id.in_(editor_ids)
    ).all()
    return {r.editor_id: r.display_name for r in rows}


def _enrich(ind: schemas.Individual, name_map: dict) -> schemas.Individual:
    """Return ind with created_by_display_name populated from name_map."""
    if ind.created_by and ind.created_by in name_map:
        return ind.model_copy(update={"created_by_display_name": name_map[ind.created_by]})
    return ind


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
    orm_list = (
        db.query(database.models.Individual)
        .options(joinedload(database.models.Individual.names))
        .offset(skip)
        .limit(limit)
        .all()
    )
    name_map = _fetch_display_names({i.created_by for i in orm_list if i.created_by}, db_sys)
    return [_enrich(schemas.Individual.model_validate(i), name_map) for i in orm_list]


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
    name_map = _fetch_display_names({individual.created_by} if individual.created_by else set(), db_sys)
    return _enrich(schemas.Individual.model_validate(individual), name_map)


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
