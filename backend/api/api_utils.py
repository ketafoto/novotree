from sqlalchemy.orm import Session
from sqlalchemy import inspect
import database.models
from database.system_models import AuthEditor


def generate_gedcom_id(db: Session, model) -> str:
    """
    Generate a unique GEDCOM ID for the given table/model.
    Assumes model has 'gedcom_id' string column with format: Letter + digits.

    Args:
        db: SQLAlchemy Session object
        model: SQLAlchemy model class to generate ID for (e.g., Individual)

    Returns:
        New unique gedcom_id string (e.g., 'I00001')
    """
    max_id = 0
    # Reflect column presence for safety
    mapper = inspect(model)
    if 'gedcom_id' not in mapper.columns:
        raise ValueError(f'Model {model} does not have a gedcom_id column')

    items = db.query(model).filter(model.gedcom_id != None).all()

    for item in items:
        gedcom_id = item.gedcom_id
        if gedcom_id and len(gedcom_id) > 1 and gedcom_id[1:].isdigit():
            if gedcom_id[0].isalpha():
                num = int(gedcom_id[1:])
                if num > max_id:
                    max_id = num

    return f"{max_id + 1:05d}"


def fetch_display_names(editor_ids: set, db_sys: Session) -> dict:
    """Batch-fetch editor display names from the system DB."""
    if not editor_ids:
        return {}
    rows = db_sys.query(AuthEditor.editor_id, AuthEditor.display_name).filter(
        AuthEditor.editor_id.in_(editor_ids)
    ).all()
    return {r.editor_id: r.display_name for r in rows}


def enrich_created_by(record, name_map: dict):
    """Return record with created_by_display_name populated from name_map."""
    if record.created_by and record.created_by in name_map:
        return record.model_copy(update={"created_by_display_name": name_map[record.created_by]})
    return record
