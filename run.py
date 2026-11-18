from flask import Flask
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


app=create_app()
from application.routes import *

if __name__=='__main__':
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run()
