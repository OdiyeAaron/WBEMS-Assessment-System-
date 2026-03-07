# In app/auth/routes.py

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse # <-- CRITICAL FIX: Use urllib.parse instead of werkzeug.urls
from app.auth import bp
from app.models import User, db
from app.auth.forms import LoginForm, RegistrationForm

DASHBOARD_URL = 'dashboard'

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(DASHBOARD_URL))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=True)
        
        next_page = request.args.get('next')
        # Use urlparse to check if the next page is internal
        if not next_page or urlparse(next_page).netloc != '':
            next_page = url_for(DASHBOARD_URL)
        return redirect(next_page)

    return render_template('login.html', title='Sign In', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    user_count = db.session.query(User).count()
    if user_count > 0 and (not current_user.is_authenticated or current_user.role != 'Admin'):
         flash('Only administrators can register new accounts.', 'warning')
         return redirect(url_for(DASHBOARD_URL))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role=form.role.data)
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'User {user.username} successfully registered. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', title='Register', form=form)


@bp.route('/logout')
@login_required 
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))