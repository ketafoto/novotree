from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import schemas
from .auth import EditorSession, get_tree_db, require_editor, require_owner
from .api_utils import fetch_display_names, enrich_created_by
from database.system_db import get_system_db
import database.models


router = APIRouter(prefix="/events", tags=["events"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_edit_permission(session: EditorSession, record_created_by: str | None) -> None:
    if session.is_contributor and record_created_by != session.editor_id:
        raise HTTPException(status_code=403, detail="Contributors can only edit their own records")


@router.post("", response_model=schemas.Event)
def create_event(
    event: schemas.EventCreate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    db_event = database.models.Event(
        individual_id=event.individual_id,
        family_id=event.family_id,
        event_type_code=event.event_type_code,
        event_date=event.event_date,
        event_date_approx=event.event_date_approx,
        event_place=event.event_place,
        description=event.description,
        created_by=session.editor_id,
        created_at=_now_iso(),
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    result = schemas.Event.model_validate(db_event)
    return result.model_copy(update={"created_by_display_name": session.display_name})


@router.get("", response_model=List[schemas.Event])
def read_events(
    skip: int = 0,
    limit: int = 100,
    individual_id: Optional[int] = None,
    family_id: Optional[int] = None,
    db: Session = Depends(get_tree_db),
    db_sys: Session = Depends(get_system_db),
):
    query = db.query(database.models.Event)
    if individual_id:
        query = query.filter(database.models.Event.individual_id == individual_id)
    if family_id:
        query = query.filter(database.models.Event.family_id == family_id)
    db_rows = query.offset(skip).limit(limit).all()
    name_map = fetch_display_names({e.created_by for e in db_rows if e.created_by}, db_sys)
    return [enrich_created_by(schemas.Event.model_validate(e), name_map) for e in db_rows]


@router.get("/{event_id}", response_model=schemas.Event)
def read_event(
    event_id: int,
    db: Session = Depends(get_tree_db),
    db_sys: Session = Depends(get_system_db),
):
    event = db.query(database.models.Event).filter(
        database.models.Event.id == event_id
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    name_map = fetch_display_names({event.created_by} if event.created_by else set(), db_sys)
    return enrich_created_by(schemas.Event.model_validate(event), name_map)


@router.put("/{event_id}", response_model=schemas.Event)
def update_event(
    event_id: int,
    event_update: schemas.EventUpdate,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    event = db.query(database.models.Event).filter(
        database.models.Event.id == event_id
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    _check_edit_permission(session, event.created_by)

    for key, value in event_update.model_dump(exclude_unset=True).items():
        if hasattr(event, key):
            setattr(event, key, value)

    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    session: EditorSession = Depends(require_editor),
    db: Session = Depends(get_tree_db),
):
    """Delete an event. Contributors may only delete their own records."""
    event = db.query(database.models.Event).filter(
        database.models.Event.id == event_id
    ).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    _check_edit_permission(session, event.created_by)
    db.delete(event)
    db.commit()
    return {"detail": "Event deleted"}
