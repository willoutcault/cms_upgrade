from __future__ import annotations

from datetime import datetime, date
from typing import Optional
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, Integer, ForeignKey, Date, DateTime, JSON, Table

from .extensions import db

# ---------------- Core Entities ----------------

class Brand(db.Model):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="brand", cascade="all, delete-orphan")


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brands.id"))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    brand: Mapped[Optional["Brand"]] = relationship(back_populates="campaigns")
    programs: Mapped[list["Program"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class Program(db.Model):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    program_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Optional external ID
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"))
    platform: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)   # e.g., Email, HCP Portal
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)       # e.g., Awareness, Conversion
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="programs")
    target_lists: Mapped[list["TargetList"]] = relationship(
        secondary=lambda: target_list_programs, back_populates="programs"
    )
    placements: Mapped[list["Placement"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )

# Association table between TargetList and Program
target_list_programs = Table(
    "target_list_programs",
    db.metadata,
    db.Column("target_list_id", db.Integer, db.ForeignKey("target_lists.id"), primary_key=True),
    db.Column("program_id", db.Integer, db.ForeignKey("programs.id"), primary_key=True),
)

# ---------------- Compatibility Enums & Models ----------------
# Many apps previously imported these from models. Provide safe defaults.

class Status(str, Enum):
    planned = "planned"
    active = "active"
    paused = "paused"
    completed = "completed"
    canceled = "canceled"

class Channel(str, Enum):
    email = "email"
    web = "web"
    portal = "portal"
    social = "social"
    sms = "sms"
    other = "other"


class Placement(db.Model):
    """Minimal placement model to keep existing imports/routes happy.
    Feel free to extend with additional fields your app uses.
    """
    __tablename__ = "placements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True, nullable=False)

    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # expected values ~ Channel enum
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)   # expected values ~ Status enum

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    program: Mapped["Program"] = relationship(back_populates="placements")


class TargetList(db.Model):
    __tablename__ = "target_lists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # New / optional metadata
    filename:   Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    alias:      Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand:      Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pharma:     Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    indication: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Optional existing fields likely present already
    client:     Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes:      Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Upload stats / coverage
    n_rows:            Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_unique_npi:      Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_matched_network: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    programs: Mapped[list["Program"]] = relationship(
        secondary=lambda: target_list_programs, back_populates="target_lists"
    )
    entries: Mapped[list["TargetListEntry"]] = relationship(
        back_populates="target_list", cascade="all, delete-orphan"
    )


class TargetListEntry(db.Model):
    __tablename__ = "target_list_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    target_list_id: Mapped[int] = mapped_column(ForeignKey("target_lists.id"), index=True, nullable=False)
    npi: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)   # compact JSON payload per NPI (first occurrence)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    target_list: Mapped["TargetList"] = relationship(back_populates="entries")
