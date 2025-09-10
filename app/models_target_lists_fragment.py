from sqlalchemy import JSON, UniqueConstraint, Table, Column

# --- Target List Models ---

class TargetList(db.Model):
    __tablename__ = "target_lists"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    n_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_unique_npi: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    n_matched_network: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    entries: Mapped[list["TargetListEntry"]] = relationship(back_populates="target_list", cascade="all, delete-orphan")
    programs: Mapped[list["Program"]] = relationship("Program", secondary="target_list_programs", backref="target_lists")

class TargetListEntry(db.Model):
    __tablename__ = "target_list_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_list_id: Mapped[int] = mapped_column(ForeignKey("target_lists.id", ondelete="CASCADE"), index=True, nullable=False)
    npi: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # store original row columns if desired

    target_list: Mapped["TargetList"] = relationship(back_populates="entries")

    __table_args__ = (UniqueConstraint("target_list_id", "npi", name="uq_targetlist_npi"),)

# Association table: TargetList <-> Program
from sqlalchemy import MetaData
target_list_programs = db.Table(
    "target_list_programs",
    db.metadata,
    db.Column("target_list_id", db.Integer, db.ForeignKey("target_lists.id", ondelete="CASCADE"), primary_key=True),
    db.Column("program_id", db.Integer, db.ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True),
)
