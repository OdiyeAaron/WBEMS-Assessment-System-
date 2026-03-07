import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager  # <-- 1. NEW IMPORT
from os.path import dirname, join, realpath 

db = SQLAlchemy()
login = LoginManager() # <-- 2. INSTANTIATE LOGIN MANAGER GLOBALLY

def create_app():
    # Use realpath and join to explicitly define the templates folder location
    app = Flask(__name__,
                template_folder=join(dirname(realpath(__file__)), 'templates'), 
                static_folder='static')
    
    # === CONFIGURATION ===
    app.config['DEBUG'] = True 
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///studentv1.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # === FLASK-LOGIN SETUP ===
    login.init_app(app)  # <-- 3. ATTACH LoginManager TO THE APP
    login.login_view = 'auth.login' # Set the endpoint for the login page

    from .models import User
    
    @login.user_loader
    def load_user(id):
        # 4. REQUIRED function to reload the user object from the user ID stored in the session
        return User.query.get(int(id))

    # === BLUEPRINT REGISTRATION ===
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth') # <-- 5. REGISTER THE AUTH BLUEPRINT

    with app.app_context():
        # import modules that register routes and models
        # Your main routes are registered here and rely on the setup above
        from . import routes, models, commands # noqa
        db.create_all()

    return app