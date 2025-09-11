from __future__ import annotations

from datetime import datetime, date
from typing import Optional
from enum import Enum as PyEnum  # <-- Python Enum base

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    Integer,
    ForeignKey,
    Date,
    DateTime,
    JSON,
    UniqueConstraint,
    Enum as SAEnum,  # <-- SQLAlchemy Enum column type
)

from .extensions import db

# ---------------- Core Entities ----------------

class Brand(db.Model):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    pharma: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    therapeutic_area: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )


class Status(str, PyEnum):
    planned = "planned"
    active = "active"
    paused = "paused"
    completed = "completed"
    canceled = "canceled"


class Channel(str, PyEnum):
    email = "email"
    app = "app"
    cmd = "cmd"
    dx = "dx"


class Campaign(db.Model):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=True)
    business_unit: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brands.id"))
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    objective: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # ✅ Enum-typed campaign status
    status: Mapped[Status] = mapped_column(SAEnum(Status), nullable=False, default=Status.planned)

    brand: Mapped[Optional["Brand"]] = relationship(back_populates="campaigns")
    programs: Mapped[list["Program"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class Program(db.Model):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    program_id: Mapped[int] = mapped_column(Integer, nullable=False) 
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"))
    platform: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  
    type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)     
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="programs")

    # ✅ Use back_populates (no backref) to avoid name collision
    target_lists: Mapped[list["TargetList"]] = relationship(
        secondary=lambda: target_list_programs,
        back_populates="programs",
    )

    placements: Mapped[list["Placement"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class Placement(db.Model):
    """Minimal placement model to keep existing imports/routes happy."""
    __tablename__ = "placements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placement_id: Mapped[int] = mapped_column(Integer, nullable=False) 
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id"), index=True, nullable=False)

    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    veeva_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ad_server_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ✅ Enum-typed fields
    channel: Mapped[Channel | None] = mapped_column(SAEnum(Channel), nullable=True)
    status:  Mapped[Status  | None] = mapped_column(SAEnum(Status),  nullable=True)

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    program: Mapped["Program"] = relationship(back_populates="placements")


# --- Target List Models ---

class TargetList(db.Model):
    __tablename__ = "target_lists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(255), nullable=False)
    pharma: Mapped[str] = mapped_column(String(255), nullable=False)
    indication: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    n_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_unique_npi: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_matched_network: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    entries: Mapped[list["TargetListEntry"]] = relationship(
        back_populates="target_list", cascade="all, delete-orphan"
    )

    # ✅ Mirror Program.target_lists with back_populates (no backref)
    programs: Mapped[list["Program"]] = relationship(
        "Program",
        secondary=lambda: target_list_programs,
        back_populates="target_lists",
    )


class TargetListEntry(db.Model):
    __tablename__ = "target_list_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    target_list_id: Mapped[int] = mapped_column(
        ForeignKey("target_lists.id", ondelete="CASCADE"), index=True, nullable=False
    )
    npi: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # original row columns if desired

    target_list: Mapped["TargetList"] = relationship(back_populates="entries")

    __table_args__ = (UniqueConstraint("target_list_id", "npi", name="uq_targetlist_npi"),)


# --- Association table: TargetList <-> Program ---

target_list_programs = db.Table(
    "target_list_programs",
    db.metadata,
    db.Column(
        "target_list_id",
        db.Integer,
        db.ForeignKey("target_lists.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "program_id",
        db.Integer,
        db.ForeignKey("programs.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
