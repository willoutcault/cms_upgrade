from app import create_app, db
from app.models import Brand, Campaign, Program, Placement, Status, Channel

app = create_app()
with app.app_context():
    db.create_all()
    # Brand
    b = Brand(name="DemoBrand", pharma="Acme Pharma", therapeutic_area="Immunology")
    db.session.add(b); db.session.flush()

    # Campaign
    c = Campaign(name="FY25 Launch - Demo", business_unit="HCM", status=Status.active, brand_id=b.id)
    db.session.add(c); db.session.flush()

    # Program
    p = Program(campaign_id=c.id, program_id=9100, name="Patient Consensus #9100", type="Patient Consensus", platform="dx")
    db.session.add(p); db.session.flush()

    # Placement
    pl = Placement(program_id=p.id, placement_id=123456, name="Email Banner A", channel=Channel.email, veeva_code="N12345", ad_server_id="DC-98765")
    db.session.add(pl)

    db.session.commit()
    print("Seeded demo data.")
