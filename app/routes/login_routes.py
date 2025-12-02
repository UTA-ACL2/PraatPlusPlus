from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from app.config import URL_PREFIX

login_bp = Blueprint('login', __name__)

VALID_ACCOUNTS = ["peter", "kenny", "theron", "tuan", "wonjun", "hridayesh", "birds", "cats", "corvids", "guest", "lindsay", "rayyan", "eleanor", "abhipsa"]
SUPER_USERS = ["peter", "kenny", "theron"]
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
            default_folder = "default_task"
            default_user_folder_path = os.path.join(user_dir, default_folder)
            os.makedirs(default_user_folder_path, exist_ok=True)
            session['username'] = username
            session['current_folder'] = default_folder
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
    session.clear()  # Clear the session
    return redirect(URL_PREFIX + url_for('login.login'))  # Redirect to the login page after logout


@login_bp.route('/general_form')
def general_form():
    # Ensure that only logged-in users can access
    if 'username' not in session:
        return redirect(URL_PREFIX + url_for('login.login'))  # Redirect unauthenticated users to `/login`

    username = session.get('acting_username', session['username'])
    user_dir = os.path.join(BASE_DIR, "static", "videos", "pool", username)
    # Ensure folder is initialized
    folders = [
        f for f in os.listdir(user_dir)
        if os.path.isdir(os.path.join(user_dir, f))
    ]
    folders.sort(key=lambda x: x.lower())
    folder = session.get('current_folder')
    if not folder or folder not in folders:
        session['current_folder'] = folders[0]
        print(f"Initialized folder '{session['current_folder']}' for user '{username}' (previous folder invalid or upon login).")
    else:
        print(f"Using existing folder '{folder}' for user '{username}'")

    return render_template('general_form.html', username=session['username'], acting_username=session.get('acting_username', session['username']), VALID_ACCOUNTS = VALID_ACCOUNTS, SUPER_USERS = SUPER_USERS)

@login_bp.route('/switch_user', methods=['POST'])
def switch_user():
    if 'username' not in session:
        return jsonify(error="Not logged in"), 403

    if session['username'] not in SUPER_USERS:
        return jsonify(error="Permission denied"), 403

    data = request.get_json()
    selected = data.get("selectedUser")

    if selected not in VALID_ACCOUNTS:
        return jsonify(error="Invalid user"), 400

    user_dir = os.path.join(BASE_DIR, "static", "videos", "pool", selected)
    if not os.path.exists(user_dir):
        return jsonify(error=f'Cannot switch to "{selected}". The user has never logged in.'), 400

    session['acting_username'] = selected
    # Set the first sorted folder when the user switches
    folders = [
        f for f in os.listdir(user_dir)
        if os.path.isdir(os.path.join(user_dir, f))
    ]
    folders.sort(key=lambda x: x.lower())
    session['current_folder'] = folders[0]
    print(f"Switch to user '{selected}', switch to folder: '{session['current_folder']}'")
    return jsonify(success=True)