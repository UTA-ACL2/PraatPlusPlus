from flask import Blueprint, request, session, redirect, url_for, render_template
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from app.config import URL_PREFIX

login_bp = Blueprint('login', __name__)

VALID_ACCOUNTS = ["peter", "kenny", "theron", "essam", "tuan", "hridayesh", "birds", "cats", "corvids", "guest", "pranjal"]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
USER_FILE = os.path.join(BASE_DIR, 'users.json')  # User password file path


def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, 'r') as f:
        return json.load(f)


def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)


@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username").strip().lower()
        password = request.form.get("password").strip()

        if username not in VALID_ACCOUNTS:
            return render_template('login.html', error="Invalid username")

        users = load_users()

        if username not in users:
            #  First login → Save password
            users[username] = generate_password_hash(password)
            save_users(users)
            user_dir = os.path.join(BASE_DIR, "static", "videos", "pool", username)
            os.makedirs(user_dir, exist_ok=True)
            session['username'] = username
            return render_template('general_form.html', username=session['username'], message=f"First login. Password set successfully. Please remember it!")

            #  Future logins → Verify password
        if check_password_hash(users[username], password):
            session['username'] = username
            return redirect(URL_PREFIX + url_for('login.general_form'))
        else:
            return render_template('login.html', error="Incorrect password")

    return render_template('login.html')


# Log out
@login_bp.route('/logout')
def logout():
    session.pop('username', None)  # Clear the session
    return redirect(URL_PREFIX + url_for('login.login'))  # Redirect to the login page after logout


@login_bp.route('/general_form')
def general_form():
    # Ensure that only logged-in users can access
    if 'username' not in session:
        return redirect(URL_PREFIX + url_for('login.login'))  # Redirect unauthenticated users to `/login`

    return render_template('general_form.html', username=session['username'])
