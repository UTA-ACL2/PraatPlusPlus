import subprocess
from typing import List
import os
import json
from flask import session
from app.config import POOL_DIR


def execute_command(command: List[str], timeout: int = 300) -> str:
    process = None  # Define in advance to avoid errors when no value is assigned
    print("Executing command:", " ".join(command))

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate(timeout=timeout)
        stdout = stdout.strip() if stdout else ""
        stderr = stderr.strip() if stderr else ""

        if process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, command, output=stdout, stderr=stderr
            )

        return stdout

    except subprocess.TimeoutExpired:
        if process:
            process.kill()
            _, _ = process.communicate()
        raise TimeoutError(f"Command timed out after {timeout} seconds.")

    except Exception as e:
        raise RuntimeError(f"Failed to execute command: {' '.join(command)}\n{str(e)}")

def update_user_cache(username, filename, metadata=None, delete=False):
    """Maintain a unified pool_metadata.json"""
    user_folder_path = get_user_folder_path()
    cache_path = os.path.join(user_folder_path, "pool_metadata.json")

    if not os.path.exists(cache_path):
        cache = {}
    else:
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    if delete:
        cache.pop(filename, None)
    elif metadata:
        cache[filename] = metadata

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def get_username():
    """
    Get the effective username (acting user if set, otherwise real user).
    Note: Must be called within a valid Flask request context.
    """
    return session.get("acting_username") or session.get("username")

def get_user_path():
    """
    Get the user path.
    Note: This function must be called within a Flask request context.
    """
    username = session.get("acting_username") or session.get("username")
    user_dir = os.path.join(POOL_DIR, username)

    return user_dir

def get_user_folder_path():
    """
    Get the folder path currently selected by the user.
    Note: This function must be called within a Flask request context.
    """
    username = session.get("acting_username") or session.get("username")
    folder_name = session.get("current_folder")
    user_dir = os.path.join(POOL_DIR, username)
    # If empty or None → auto select first folder
    if not folder_name:
        folders = [
            f for f in os.listdir(user_dir)
            if os.path.isdir(os.path.join(user_dir, f))
        ]
        if folders:
            folders.sort(key=lambda x: x.lower())
            folder_name = folders[0]
            session["current_folder"] = folder_name

    folder_dir = os.path.join(user_dir, folder_name)

    return folder_dir
