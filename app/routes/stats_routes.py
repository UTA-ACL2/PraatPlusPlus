from flask import Blueprint, render_template, session
import os, json
from app.utils.utils import get_user_path

stats_bp = Blueprint("stats", __name__)

STATUS_KEYS = ["Not Started", "Ongoing", "Finished"]

def safe_load_json(path, default):

    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

@stats_bp.route("/statistics", methods=["GET"])
def statistics_page():
    username = session.get("acting_username") or session.get("username")
    if not username:
        return render_template("login.html")

    user_dir = get_user_path()
    if not os.path.isdir(user_dir):
        return render_template("statistics.html", stats={"username": username, "folders": [], "categories_by_folder": []}, segment="statistics")

    folders = sorted(
        [d for d in os.listdir(user_dir) if os.path.isdir(os.path.join(user_dir, d))],
        key=lambda x: x.lower()
    )

    folder_stats = []
    categories_by_folder = []

    for folder in folders:
        folder_path = os.path.join(user_dir, folder)
        cache_path = os.path.join(folder_path, "pool_metadata.json")
        cat_path = os.path.join(folder_path, "custom_categories.json")
        cache = safe_load_json(cache_path, {})
        status_counts = {k: 0 for k in STATUS_KEYS}
        total = 0

        if isinstance(cache, dict):
            for meta in cache.values():
                total += 1
                st = meta.get("status", "Not Started")
                if st not in status_counts:
                    st = "Not Started"
                status_counts[st] += 1

        folder_stats.append({
            "folder": folder,
            "total": total,
            "status_counts": status_counts,
        })

        cats = safe_load_json(cat_path, [])
        if not isinstance(cats, list):
            cats = []
        categories_by_folder.append({
            "folder": folder,
            "categories": cats
        })

    stats = {
        "username": username,
        "folders": folder_stats,
        "categories_by_folder": categories_by_folder
    }

    return render_template("statistics.html", stats=stats)