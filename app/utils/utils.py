import subprocess
from typing import List
import os
import json

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
POOL_DIR = os.path.join(BASE_DIR, "static", "videos", "pool")

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
    cache_path = os.path.join(POOL_DIR, username, "pool_metadata.json")

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