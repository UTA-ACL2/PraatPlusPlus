from flask import Blueprint, jsonify, request, session
import os
import json

lock_bp = Blueprint("lock_routes", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
LOCK_FILE = os.path.join(BASE_DIR, 'locks.json')  # Lock file path


# Initialize `session_id` (ensure each session is unique)
def ensure_session_id():
    if 'session_id' not in session:
        import uuid
        session['session_id'] = str(uuid.uuid4())


# read lock
def load_locks():
    if not os.path.exists(LOCK_FILE):
        return {}
    with open(LOCK_FILE, 'r') as f:
        return json.load(f)


# save lock
def save_locks(locks):
    with open(LOCK_FILE, 'w') as f:
        json.dump(locks, f)


# Locking logic
def lock_file(username, filename):
    ensure_session_id()
    folder = session.get("current_folder")
    locks = load_locks()
    user_locks = locks.get(username, {})
    lock_key = f"{folder}/{filename}"
    if lock_key in user_locks:
        if user_locks[lock_key] == session['session_id']:
            return True  # Already locked by self
        return False     # Locked by someone else
    user_locks[lock_key] = session['session_id']
    locks[username] = user_locks
    save_locks(locks)
    return True


# Unlocking logic
def unlock_file(username, filename):
    ensure_session_id()
    folder = session.get("current_folder")
    locks = load_locks()
    user_locks = locks.get(username, {})
    lock_key = f"{folder}/{filename}"
    if lock_key in user_locks and user_locks[lock_key] == session['session_id']:
        del user_locks[lock_key]
        locks[username] = user_locks
        save_locks(locks)
        return True
    return False


@lock_bp.route('/lock_file', methods=['POST'])
def lock_file_api():
    data = request.json
    username = data.get('username')
    filename = data.get('filename')
    success = lock_file(username, filename)
    return jsonify({'success': success, 'message': "Locked successfully" if success else "File is locked by another user"})


@lock_bp.route('/unlock_file', methods=['POST'])
def unlock_file_api():
    data = request.json
    username = data.get('username')
    filename = data.get('filename')
    success = unlock_file(username, filename)
    return jsonify({'success': success, 'message': "Unlocked" if success else "Unlock failed (not owner or not locked)"})

