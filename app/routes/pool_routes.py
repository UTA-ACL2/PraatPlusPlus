from flask import Blueprint, jsonify, request, Response, session
import time
import os
import re
import subprocess
import json
import shutil
from app.utils.utils import update_user_cache, get_username, get_user_folder_path

pool_bp = Blueprint("pool_routes", __name__)  # Create Blueprint


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
POOL_DIR = os.path.join(BASE_DIR, "static", "videos", "pool")


def get_video_duration(file_path):
    """Use `ffprobe` to get the video duration"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration", "-of", "json", file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        duration_data = json.loads(result.stdout)  # Parse the JSON output
        duration = float(duration_data["format"]["duration"])
        return round(duration, 2)  # Keep two decimal places
    except Exception as e:
        print(f"Error getting duration for {file_path}: {e}")
        return "Unknown"  # Return "Unknown" when an error occurs


@pool_bp.route('/<username>/files', methods=['GET'])
def get_user_files(username):
    """Get user's video/audio file list (with pagination + sorting + cache)"""
    username = username.lower()
    folder = get_user_folder_path()
    annotation_folder = os.path.join(folder, "annotation")
    cache_path = os.path.join(folder, "pool_metadata.json")

    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 10))
    sort_key = request.args.get("sort_key", "name")
    order = request.args.get("order", "asc").lower()

    if not os.path.exists(folder):
        return jsonify({"error": f"User folder '{username}' not found"}), 404

    # Try loading from cache first
    cache = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    allowed_extensions = {'.mp4': 'MP4', '.wav': 'WAV', '.mp3': 'MP3'}
    all_files = os.listdir(folder)
    media_files = [f for f in all_files if os.path.splitext(f)[1].lower() in allowed_extensions]
    files_info = []

    def is_annotated_data(data):
        """A file is considered annotated if ANY tier contains at least one interval."""
        if not isinstance(data, list):
            return False

        for tier in data:
            tier_data = tier.get("data", [])
            if isinstance(tier_data, list) and len(tier_data) > 0:
                return True

        return False

    for file_name in media_files:
        # Try reading from cache
        metadata = cache.get(file_name)

        ext = os.path.splitext(file_name)[1].lower()
        file_path = os.path.join(folder, file_name)
        file_stat = os.stat(file_path)
        annotation_path = os.path.join(annotation_folder, file_name.rsplit('.', 1)[0], "annotations.json")

        # If the cache does not exist, it means it is a new file → Recalculate metadata
        if not metadata:
            duration = get_video_duration(file_path)
            metadata = {
                "name": file_name,
                "date": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stat.st_mtime)),
                "type": allowed_extensions[ext],
                "size": round(file_stat.st_size / 1024 / 1024, 2),
                "duration": duration if duration != "Unknown" else 0,
            }

        # Update annotation status and lastAnnotationSaveTime every time
        is_annotated = False
        last_annotation_save_time = "----"
        if os.path.exists(annotation_path):
            try:
                with open(annotation_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # if isinstance(data, list) and len(data) > 0:
                    if is_annotated_data(data):
                        is_annotated = True
                mtime = os.path.getmtime(annotation_path)
                last_annotation_save_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            except Exception as e:
                print(f"[WARN] Failed to read {annotation_path}: {e}")

        metadata["status"] = "Annotated" if is_annotated else "Not Annotated"
        metadata["lastAnnotationSaveTime"] = last_annotation_save_time

        update_user_cache(username, file_name, metadata)
        files_info.append(metadata)

    # Sorting
    reverse = (order == "desc")

    def sort_value(item):
        if sort_key == "name":
            return item["name"].lower()
        elif sort_key == "type":
            return item["type"].lower()
        elif sort_key == "status":
            return 1 if item["status"] == "Annotated" else 0
        elif sort_key == "duration":
            return float(item["duration"])
        elif sort_key == "size":
            return float(item["size"])
        elif sort_key == "lastAnnotationSaveTime":
            if item["lastAnnotationSaveTime"] == "----":
                return 0
            try:
                return time.mktime(time.strptime(item["lastAnnotationSaveTime"], "%Y-%m-%d %H:%M:%S"))
            except:
                return 0
        else:
            return item["name"].lower()

    files_info.sort(key=sort_value, reverse=reverse)

    total_files = len(files_info)
    total_pages = max(1, (total_files + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_files = files_info[start:end]

    for f in paginated_files:
        f["size"] = f"{f['size']} MB"
        f["duration"] = f"{f['duration']} sec" if f["duration"] != 0 else "Unknown"

    return jsonify({
        "username": username,
        "files": paginated_files,
        "total_files": total_files,
        "total_pages": total_pages,
        "current_page": page
    })


@pool_bp.route('/delete_file', methods=['DELETE'])
def delete_user_file():
    """Delete user's file + corresponding annotation folder+ cache"""
    username = request.args.get("username")
    filename = request.args.get("filename")

    if not username or not filename:
        return jsonify(success=False, error="Missing username or filename"), 400

    user_folder_path = get_user_folder_path()
    file_path = os.path.join(user_folder_path, filename)
    annotation_folder = os.path.join(user_folder_path, "annotation", os.path.splitext(filename)[0])

    try:
        # Delete video/audio files
        if os.path.exists(file_path):
            os.remove(file_path)
        else:
            return jsonify(success=False, error="File not found")

        # Delete the corresponding annotation folder (if it exists)
        if os.path.isdir(annotation_folder):
            shutil.rmtree(annotation_folder)

        update_user_cache(username, filename, delete=True)

        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@pool_bp.route('/export_all_annotations', methods=['GET'])
def export_all_annotations():
    """Export all non-empty annotations for a user into a single JSON file."""
    username = get_username()
    if not username:
        return jsonify({"error": "Missing username"}), 400

    user_folder_path = get_user_folder_path()
    user_annotation_dir = os.path.join(user_folder_path, "annotation")
    if not os.path.exists(user_annotation_dir):
        return jsonify({"error": "No annotations found for this user"}), 404

    all_annotations = {}
    skipped_files = 0

    for file_name_rsplit in os.listdir(user_annotation_dir):
        annotation_file_path = os.path.join(user_annotation_dir, file_name_rsplit, "annotations.json")
        if not os.path.exists(annotation_file_path):
            continue

        try:
            with open(annotation_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    all_annotations[file_name_rsplit] = data
                else:
                    skipped_files += 1
        except Exception as e:
            print(f"[WARN] Failed to read {annotation_file_path}: {e}")
            skipped_files += 1
            continue

    if not all_annotations:
        return jsonify({"error": "No valid annotations found to export"}), 404

    json_data = json.dumps(all_annotations, indent=4, ensure_ascii=False)
    response = Response(json_data, mimetype="application/json")
    response.headers["Content-Disposition"] = f"attachment; filename={username}_all_annotations.json"

    print(f"[INFO] Exported {len(all_annotations)} valid annotations, skipped {skipped_files} empty files.")
    return response

@pool_bp.route('/pool/folders', methods=['GET'])
def get_user_folders():
    username = get_username()
    if not username:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    user_dir = os.path.join(POOL_DIR, username)

    if not os.path.exists(user_dir):
        return jsonify({"success": False, "error": f"User path '{username}' not found"}), 404

    folders = [
        name
        for name in os.listdir(user_dir)
        if os.path.isdir(os.path.join(user_dir, name))
    ]

    folders.sort(key=lambda x: x.lower())

    return jsonify({
        "success": True,
        "username": username,
        "folders": folders,
        "current_folder": session.get("current_folder")
    })


@pool_bp.route('/switch_folder', methods=['POST'])
def switch_folder():
    data = request.get_json()
    folder = data.get("folderNameNew")

    if not folder:
        return jsonify(success=False, error="Missing folder name"), 400

    session['current_folder'] = folder
    return jsonify(success=True)


def safe_folder_name(name: str) -> str:
    name = name.strip()
    if not name:
        return "untitled"

    name = re.sub(r"[^\w\u4e00-\u9fff]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")

    return name or "untitled"


@pool_bp.route('/create_folder', methods=['POST'])
def create_folder():
    """Create a new folder under user's directory"""
    data = request.get_json()
    username = get_username()
    if not username:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    folder_name = data.get("folderName")
    user_dir = os.path.join(POOL_DIR, username)

    if not username or not folder_name:
        return jsonify({"success": False, "error": "Missing username or folderName"}), 400

    # Clean folder name
    folder_name = safe_folder_name(folder_name)
    new_folder_path = os.path.join(user_dir, folder_name)

    try:
        if os.path.exists(new_folder_path):
            return jsonify({"success": False, "error": "Folder already exists"}), 409

        os.makedirs(new_folder_path, exist_ok=True)

        return jsonify({"success": True, "folder": folder_name})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
