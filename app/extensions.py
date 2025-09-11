from __future__ import annotations

import os
import datetime
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text, event

db = SQLAlchemy()

# -------- Read-only Network (Warehouse) --------
# These are initialized by init_readonly_engine_from_env() in app/__init__.py
ro_engine = None                 # SQLAlchemy Engine (read-only), or None
ro_sql_network_npi: Optional[str] = None  # The SQL snippet that returns a single column named 'npi'

# -------- Cache controls (for local app DB) --------
# See NETWORK_CACHE_STRATEGY in .env: 'live' | 'startup_snapshot' | 'manual'
network_cache_strategy: Optional[str] = None
network_cache_limit: Optional[int] = None
network_cache_last_at: Optional[datetime.datetime] = None
network_cache_count: int = 0


def init_readonly_engine_from_env() -> None:
    """Initialize the optional read-only engine and cache strategy from env.

    Env vars:
      - NETWORK_DATABASE_URL  e.g. postgresql+psycopg://readonly:pass@host:5432/db
      - NETWORK_NPI_SQL       must return ONE column named 'npi' (text)
      - NETWORK_CACHE_STRATEGY: live | startup_snapshot | manual
      - NETWORK_CACHE_LIMIT: optional int cap when snapshotting
    """
    global ro_engine, ro_sql_network_npi, network_cache_strategy, network_cache_limit

    url = (os.getenv("NETWORK_DATABASE_URL") or "").strip()
    sql = (os.getenv("NETWORK_NPI_SQL") or "").strip()

    # cache strategy
    strategy = (os.getenv("NETWORK_CACHE_STRATEGY", "live") or "live").strip().lower()
    network_cache_strategy = strategy if strategy in {"live", "startup_snapshot", "manual"} else "live"

    # cache limit
    try:
        network_cache_limit = int((os.getenv("NETWORK_CACHE_LIMIT") or "0").strip() or 0) or None
    except Exception:
        network_cache_limit = None

    ro_sql_network_npi = sql or None
    if not url:
        ro_engine = None
    else:
        ro_engine = create_engine(url, pool_pre_ping=True, future=True)

        # Force session to READ ONLY where supported (e.g., Postgres)
        @event.listens_for(ro_engine, "connect")
        def _set_ro(dbapi_connection, connection_record):
            try:
                with dbapi_connection.cursor() as cur:
                    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;")
                    cur.execute("SET default_transaction_read_only = on;")
            except Exception:
                # Non-Postgres backends may not support these; ignore.
                pass

    # If configured to snapshot at startup, try once (non-fatal on failure)
    if network_cache_strategy == "startup_snapshot" and ro_engine and ro_sql_network_npi:
        try:
            refresh_network_cache()
        except Exception:
            # allow app to boot; user can refresh manually from /network
            pass


def ensure_local_network_table() -> None:
    """Create the local cache table for network NPIs if it doesn't exist."""
    with db.engine.begin() as conn:
        conn.exec_driver_sql(
            """            CREATE TABLE IF NOT EXISTS network_npis (
                npi TEXT PRIMARY KEY
            )
            """
        )
        try:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_network_npi ON network_npis(npi)")
        except Exception:
            pass


def refresh_network_cache() -> int:
    """Fetch NPIs from the read-only warehouse SQL and load them into the local cache.

    Returns: number of rows inserted.
    Raises: RuntimeError if RO source is not configured.
    """
    global network_cache_last_at, network_cache_count

    if not ro_engine or not ro_sql_network_npi:
        raise RuntimeError("Read-only source not configured (NETWORK_DATABASE_URL/NETWORK_NPI_SQL)." )

    ensure_local_network_table()

    select_sql = f"SELECT npi FROM ({ro_sql_network_npi}) AS net"
    rows_inserted = 0

    with ro_engine.connect() as rconn:
        try:
            rconn.exec_driver_sql("SET TRANSACTION READ ONLY;")
        except Exception:
            pass

        result = rconn.execution_options(stream_results=True).exec_driver_sql(select_sql)
        batch = []
        batch_size = 5000
        limit = network_cache_limit or float("inf" )

        with db.engine.begin() as lconn:
            # Truncate before refill
            lconn.exec_driver_sql("DELETE FROM network_npis")
            for row in result:
                n = str(row[0]) if row and row[0] is not None else None
                if not n:
                    continue
                batch.append({"npi": n})
                if len(batch) >= batch_size:
                    lconn.exec_driver_sql(
                        "INSERT INTO network_npis (npi) VALUES (:npi) ON CONFLICT(npi) DO NOTHING",
                        batch,
                    )
                    rows_inserted += len(batch)
                    batch.clear()
                    if rows_inserted >= limit:
                        break
            if batch:
                lconn.exec_driver_sql(
                    "INSERT INTO network_npis (npi) VALUES (:npi) ON CONFLICT(npi) DO NOTHING",
                    batch,
                )
                rows_inserted += len(batch)

    network_cache_last_at = datetime.datetime.utcnow()
    network_cache_count = rows_inserted
    return rows_inserted


def ensure_mvp_schema_sqlite() -> None:
    """Best-effort SQLite-only migration to add new optional columns for TargetList.

    Adds columns if missing:
      - brand TEXT
      - pharma TEXT
      - indication TEXT
      - filename TEXT (if you didn't already have it)
    """
    try:
        backend = db.engine.url.get_backend_name()
    except Exception:
        return
    if backend != "sqlite":
        return

    with db.engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info('target_lists')").fetchall()
        cols = {r[1] for r in rows}
        stmts = []
        if "brand" not in cols:
            stmts.append("ALTER TABLE target_lists ADD COLUMN brand TEXT")
        if "pharma" not in cols:
            stmts.append("ALTER TABLE target_lists ADD COLUMN pharma TEXT")
        if "indication" not in cols:
            stmts.append("ALTER TABLE target_lists ADD COLUMN indication TEXT")
        if "filename" not in cols:
            stmts.append("ALTER TABLE target_lists ADD COLUMN filename TEXT")
        for sql in stmts:
            conn.exec_driver_sql(sql)
