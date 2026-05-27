from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from typing import Any, List

from .. import schemas
from . import api_utils
from .api_utils import fetch_display_names, enrich_created_by
from .auth import EditorSession, get_tree_db, get_tree_owner_info, require_editor, require_owner
from database.owner_info import OwnerInfo
from database.system_db import get_system_db
import database.models

INDIVIDUAL_DATA_EXPORT_SCHEMA_VERSION = "1.0"
INDIVIDUAL_DATA_EXPORT_FILENAME_PREFIX = "novotree"


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


def _attribution(row: Any, name_map: dict) -> dict:
    """Return created_by / created_by_display_name / created_at for any attributed row.

    Display name is resolved best-effort: if the editor was deleted from the system
    DB after stamping the row, created_by_display_name is None and the raw
    created_by editor_id is the only handle the export carries.
    """
    created_by = getattr(row, "created_by", None)
    return {
        "created_by": created_by,
        "created_by_display_name": name_map.get(created_by) if created_by else None,
        "created_at": getattr(row, "created_at", None),
    }


def _date_str(value: Any) -> Any:
    """ISO-format date columns; pass everything else through unchanged."""
    return value.isoformat() if isinstance(value, date) else value


@router.get("/{individual_id}/data-export")
def export_individual_data(
    individual_id: int,
    session: EditorSession = Depends(require_owner),
    db: Session = Depends(get_tree_db),
    db_sys: Session = Depends(get_system_db),
):
    """Right-of-access export for a single Individual (privacy §2.6 / M-09).

    Owner-only. Returns a JSON document with every field, event, media reference,
    and family connection touching this individual, plus contributor attribution
    (created_by / created_at) on each row that carries it. Delivered as an
    attachment so the browser shows a save dialog.
    """
    individual = (
        db.query(database.models.Individual)
        .options(joinedload(database.models.Individual.names))
        .filter(database.models.Individual.id == individual_id)
        .first()
    )
    if individual is None:
        raise HTTPException(status_code=404, detail="Individual not found")

    events = (
        db.query(database.models.Event)
        .filter(database.models.Event.individual_id == individual_id)
        .all()
    )
    media = (
        db.query(database.models.Media)
        .filter(database.models.Media.individual_id == individual_id)
        .all()
    )

    member_links = (
        db.query(database.models.FamilyMember)
        .filter(database.models.FamilyMember.individual_id == individual_id)
        .all()
    )
    child_links = (
        db.query(database.models.FamilyChild)
        .filter(database.models.FamilyChild.child_id == individual_id)
        .all()
    )
    family_ids = {link.family_id for link in member_links} | {link.family_id for link in child_links}
    families = (
        db.query(database.models.Family)
        .filter(database.models.Family.id.in_(family_ids))
        .all()
        if family_ids else []
    )

    editor_ids = set()
    for row in (individual, *individual.names, *events, *media, *families):
        if getattr(row, "created_by", None):
            editor_ids.add(row.created_by)
    name_map = fetch_display_names(editor_ids, db_sys)

    payload = {
        "_meta": {
            "schema_version": INDIVIDUAL_DATA_EXPORT_SCHEMA_VERSION,
            "exported_at": _now_iso(),
            "individual_id": individual_id,
            "owner_id": session.owner_id,
            "notes": [
                "updated_by / updated_at are not yet tracked; will appear once Tier 3 §4.6 lands.",
                "FamilyMember / FamilyChild join rows carry no per-link attribution; "
                "the parent Family record's created_by/created_at applies. See docs/notes.txt.",
            ],
        },
        "individual": {
            "id": individual.id,
            "gedcom_id": individual.gedcom_id,
            "sex_code": individual.sex_code,
            "birth_date": _date_str(individual.birth_date),
            "birth_date_approx": individual.birth_date_approx,
            "birth_place": individual.birth_place,
            "death_date": _date_str(individual.death_date),
            "death_date_approx": individual.death_date_approx,
            "death_place": individual.death_place,
            "notes": individual.notes,
            **_attribution(individual, name_map),
        },
        "names": [
            {
                "id": n.id,
                "name_type": n.name_type,
                "given_name": n.given_name,
                "family_name": n.family_name,
                "prefix": n.prefix,
                "suffix": n.suffix,
                "name_order": n.name_order,
                **_attribution(n, name_map),
            }
            for n in individual.names
        ],
        "events": [
            {
                "id": e.id,
                "event_type_code": e.event_type_code,
                "event_date": _date_str(e.event_date),
                "event_date_approx": e.event_date_approx,
                "event_place": e.event_place,
                "description": e.description,
                **_attribution(e, name_map),
            }
            for e in events
        ],
        "media": [
            {
                "id": m.id,
                "file_path": m.file_path,
                "media_type_code": m.media_type_code,
                "media_date": _date_str(m.media_date),
                "media_date_approx": m.media_date_approx,
                "description": m.description,
                "is_default": bool(m.is_default) if m.is_default is not None else None,
                "age_on_photo": m.age_on_photo,
                **_attribution(m, name_map),
            }
            for m in media
        ],
        "families": [
            {
                "id": f.id,
                "gedcom_id": f.gedcom_id,
                "family_type": f.family_type,
                "marriage_date": _date_str(f.marriage_date),
                "marriage_date_approx": f.marriage_date_approx,
                "marriage_place": f.marriage_place,
                "divorce_date": _date_str(f.divorce_date),
                "divorce_date_approx": f.divorce_date_approx,
                "notes": f.notes,
                "role_in_family": (
                    "child" if any(link.family_id == f.id for link in child_links)
                    else next((link.role for link in member_links if link.family_id == f.id), None)
                ),
                **_attribution(f, name_map),
            }
            for f in families
        ],
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{INDIVIDUAL_DATA_EXPORT_FILENAME_PREFIX}-{session.owner_id}-individual-{individual_id}-{timestamp}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
