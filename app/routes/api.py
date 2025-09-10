from flask import Blueprint, jsonify, request
from sqlalchemy import select, or_
from ..extensions import db
from ..models import Brand, Campaign, Program, Placement, Status, Channel

api_bp = Blueprint("api", __name__)

def serialize_campaign(c):
    return {
        "id": c.id,
        "external_id": c.external_id,
        "name": c.name,
        "business_unit": c.business_unit,
        "status": c.status.value,
        "start_date": str(c.start_date) if c.start_date else None,
        "end_date": str(c.end_date) if c.end_date else None,
        "brand_id": c.brand_id,
        "programs": [serialize_program(p) for p in c.programs],
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }

def serialize_program(p):
    return {
        "id": p.id,
        "program_id": p.program_id,
        "name": p.name,
        "type": p.type,
        "platform": p.platform,
        "placements": [serialize_placement(pl) for pl in p.placements],
    }

def serialize_placement(pl):
    return {
        "id": pl.id,
        "placement_id": pl.placement_id,
        "name": pl.name,
        "channel": pl.channel.value if pl.channel else None,
        "veeva_code": pl.veeva_code,
        "ad_server_id": pl.ad_server_id,
    }

@api_bp.get("/campaigns")
def api_list_campaigns():
    q = request.args.get("q", "").strip()
    stmt = select(Campaign).order_by(Campaign.created_at.desc())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Campaign.name.ilike(like), Campaign.external_id.ilike(like)))
    rows = db.session.execute(stmt).scalars().all()
    return jsonify([serialize_campaign(c) for c in rows])

@api_bp.get("/campaigns/<int:cid>")
def api_get_campaign(cid):
    c = db.session.get(Campaign, cid)
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify(serialize_campaign(c))
