from flask import Blueprint, jsonify, request, session
import os
import json
import time

lock_bp = Blueprint("lock_routes", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
LOCK_FILE = os.path.join(BASE_DIR, 'locks.json')  # Lock file path
LOCK_TIMEOUT_SECONDS = 120


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

def cleanup_expired_locks(locks):
    now = time.time()
    changed = False

    for username in list(locks.keys()):
        user_locks = locks.get(username, {})

        for lock_key in list(user_locks.keys()):
            lock_info = user_locks[lock_key]

            if isinstance(lock_info, str):
                del user_locks[lock_key]
                changed = True
                continue

            expires_at = lock_info.get("expires_at", 0)
            if now > expires_at:
                del user_locks[lock_key]
                changed = True

        if user_locks:
            locks[username] = user_locks
        else:
            del locks[username]
            changed = True

    if changed:
        save_locks(locks)

    return locks

def touch_lock(username, filename):
    ensure_session_id()
    folder = session.get("current_folder")
    locks = load_locks()
    locks = cleanup_expired_locks(locks)

    user_locks = locks.get(username, {})
    lock_key = f"{folder}/{filename}"

    if lock_key not in user_locks:
        return False, "Lock not found"

    lock_info = user_locks[lock_key]
    if lock_info.get("session_id") != session['session_id']:
        return False, "Not lock owner"

    lock_info["expires_at"] = time.time() + LOCK_TIMEOUT_SECONDS
    user_locks[lock_key] = lock_info
    locks[username] = user_locks
    save_locks(locks)
    return True, "Lock refreshed"

# Locking logic
def lock_file(username, filename):
    ensure_session_id()
    folder = session.get("current_folder")
    locks = load_locks()
    locks = cleanup_expired_locks(locks)

    user_locks = locks.get(username, {})
    lock_key = f"{folder}/{filename}"
    now = time.time()

    if lock_key in user_locks:
        lock_info = user_locks[lock_key]

        if lock_info.get("session_id") == session['session_id']:
            lock_info["expires_at"] = now + LOCK_TIMEOUT_SECONDS
            user_locks[lock_key] = lock_info
            locks[username] = user_locks
            save_locks(locks)
            return True

        return False

    user_locks[lock_key] = {
        "session_id": session['session_id'],
        "expires_at": now + LOCK_TIMEOUT_SECONDS
    }
    locks[username] = user_locks
    save_locks(locks)
    return True


# Unlocking logic
def unlock_file(username, filename):
    ensure_session_id()
    folder = session.get("current_folder")
    locks = load_locks()
    locks = cleanup_expired_locks(locks)

    user_locks = locks.get(username, {})
    lock_key = f"{folder}/{filename}"

    if lock_key in user_locks:
        lock_info = user_locks[lock_key]

        if lock_info.get("session_id") == session['session_id']:
            del user_locks[lock_key]
            locks[username] = user_locks
            save_locks(locks)
            return True

        return False

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

@lock_bp.route('/touch_lock', methods=['POST'])
def touch_lock_api():
    data = request.json
    username = data.get('username')
    filename = data.get('filename')
    success, message = touch_lock(username, filename)
    return jsonify({
        'success': success,
        'message': message
    }), (200 if success else 404)