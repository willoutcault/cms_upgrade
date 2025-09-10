from app import create_app, db
from app.models import Brand, Campaign, Program, Placement

app = create_app()

if __name__ == "__main__":
    # Ensure tables exist (simple MVP; you can replace with Alembic later)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
