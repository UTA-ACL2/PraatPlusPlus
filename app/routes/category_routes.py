from flask import Blueprint, jsonify, request
import os
import json
from app.utils.utils import get_username, get_user_folder_path

category_bp = Blueprint("custom_categories", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory


@category_bp.route("/save_custom_category", methods=["POST"])
def save_custom_category():
    """Save new category"""
    data = request.json
    username = data["username"]
    category = data["category"]
    options = data["options"]

    user_folder_path = get_user_folder_path()
    custom_path = os.path.join(user_folder_path, "custom_categories.json")

    # Read existing category information
    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            categories = json.load(f)
    else:
        categories = []

    # Add new Category
    if not any(cat["category"] == category for cat in categories):
        new_category = {"category": category, "options": options}
        categories.append(new_category)

    # Save to JSON.
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(categories, f, indent=4)

    return jsonify({"success": True, "message": "Category saved!"})


@category_bp.route("/load_custom_categories", methods=["GET"])
def load_custom_categories():
    """Load user saved Categories"""
    user_folder_path = get_user_folder_path()
    custom_path = os.path.join(user_folder_path, "custom_categories.json")

    if os.path.exists(custom_path):
        with open(custom_path, "r", encoding="utf-8") as f:
            categories = json.load(f)
    else:
        categories = []

    return jsonify({"success": True, "categories": categories})


@category_bp.route("/delete_custom_category", methods=["POST"])
def delete_custom_category():
    """Delete the specified category"""
    data = request.json
    username = get_username()
    category_to_delete = data.get("category")

    if not username or not category_to_delete:
        return jsonify({"status": "error", "message": "Missing username or category"}), 400

    user_folder_path = get_user_folder_path()
    custom_path = os.path.join(user_folder_path, "custom_categories.json")

    # Check if the JSON exists
    if not os.path.exists(custom_path):
        return jsonify({"status": "error", "message": "custom_categories.json not found"}), 404

    # Read json
    with open(custom_path, "r", encoding="utf-8") as f:
        categories = json.load(f)

    # Delete the corresponding category.
    new_categories = [c for c in categories if c.get("category") != category_to_delete]

    # Overwrite and write.
    with open(custom_path, "w", encoding="utf-8") as f:
        json.dump(new_categories, f, indent=4, ensure_ascii=False)

    return jsonify({"status": "success"})

