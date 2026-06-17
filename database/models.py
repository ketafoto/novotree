# "models" stands for ORM models that reflect the format of the database tables.
# Models are python objects, where instance of object reflects the row in the table.
# The models are used by SQLAlchemy ORM to read and write data from/to the database.

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Date,
    Text,
    ForeignKey,
    PrimaryKeyConstraint,
)

from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# GEDCOM event codes that inherently reveal religion, and so are GDPR Art. 9
# special-category data regardless of any manual flag (a baptism record is a
# religion record). Source list: db.LOOKUP_TABLES["lookup_event_types"] (the
# religious-rite subset). Events of these types are excluded from share-link
# viewer payloads by default; see backend/api/tree.py and PRIVACY_DESIGN.md 3.7.
#
SENSITIVE_EVENT_CODES = frozenset({
    "BAPM", "BARM", "BASM", "BLES", "CHR", "CHRA", "CONF", "FCOM", "ORDN",
})


def event_is_sensitive(event) -> bool:
    """True if an Event row is special-category: an inherently-religious type
    (SENSITIVE_EVENT_CODES) OR the Owner manually flagged it via is_sensitive."""
    return bool(event.is_sensitive) or event.event_type_code in SENSITIVE_EVENT_CODES


Base = declarative_base()

class Individual(Base):
    __tablename__ = "main_individuals"

    id = Column(Integer, primary_key=True, index=True)
    gedcom_id = Column(String, unique=True, nullable=False, index=True)
    sex_code = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    birth_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    birth_place = Column(String, nullable=True)
    death_date = Column(Date, nullable=True)
    death_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    death_place = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # Special-category (GDPR Art. 9) flags, Owner-set. NULL/False = not sensitive.
    # is_sensitive hides the whole person from share-link viewers; notes_sensitive
    # hides only the free-text notes while the rest stays visible. See PRIVACY_DESIGN.md 3.7.
	#
    is_sensitive = Column(Boolean, nullable=True)
    notes_sensitive = Column(Boolean, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    # Relationships
    names = relationship("IndividualName", back_populates="individual", cascade="all, delete-orphan")
    families = relationship("FamilyMember", back_populates="individual", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="individual", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="individual", cascade="all, delete-orphan")

class IndividualName(Base):
    __tablename__ = "main_individual_names"

    id = Column(Integer, primary_key=True, index=True)
    individual_id = Column(Integer, ForeignKey("main_individuals.id"), nullable=False)
    name_type = Column(String, nullable=True)
    given_name = Column(String, nullable=True)
    family_name = Column(String, nullable=True)
    prefix = Column(String, nullable=True)
    suffix = Column(String, nullable=True)
    name_order = Column(Integer, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    # Relationships
    individual = relationship("Individual", back_populates="names")

class Family(Base):
    __tablename__ = "main_families"

    id = Column(Integer, primary_key=True, index=True)
    gedcom_id = Column(String, unique=True, nullable=False, index=True)
    marriage_date = Column(Date, nullable=True)
    marriage_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    marriage_place = Column(String, nullable=True)
    divorce_date = Column(Date, nullable=True)
    divorce_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    family_type = Column(String, nullable=False, default="marriage")
    notes = Column(Text, nullable=True)
    # Special-category (GDPR Art. 9) flag for the family's free-text notes. See Individual.notes_sensitive.
    notes_sensitive = Column(Boolean, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    # Relationships
    members = relationship("FamilyMember", back_populates="family", cascade="all, delete-orphan")
    children = relationship("FamilyChild", back_populates="family", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="family", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="family", cascade="all, delete-orphan")

class FamilyMember(Base):
    __tablename__ = "main_family_members"

    family_id = Column(Integer, ForeignKey("main_families.id"), primary_key=True, nullable=False)
    individual_id = Column(Integer, ForeignKey("main_individuals.id"), primary_key=True, nullable=False)
    role = Column(String, nullable=True)

    # Relationships
    family = relationship("Family", back_populates="members")
    individual = relationship("Individual", back_populates="families")

class FamilyChild(Base):
    __tablename__ = "main_family_children"

    family_id = Column(Integer, ForeignKey("main_families.id"), primary_key=True, nullable=False)
    child_id = Column(Integer, ForeignKey("main_individuals.id"), primary_key=True, nullable=False)

    # Relationships
    family = relationship("Family", back_populates="children")
    child = relationship("Individual")

class Event(Base):
    __tablename__ = "main_events"

    id = Column(Integer, primary_key=True, index=True)
    individual_id = Column(Integer, ForeignKey("main_individuals.id"), nullable=True)
    family_id = Column(Integer, ForeignKey("main_families.id"), nullable=True)
    event_type_code = Column(String, nullable=False)  # References lookup_event_types(code)
    event_date = Column(Date, nullable=True)
    event_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    event_place = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    # Manual special-category (GDPR Art. 9) flag. Independent of the inherently-religious
    # event types in SENSITIVE_EVENT_CODES; event_is_sensitive() ORs the two.
    is_sensitive = Column(Boolean, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    # Relationships
    individual = relationship("Individual", back_populates="events")
    family = relationship("Family", back_populates="events")

class Media(Base):
    __tablename__ = "main_media"

    id = Column(Integer, primary_key=True, index=True)
    individual_id = Column(Integer, ForeignKey("main_individuals.id"), nullable=True)
    family_id = Column(Integer, ForeignKey("main_families.id"), nullable=True)
    file_path = Column(String, nullable=True)
    media_type_code = Column(String, nullable=True)  # References lookup_media_types(code)
    media_date = Column(Date, nullable=True)
    media_date_approx = Column(String, nullable=True)  # Raw GEDCOM date string for non-exact dates, e.g. 'ABT 1970'
    description = Column(Text, nullable=True)
    is_default = Column(Integer, nullable=True, default=0)
    age_on_photo = Column(Integer, nullable=True)
    # Manual special-category (GDPR Art. 9) flag, default off. A flagged photo is
    # excluded from share-link viewers; so are all photos of an is_sensitive Individual.
    is_sensitive = Column(Boolean, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(String, nullable=True)

    # Relationships
    individual = relationship("Individual", back_populates="media")
    family = relationship("Family", back_populates="media")


class Header(Base):
    """GEDCOM Header/Submitter metadata (singleton table).

    Stores information from HEAD and SUBM records for round-trip fidelity.
    Only one record is allowed (id must always be 1).
    """
    __tablename__ = "meta_header"

    id = Column(Integer, primary_key=True)  # Always 1

    # Source system (SOUR)
    source_system_id = Column(String, nullable=True)
    source_system_name = Column(String, nullable=True)
    source_version = Column(String, nullable=True)
    source_corporation = Column(String, nullable=True)

    # File info
    file_name = Column(String, nullable=True)
    creation_date = Column(String, nullable=True)  # Raw GEDCOM date
    creation_time = Column(String, nullable=True)

    # GEDCOM version (GEDC)
    gedcom_version = Column(String, nullable=True, default="5.5.1")
    gedcom_form = Column(String, nullable=True, default="LINEAGE-LINKED")

    # Other header fields
    charset = Column(String, nullable=True, default="UTF-8")
    language = Column(String, nullable=True)
    copyright = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    # Submitter info (SUBM record)
    submitter_id = Column(String, nullable=True)
    submitter_name = Column(String, nullable=True)
    submitter_address = Column(String, nullable=True)
    submitter_city = Column(String, nullable=True)
    submitter_state = Column(String, nullable=True)
    submitter_postal = Column(String, nullable=True)
    submitter_country = Column(String, nullable=True)
    submitter_phone = Column(String, nullable=True)
    submitter_email = Column(String, nullable=True)
    submitter_fax = Column(String, nullable=True)
    submitter_www = Column(String, nullable=True)

    # Timestamps
    imported_at = Column(String, nullable=True)
    last_modified = Column(String, nullable=True)

class Source(Base):
    __tablename__ = "main_sources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=True)
    publication = Column(String, nullable=True)
    publish_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
