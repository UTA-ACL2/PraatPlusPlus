import os
import json
from flask import Blueprint, request, jsonify
from app.utils.utils import get_user_folder_path

annotation_bp = Blueprint("annotation", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory


@annotation_bp.route("/save_annotation", methods=["POST"])
def save_annotation():
    """Receive the auto-saved JSON from the frontend and store it on the server"""
    try:
        data = request.get_json(force=True)  # More robust, compatible with `navigator.sendBeacon`
    except Exception as e:
        print("Failed to parse JSON:", e)
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    if not data or "username" not in data or "videoName" not in data or "annotations" not in data:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    username = data["username"]
    video_name = data["videoName"]
    annotation = data["annotations"]

    user_folder_path = get_user_folder_path()
    annotation_folder = os.path.join(user_folder_path, "annotation", video_name)
    os.makedirs(annotation_folder, exist_ok=True)  # Create directory

    json_path = os.path.join(annotation_folder, "annotations.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(annotation, f, indent=4)

    return jsonify({"success": True, "message": "Annotation saved successfully."})


@annotation_bp.route("/load_annotation", methods=["GET"])
def load_annotation():
    """Load the saved JSON annotation data"""
    username = request.args.get("username")
    video_name = request.args.get("videoName")

    if not username or not video_name:
        return jsonify({"success": False, "message": "Missing parameters"}), 400

    user_folder_path = get_user_folder_path()
    json_path = os.path.join(user_folder_path, "annotation", video_name, "annotations.json")

    if not os.path.exists(json_path):
        return jsonify({"success": False, "message": "No annotation found."})

    with open(json_path, "r", encoding="utf-8") as f:
        annotation_data = json.load(f)

    return jsonify({"success": True, "annotations": annotation_data})
