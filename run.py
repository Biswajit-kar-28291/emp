from flask import Flask
from sqlalchemy import inspect, text
from application.database import db
from application.models import ROLE_ADMIN, STATUS_ACTIVE, User
import os
app=None


def create_app(test_config=None):
    app=Flask(__name__)
    app.debug=True
    app.config['SQLALCHEMY_DATABASE_URI']=os.environ.get(
        'DATABASE_URL', 'sqlite:///emp.sqlite3'
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    app.app_context().push()
    return app


def create_default_admin():
    admin_email=os.environ.get('ADMIN_EMAIL', 'admin@emp.local').strip().lower()
    admin_password=os.environ.get('ADMIN_PASSWORD', 'admin123')
    if User.query.filter_by(role=ROLE_ADMIN).first() is None:
        db.session.add(User(
            email=admin_email,
            password=admin_password,
            role=ROLE_ADMIN,
            account_status=STATUS_ACTIVE,
        ))
        db.session.commit()


def update_existing_schema():
    """Add new nullable/defaulted fields without deleting existing local records."""
    inspector = inspect(db.engine)
    if "examiner_profiles" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("examiner_profiles")}
        if "contact_details" not in columns:
            db.session.execute(text("ALTER TABLE examiner_profiles ADD COLUMN contact_details VARCHAR(255)"))
        if "department" not in columns:
            db.session.execute(text("ALTER TABLE examiner_profiles ADD COLUMN department VARCHAR(255)"))
    if "evaluations" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("evaluations")}
        if "is_finalized" not in columns:
            db.session.execute(
                text("ALTER TABLE evaluations ADD COLUMN is_finalized BOOLEAN NOT NULL DEFAULT 0")
            )
    if "booking_history" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("booking_history")}
        for name, definition in (
            ("old_slot_id", "INTEGER REFERENCES examination_slots(id)"),
            ("new_slot_id", "INTEGER REFERENCES examination_slots(id)"),
            ("actor_id", "INTEGER REFERENCES users(id)"),
        ):
            if name not in columns:
                db.session.execute(text(f"ALTER TABLE booking_history ADD COLUMN {name} {definition}"))
    db.session.commit()


app=create_app()
from application.routes import *

if __name__=='__main__':
    with app.app_context():
        db.create_all()
        update_existing_schema()
        create_default_admin()
    app.run()
