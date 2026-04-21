# Per-owner SQLite session management.
#
# Each owner has their own database under datasets/<owner>/data.sqlite.
# Engines are cached in a pool keyed by owner_id — created on first use,
# reused across requests.
#
from typing import Generator, Optional, Union
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine
from .models import Base
from .owner_info import OwnerInfo

# Engine pool: owner_id -> (Engine, sessionmaker)
_pool: dict[str, tuple[Engine, sessionmaker]] = {}

# Single source of truth for lookup tables.
# To add a new lookup table, add an entry here — get_engine, engine_from_url,
# and tests will pick it up automatically.
# Format: table_name -> dict of code -> description.
LOOKUP_TABLES: dict[str, dict[str, str]] = {
    "lookup_sexes": {
        "M": "Male", "F": "Female", "NB": "Non-binary", "U": "Unknown",
    },
    "lookup_event_types": {
        "BIRT": "Birth", "DEAT": "Death", "BURI": "Burial", "CREM": "Cremation",
        "BAPM": "Baptism", "BARM": "Bar Mitzvah", "BASM": "Bat Mitzvah",
        "BLES": "Blessing", "CHR": "Christening", "CHRA": "Adult Christening",
        "CONF": "Confirmation", "FCOM": "First Communion",
        "ORDN": "Ordination", "NATU": "Naturalization",
        "EMIG": "Emigration", "IMMI": "Immigration",
        "CENS": "Census", "PROB": "Probate", "WILL": "Will",
        "GRAD": "Graduation", "RETI": "Retirement",
        "OCCU": "Occupation", "EDUC": "Education", "RESI": "Residence",
        "ADOP": "Adoption", "EVEN": "Other Event",
        "MARR": "Marriage", "MARB": "Marriage Banns", "MARC": "Marriage Contract",
        "MARL": "Marriage License", "MARS": "Marriage Settlement",
        "DIV": "Divorce", "DIVF": "Divorce Filed", "ANUL": "Annulment",
        "ENGA": "Engagement",
        "STUD_START": "Study Start", "STUD_END": "Study End",
        "WORK_START": "Work/Job Start", "WORK_END": "Work/Job End",
        "RELOC": "Relocation To",
    },
    "lookup_media_types": {
        "photo": "Photograph", "audio": "Audio", "video": "Video",
    },
    "lookup_family_roles": {
        "husband": "Husband", "wife": "Wife", "partner": "Unmarried Partner",
    },
    "lookup_family_types": {
        "marriage": "Marriage", "civil_union": "Civil Union",
        "domestic_partnership": "Domestic Partnership",
        "common_law": "Common-law Marriage", "other": "Other",
    },
    "lookup_name_types": {
        "birth": "Birth", "aka": "Also Known As",
        "married": "Married", "maiden": "Maiden",
    },
    "lookup_date_approx_types": {
        "ABT": "About", "CAL": "Calculated", "EST": "Estimated",
        "BEF": "Before", "AFT": "After",
        "BET": "Between X And Y", "FROM": "From X To Y",
    },
}


def _seed_lookup_tables(eng: Engine) -> None:
    """Create and populate lookup tables from LOOKUP_TABLES (idempotent)."""
    with eng.connect() as conn:
        for table_name, rows in LOOKUP_TABLES.items():
            conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS {table_name} "
                f"(code TEXT PRIMARY KEY, description TEXT NOT NULL)"))
            for code, description in rows.items():
                conn.execute(text(
                    f"INSERT OR IGNORE INTO {table_name} (code, description) "
                    f"VALUES (:code, :desc)"),
                    {"code": code, "desc": description})
        conn.commit()


def get_engine(owner_id: str, owner_info: Optional[OwnerInfo] = None) -> Engine:
    """Return (creating if needed) the SQLAlchemy engine for an owner.

    Pass owner_info to use a custom base_dir (e.g. test temp dirs).
    When omitted, OwnerInfo is constructed from owner_id using the default datasets/ dir.
    """
    if owner_id not in _pool:
        if owner_info is None:
            owner_info = OwnerInfo(owner_id=owner_id)
        engine = create_engine(
            f"sqlite:///{owner_info.db_file}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        _seed_lookup_tables(engine)
        _pool[owner_id] = (engine, sessionmaker(autocommit=False, autoflush=False, bind=engine))
    return _pool[owner_id][0]


def get_owner_info(owner_id: str) -> OwnerInfo:
    """Return OwnerInfo for an owner (ensuring their engine is initialized)."""
    get_engine(owner_id)  # ensures dirs and db exist
    return OwnerInfo(owner_id=owner_id)


def get_db(owner_id: str) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for the given owner_id."""
    get_engine(owner_id)  # ensure initialized
    _, session_factory = _pool[owner_id]
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def reload_owner(owner_id: str) -> None:
    """Dispose and remove an owner's engine from the pool (forces re-init on next use).

    Call this after a GEDCOM import that replaces the owner's database.
    """
    if owner_id in _pool:
        engine, _ = _pool.pop(owner_id)
        engine.dispose()


def engine_from_url(url: str, create_tables: bool = True) -> Engine:
    """Create a standalone engine from a database URL (for import/export scripts)."""
    engine = create_engine(url, connect_args={"check_same_thread": False})
    if create_tables:
        Base.metadata.create_all(bind=engine)
        _seed_lookup_tables(engine)
    return engine


# ---------------------------------------------------------------------------
# Legacy shims — kept for callers that haven't been migrated yet.
# These will be removed once all endpoints use the dependency injection path.
# ---------------------------------------------------------------------------

def init_db_once(owner_info: Optional[Union[OwnerInfo, str]] = None) -> Engine:
    """Legacy: initialize (or return cached) engine for an owner."""
    if owner_info is None:
        owner_info_obj = OwnerInfo()
    elif isinstance(owner_info, str):
        owner_info_obj = OwnerInfo(owner_id=owner_info)
    else:
        owner_info_obj = owner_info  # preserves custom base_dir (e.g. test temp dirs)
    return get_engine(owner_info_obj.owner_id, owner_info_obj)


def reset_engine() -> None:
    """Legacy: dispose all engines in pool (used by import endpoint)."""
    for engine, _ in _pool.values():
        engine.dispose()
    _pool.clear()


def get_active_owner() -> Optional[OwnerInfo]:
    """Legacy: returns None — replaced by per-request owner resolution."""
    return None
