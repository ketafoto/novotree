"""
Lookup types API endpoints.

Provides endpoints to fetch predefined GEDCOM lookup values
for dropdowns in the frontend.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from .auth import get_viewer_tree_db

router = APIRouter(prefix="/types", tags=["Lookup Types"])


class LookupType(BaseModel):
    """A lookup type with code and description."""
    code: str
    description: str


@router.get("/sex", response_model=List[LookupType])
def get_sex_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all sex type codes for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_sexes ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/events", response_model=List[LookupType])
def get_event_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all event type codes for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_event_types ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/media", response_model=List[LookupType])
def get_media_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all media type codes for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_media_types ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/family-roles", response_model=List[LookupType])
def get_family_roles(db: Session = Depends(get_viewer_tree_db)):
    """Get all family member role codes for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_family_roles ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/family-types", response_model=List[LookupType])
def get_family_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all family type codes for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_family_types ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/name-types", response_model=List[LookupType])
def get_name_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all name types for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_name_types ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]


@router.get("/date-approx", response_model=List[LookupType])
def get_date_approx_types(db: Session = Depends(get_viewer_tree_db)):
    """Get all approximate date types for dropdowns."""
    rows = db.execute(text("SELECT code, description FROM lookup_date_approx_types ORDER BY code")).fetchall()
    return [LookupType(code=r[0], description=r[1]) for r in rows]
