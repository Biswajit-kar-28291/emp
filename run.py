from flask import Flask
from application.database import db
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


app=create_app()
from application.routes import *

if __name__=='__main__':
    with app.app_context():
        db.create_all()
    app.run()
