import io, os, csv, datetime, math
from collections import Counter, defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import select, text, or_
from ..extensions import db, refresh_network_cache
from .. import extensions as ext
from ..models import TargetList, TargetListEntry, Program, Campaign, Brand

targets_bp = Blueprint("targets", __name__, template_folder="../templates/targets")

# -----------------------------
# CSV/XLSX parsing (no pandas)
# -----------------------------
try:
    from openpyxl import load_workbook
except Exception:
    load_workbook = None

def _read_csv_dicts(file_bytes: bytes):
    f = io.StringIO(file_bytes.decode('utf-8', errors='ignore'))
    reader = csv.DictReader(f)
    return list(reader)

def _read_xlsx_dicts(file_bytes: bytes):
    if not load_workbook:
        raise RuntimeError("openpyxl not installed")
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    out = []
    for r in rows[1:] if len(rows) > 1 else []:
        rec = {}
        for i, v in enumerate(r):
            key = headers[i] if i < len(headers) else f"col{i+1}"
            rec[key] = "" if v is None else str(v)
        out.append(rec)
    return out

def _read_rows(file_storage):
    content = file_storage.read()
    file_storage.seek(0)
    name = (file_storage.filename or "").lower()
    if name.endswith(('.xlsx', '.xls')):
        return _read_xlsx_dicts(content)
    else:
        return _read_csv_dicts(content)

def _pick_npi_column(rows):
    if not rows:
        return None
    headers = list(rows[0].keys())
    lower = [h.lower().strip() for h in headers]
    candidates = ["npi", "npi_id", "npi number", "npi_number"]
    for cand in candidates:
        if cand in lower:
            return headers[lower.index(cand)]
    best = None; best_score = -1
    for h in headers:
        vals = [("".join([c for c in (row.get(h) or "") if c.isdigit()])) for row in rows[:200]]
        score = sum(1 for v in vals if len(v) == 10)
        if score > best_score:
            best_score = score; best = h
    return best or headers[0]

def _extract_clean_npi(raw: str):
    return "".join(ch for ch in str(raw or "").strip() if ch.isdigit())

def _extract_clean_npis(rows, npi_col):
    return [_extract_clean_npi(row.get(npi_col)) for row in rows if _extract_clean_npi(row.get(npi_col))]

# -----------------------------
# Program search helper
# -----------------------------
def _query_programs(q: str | None):
    stmt = select(Program).order_by(Program.created_at.desc())
    if q:
        like = f"%{q}%"
        # search across program fields + campaign + brand
        stmt = (
            select(Program)
            .join(Campaign, Program.campaign_id == Campaign.id)
            .join(Brand, isouter=True, onclause=Campaign.brand_id == Brand.id)
            .where(
                or_(
                    Program.name.ilike(like),
                    Program.platform.ilike(like),
                    Program.type.ilike(like),
                    Campaign.name.ilike(like),
                    Brand.name.ilike(like),
                    Program.program_id.cast(db.Integer).cast(db.String).ilike(like) if Program.program_id is not None else Program.name.ilike(like),
                )
            )
            .order_by(Program.created_at.desc())
        )
    return db.session.execute(stmt).scalars().all()

# -----------------------------
# Data summary (from JSON extras)
# -----------------------------
SUMMARY_CANDIDATES = [
    ("Specialty", 8),
    ("State", 8),
    ("City", 8),
    ("Tier", 5),
    ("Client", 5),
]
NUMERIC_CANDIDATES = ["ActivityScore", "Score", "Rank"]

def _summarize_entries(tid: int, limit_rows: int = 20000):
    rows = db.session.execute(
        select(TargetListEntry.extra, TargetListEntry.npi).where(TargetListEntry.target_list_id == tid).limit(limit_rows)
    ).all()
    facet_counts = {k: Counter() for k, _ in SUMMARY_CANDIDATES}
    numeric_values = defaultdict(list)

    for extra, npi in rows:
        if not extra or not isinstance(extra, dict):
            continue
        for key, topn in SUMMARY_CANDIDATES:
            if key in extra and extra[key]:
                facet_counts[key][str(extra[key])] += 1
        for nk in NUMERIC_CANDIDATES:
            if nk in extra:
                try:
                    numeric_values[nk].append(float(str(extra[nk]).strip()))
                except Exception:
                    pass

    facets = {}
    for key, topn in SUMMARY_CANDIDATES:
        if facet_counts[key]:
            facets[key] = facet_counts[key].most_common(topn)

    numerics = {}
    for nk, vals in numeric_values.items():
        if vals:
            vals_sorted = sorted(vals)
            n = len(vals_sorted)
            def pct(p): 
                i = max(0, min(n-1, int(round((p/100.0)*(n-1)))))
                return vals_sorted[i]
            numerics[nk] = {
                "count": n,
                "min": vals_sorted[0],
                "p50": pct(50),
                "p90": pct(90),
                "max": vals_sorted[-1],
            }

    # sample up to 25 entries for preview table
    sample = db.session.execute(
        select(TargetListEntry.npi, TargetListEntry.extra).where(TargetListEntry.target_list_id == tid).limit(25)
    ).all()

    return facets, numerics, sample

# -----------------------------
# Routes
# -----------------------------
@targets_bp.route("/target-lists", methods=["GET", "POST"])
def target_lists():
    # Ensure new columns exist on SQLite (MVP migration)
    try:
        ext.ensure_mvp_schema_sqlite()
    except Exception:
        pass

    if request.method == "POST":
        alias = request.form.get("alias") or None
        name = request.form.get("name", "").strip() or (alias or "Unnamed List")
        brand = request.form.get("brand") or None
        pharma = request.form.get("pharma") or None
        indication = request.form.get("indication") or None
        notes = request.form.get("notes") or None

        f = request.files.get("file")
        if not f or f.filename == "":
            flash("Upload a CSV/XLSX with NPI column.", "warning")
            return redirect(url_for("targets.target_lists"))
        try:
            rows = _read_rows(f)
            if not rows:
                raise RuntimeError("File appears empty.")
            npi_col = _pick_npi_column(rows)
            if not npi_col:
                raise RuntimeError("Could not identify NPI column.")

            filename = f.filename or None
            t = TargetList(name=name, alias=alias, brand=brand, pharma=pharma, indication=indication, notes=notes, filename=filename)
            db.session.add(t); db.session.flush()

            # Build NPI -> extra mapping (first occurrence wins)
            npi_to_extra = {}
            for r in rows:
                npi = _extract_clean_npi(r.get(npi_col))
                if not npi or npi in npi_to_extra:
                    continue
                extra = {k: v for k, v in r.items() if k != npi_col}
                # cap extra size to avoid huge payload per entry
                if len(extra) > 30:
                    # keep only first 30 keys deterministically
                    keep_keys = list(extra.keys())[:30]
                    extra = {k: extra[k] for k in keep_keys}
                npi_to_extra[npi] = extra

            unique_npis = list(npi_to_extra.keys())

            entries = [TargetListEntry(target_list_id=t.id, npi=n, extra=npi_to_extra.get(n)) for n in unique_npis]
            db.session.bulk_save_objects(entries)

            t.n_rows = int(len(rows))
            t.n_unique_npi = int(len(unique_npis))
            # coverage via live or cache based on strategy
            if (ext.network_cache_strategy or "live") in {"startup_snapshot", "manual"}:
                # cache path: ensure table exists, match locally
                ext.ensure_local_network_table()
                res = db.session.execute(text("""
                    SELECT COUNT(*) FROM (
                      SELECT npi FROM network_npis
                      WHERE npi IN (SELECT e.npi FROM target_list_entries e WHERE e.target_list_id = :tid)
                    ) sub
                """), {"tid": t.id}).scalar_one()
                t.n_matched_network = int(res or 0)
            else:
                # live path
                sql = f"""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT net.npi
                    FROM ({ext.ro_sql_network_npi}) AS net
                    WHERE net.npi IN (
                        SELECT e.npi FROM target_list_entries e WHERE e.target_list_id = :tid
                    )
                ) AS sub
                """
                with ext.ro_engine.connect() as conn:
                    try:
                        conn.exec_driver_sql("SET TRANSACTION READ ONLY;")
                    except Exception:
                        pass
                    res = conn.exec_driver_sql(sql, {"tid": t.id}).scalar()
                    t.n_matched_network = int(res or 0)

            db.session.commit()
            flash("Target list stored.", "success")
            return redirect(url_for("targets.target_lists"))
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to store target list: {e}", "danger")
            return redirect(url_for("targets.target_lists"))

    lists = db.session.execute(select(TargetList).order_by(TargetList.created_at.desc())).scalars().all()
    return render_template("targets/list.html", lists=lists)

@targets_bp.route("/target-lists/<int:tid>", methods=["GET", "POST"])
def target_list_detail(tid):
    # Ensure new columns exist on SQLite (MVP migration)
    try:
        ext.ensure_mvp_schema_sqlite()
    except Exception:
        pass

    t = db.session.get(TargetList, tid)
    if not t:
        flash("Target list not found.", "danger")
        return redirect(url_for("targets.target_lists"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "meta":
            t.alias = request.form.get("alias") or None
            t.name = request.form.get("name") or t.alias or t.name
            t.brand = request.form.get("brand") or None
            t.pharma = request.form.get("pharma") or None
            t.indication = request.form.get("indication") or None
            t.notes = request.form.get("notes") or None
            db.session.commit()
            flash("Details updated.", "success")
            return redirect(url_for("targets.target_list_detail", tid=tid))
        elif action == "map":
            program_ids = request.form.getlist("program_ids")
            programs = db.session.execute(select(Program).where(Program.id.in_([int(x) for x in program_ids]))).scalars().all() if program_ids else []
            t.programs = programs
            db.session.commit()
            flash("Mappings updated.", "success")
            return redirect(url_for("targets.target_list_detail", tid=tid))

    # Program search/filter
    q = request.args.get("q", "").strip()
    programs = _query_programs(q)

    # Recompute match using current strategy
    if (ext.network_cache_strategy or "live") in {"startup_snapshot", "manual"}:
        ext.ensure_local_network_table()
        matched = db.session.execute(text("""
            SELECT COUNT(*) FROM network_npis n
            WHERE n.npi IN (SELECT e.npi FROM target_list_entries e WHERE e.target_list_id = :tid)
        """), {"tid": t.id}).scalar_one()
    else:
        sql = f"""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT net.npi
            FROM ({ext.ro_sql_network_npi}) AS net
            WHERE net.npi IN (
                SELECT e.npi FROM target_list_entries e WHERE e.target_list_id = :tid
            )
        ) AS sub
        """
        with ext.ro_engine.connect() as conn:
            try:
                conn.exec_driver_sql("SET TRANSACTION READ ONLY;")
            except Exception:
                pass
            matched = conn.exec_driver_sql(sql, {"tid": t.id}).scalar()
    t.n_matched_network = int(matched or 0)
    db.session.commit()

    # Data summary
    facets, numerics, sample = _summarize_entries(t.id)

    return render_template("targets/detail.html", t=t, programs=programs, q=q, facets=facets, numerics=numerics, sample=sample)
