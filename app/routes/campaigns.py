from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from sqlalchemy import select, or_
from datetime import date
from ..extensions import db
from ..models import Brand, Campaign, Program, Placement, Status, Channel

campaigns_bp = Blueprint("campaigns", __name__, template_folder="../templates/campaigns")

def _parse_date(val: str | None):
    if not val:
        return None
    val = val.strip()
    if not val:
        return None
    try:
        # HTML <input type="date"> posts YYYY-MM-DD
        return date.fromisoformat(val)
    except Exception:
        return None

# -------------
# HTML VIEWS
# -------------
@campaigns_bp.route("/campaigns")
def list_campaigns():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Campaign.name.ilike(like), Campaign.external_id.ilike(like)))
    if status:
        try:
            st = Status(status)
            stmt = stmt.where(Campaign.status == st)
        except Exception:
            pass
    campaigns = db.session.execute(stmt).scalars().all()
    return render_template("campaigns/list.html", campaigns=campaigns, q=q, status=status, Status=Status)

@campaigns_bp.route("/campaigns/new", methods=["GET", "POST"])
def create_campaign():
    if request.method == "POST":
        name = request.form["name"].strip()
        external_id = request.form.get("external_id") or None
        business_unit = request.form.get("business_unit") or None
        status_val = request.form.get("status") or "planned"
        start_date = _parse_date(request.form.get("start_date"))
        end_date = _parse_date(request.form.get("end_date"))
        brand_id = request.form.get("brand_id") or None
        notes = request.form.get("notes") or None

        c = Campaign(
            name=name,
            external_id=external_id,
            business_unit=business_unit,
            status=Status(status_val),
            start_date=start_date,
            end_date=end_date,
            brand_id=int(brand_id) if brand_id else None,
            notes=notes,
        )
        db.session.add(c)
        db.session.commit()
        flash("Campaign created.", "success")
        return redirect(url_for("campaigns.list_campaigns"))

    brands = db.session.execute(select(Brand).order_by(Brand.name)).scalars().all()
    return render_template("campaigns/create.html", brands=brands, Status=Status)

@campaigns_bp.route("/campaigns/<int:cid>")
def view_campaign(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        flash("Campaign not found.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    brands = db.session.execute(select(Brand).order_by(Brand.name)).scalars().all()
    return render_template("campaigns/detail.html", c=c, brands=brands, Status=Status, Channel=Channel)

@campaigns_bp.route("/campaigns/<int:cid>/edit", methods=["POST"])
def edit_campaign(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        flash("Campaign not found.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    c.name = request.form["name"].strip()
    c.external_id = request.form.get("external_id") or None
    c.business_unit = request.form.get("business_unit") or None
    c.status = Status(request.form.get("status") or "planned")
    c.start_date = _parse_date(request.form.get("start_date"))
    c.end_date = _parse_date(request.form.get("end_date"))
    c.brand_id = int(request.form["brand_id"]) if request.form.get("brand_id") else None
    c.notes = request.form.get("notes") or None
    db.session.commit()
    flash("Campaign updated.", "success")
    return redirect(url_for("campaigns.view_campaign", cid=cid))

@campaigns_bp.route("/campaigns/<int:cid>/delete", methods=["POST"])
def delete_campaign(cid):
    c = db.session.get(Campaign, cid)
    if c:
        db.session.delete(c)
        db.session.commit()
        flash("Campaign deleted.", "warning")
    return redirect(url_for("campaigns.list_campaigns"))

# --- Brand simple CRUD (minimal) ---
@campaigns_bp.route("/brands/new", methods=["POST"])
def create_brand():
    name = request.form["name"].strip()
    pharma = request.form.get("pharma") or None
    ta = request.form.get("therapeutic_area") or None
    b = Brand(name=name, pharma=pharma, therapeutic_area=ta)
    db.session.add(b)
    db.session.commit()
    flash("Brand created.", "success")
    return redirect(url_for("campaigns.list_campaigns"))

# --- Program and Placement creation from Campaign detail ---
@campaigns_bp.route("/campaigns/<int:cid>/programs/new", methods=["POST"])
def create_program(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        flash("Campaign not found.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    p = Program(
        campaign_id=cid,
        program_id=int(request.form["program_id"]) if request.form.get("program_id") else None,
        name=request.form["name"].strip(),
        type=request.form.get("type") or None,
        platform=request.form.get("platform") or None,
    )
    db.session.add(p)
    db.session.commit()
    flash("Program added.", "success")
    return redirect(url_for("campaigns.view_campaign", cid=cid))

@campaigns_bp.route("/programs/<int:pid>/placements/new", methods=["POST"])
def create_placement(pid):
    p = db.session.get(Program, pid)
    if not p:
        flash("Program not found.", "danger")
        return redirect(url_for("campaigns.list_campaigns"))
    # Note: channel is optional and must map to enum name if provided
    channel_val = request.form.get("channel")
    channel_parsed = getattr(type(p).placements.property.mapper.class_.channel.type.enum_class, channel_val) if channel_val else None  # type: ignore
    pl = Placement(
        program_id=pid,
        placement_id=int(request.form["placement_id"]) if request.form.get("placement_id") else None,
        name=request.form.get("name") or None,
        channel=channel_parsed,
        veeva_code=request.form.get("veeva_code") or None,
        ad_server_id=request.form.get("ad_server_id") or None,
    )
    db.session.add(pl)
    db.session.commit()
    flash("Placement added.", "success")
    return redirect(url_for("campaigns.view_campaign", cid=p.campaign_id))
