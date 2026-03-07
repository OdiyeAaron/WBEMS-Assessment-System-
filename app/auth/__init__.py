# In app/auth/__init__.py

from flask import Blueprint

# The name 'auth' is used when calling url_for (e.g., url_for('auth.login'))
bp = Blueprint('auth', __name__)

from app.auth import routes