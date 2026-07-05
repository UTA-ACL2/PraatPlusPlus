import re
import shutil
from flask import Blueprint, request, session, redirect, url_for, flash, jsonify
import os
from app.config import URL_PREFIX
from app.utils.utils import get_user_folder_path

import json
import uuid
from textgrid import TextGrid, IntervalTier, PointTier
upload_bp = Blueprint('upload', __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "videos", "pool")  # Store the uploaded video
ALLOWED_EXTENSIONS = {'mp4', 'wav', 'mp3'}  # Allowed file formats


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    # Replace illegal characters with `_`
    safe_name = re.sub(r'[^\w]', '_', name)
    # Merge consecutive `_` into a single `_`
    safe_name = re.sub(r'_+', '_', safe_name)
    # Remove the leading and trailing `_`
    safe_name = safe_name.strip('_')
    return safe_name + ext


@upload_bp.route('/upload', methods=['POST'])
def upload_files():
    if 'username' not in session:
        flash("You must be logged in to upload files.", "error")
        return redirect(URL_PREFIX + url_for('login.login'))

    user_folder_path = get_user_folder_path()
    annotation_folder = os.path.join(user_folder_path, "annotation")
    os.makedirs(annotation_folder, exist_ok=True)  # Ensure the directory exists

    files = request.files.getlist("audioFile")  # Get multiple files
    uploaded_files = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = safe_filename(file.filename)
            basename = os.path.splitext(filename)[0]

            # If the frontend sends the `override` flag as true, clear the corresponding folder in `annotation`
            override_key = f"override_{basename}"
            override = request.form.get(override_key, "false") == "true"

            video_annotation_dir = os.path.join(annotation_folder, basename)

            if override and os.path.exists(video_annotation_dir):
                shutil.rmtree(video_annotation_dir, ignore_errors=True)
                # Delete `.mp4` and `.wav` files with the same prefix name
                for ext in ['.mp4', '.wav', '.mp3']:
                    file_path = os.path.join(user_folder_path, f"{basename}{ext}")
                    if os.path.exists(file_path):
                        os.remove(file_path)

            os.makedirs(video_annotation_dir, exist_ok=True)
            save_path = os.path.join(user_folder_path, filename)
            file.save(save_path)
            uploaded_files.append(filename)

    if uploaded_files:
        flash(f"Uploaded: {', '.join(uploaded_files)}", "success")
    else:
        flash("No valid files uploaded.", "error")

    return redirect(URL_PREFIX + url_for('login.file_pool'))


@upload_bp.route('/check_file_exists', methods=['GET'])
def check_file_exists():
    username = session.get('acting_username', session['username'])
    video_name = request.args.get("videoName")  # Without file extension.
    # Check if a file with the same prefix already exists in the user's directory
    user_folder = get_user_folder_path()
    video_file_path = os.path.join(user_folder, f"{video_name}.mp4")
    audio_file_path = os.path.join(user_folder, f"{video_name}.wav")
    audio_file_path2 = os.path.join(user_folder, f"{video_name}.mp3")
    # exists = os.path.exists(video_file_path)
    exists = os.path.exists(video_file_path) or os.path.exists(audio_file_path) or os.path.exists(audio_file_path2)

    return jsonify({"exists": exists})


# TODO: Handle TextGrid tier names that are not mapped to existing categories.
# TextGrid files do not contain a separate category field, so annotations may fail
# to load if the tier name does not already exist in the current category list.

ALLOWED_EXTENSIONS = {'mp4', 'wav', 'mp3'}
TEXTGRID_EXTENSIONS = {'textgrid'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_textgrid_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in TEXTGRID_EXTENSIONS


def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r'[^\w]', '_', name)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    return safe_name + ext


def safe_basename(filename):
    name, _ = os.path.splitext(filename)
    safe_name = re.sub(r'[^\w]', '_', name)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    return safe_name


def load_old_tier_meta(old_json_path):
    """
    Read old annotations.json and preserve metadata that TextGrid cannot store:
    - category
    - finished
    """
    tier_meta = {}

    if not os.path.exists(old_json_path):
        return tier_meta

    try:
        with open(old_json_path, "r", encoding="utf-8") as f:
            old_annotations = json.load(f)

        if isinstance(old_annotations, list):
            for tier in old_annotations:
                if not isinstance(tier, dict):
                    continue
                tier_type = tier.get("type")
                tier_name = tier.get("name")
                if not tier_type or not tier_name:
                    continue

                tier_meta[(tier_type, tier_name)] = {
                    "category": tier.get("category", "default"),
                    "finished": tier.get("finished", False)
                }
    except Exception:
        pass

    return tier_meta


def convert_textgrid_to_json_schema(textgrid_path, old_json_path=None):
    """
    Convert TextGrid -> your frontend annotations.json schema
    """
    tg = TextGrid.fromFile(textgrid_path)

    old_meta = load_old_tier_meta(old_json_path) if old_json_path else {}
    annotations = []

    for tier in tg:
        # Interval tier
        if isinstance(tier, IntervalTier):
            interval_data = []

            for interval in tier:
                xmin = float(interval.minTime)
                xmax = float(interval.maxTime)
                text = interval.mark or ""

                # Skip empty intervals by default
                # because your frontend stores actual created regions,
                # not full blank segmentation.
                if xmin >= xmax:
                    continue
                if text.strip() == "":
                    continue

                interval_data.append({
                    "xmin": xmin,
                    "xmax": xmax,
                    "text": text,
                    "confidence": "1"   # TextGrid doesn't store this in your export
                })

            interval_data.sort(key=lambda x: x["xmin"])

            meta = old_meta.get(
                ("IntervalTier", tier.name),
                {"category": tier.name or "default", "finished": False}
            )

            annotations.append({
                "type": "IntervalTier",
                "category": meta["category"],
                "name": tier.name,
                "finished": meta["finished"],
                "data": interval_data
            })

        # Point tier
        elif isinstance(tier, PointTier):
            point_data = []

            for point in tier:
                number = float(point.time)
                mark = point.mark or ""

                point_data.append({
                    "number": number,
                    "mark": mark
                })

            point_data.sort(key=lambda x: x["number"])

            annotations.append({
                "type": "TextTier",
                "name": tier.name,
                "data": point_data
            })

    return annotations


@upload_bp.route('/upload_textgrid', methods=['POST'])
def upload_textgrid():
    if 'username' not in session:
        return jsonify({
            "success": False,
            "message": "You must be logged in to import TextGrid."
        }), 401

    files = request.files.getlist("textgridFile")
    if not files:
        return jsonify({
            "success": False,
            "message": "No TextGrid file uploaded."
        }), 400

    user_folder_path = get_user_folder_path()
    annotation_root = os.path.join(user_folder_path, "annotation")
    os.makedirs(annotation_root, exist_ok=True)

    imported = []
    failed = []

    for tg_file in files:
        if not tg_file or tg_file.filename == "":
            failed.append({
                "file": "",
                "reason": "Empty file."
            })
            continue

        if not allowed_textgrid_file(tg_file.filename):
            failed.append({
                "file": tg_file.filename,
                "reason": "Only .TextGrid files are allowed."
            })
            continue

        # Use the same sanitization rule as media upload
        basename = safe_basename(tg_file.filename)

        # Match folder: annotation/<basename>/
        target_annotation_dir = os.path.join(annotation_root, basename)
        if not os.path.isdir(target_annotation_dir):
            failed.append({
                "file": tg_file.filename,
                "reason": f"Matching annotation folder not found: annotation/{basename}"
            })
            continue

        target_json_path = os.path.join(target_annotation_dir, "annotations.json")
        backup_json_path = target_json_path + ".bak"

        # Save uploaded TextGrid to a temporary file inside the target folder
        temp_textgrid_path = os.path.join(
            target_annotation_dir,
            f"__import_{uuid.uuid4().hex}.TextGrid"
        )

        try:
            tg_file.save(temp_textgrid_path)

            old_json_path = target_json_path if os.path.exists(target_json_path) else None

            new_annotation_data = convert_textgrid_to_json_schema(
                temp_textgrid_path,
                old_json_path=old_json_path
            )

            # backup old json if exists
            if os.path.exists(target_json_path):
                shutil.copy2(target_json_path, backup_json_path)

            with open(target_json_path, "w", encoding="utf-8") as f:
                json.dump(new_annotation_data, f, ensure_ascii=False, indent=4)

            imported.append({
                "file": tg_file.filename,
                "matched_folder": basename,
                "saved_json": "annotations.json",
                "backup": os.path.basename(backup_json_path) if os.path.exists(backup_json_path) else None
            })

        except Exception as e:
            failed.append({
                "file": tg_file.filename,
                "reason": str(e)
            })

        finally:
            if os.path.exists(temp_textgrid_path):
                os.remove(temp_textgrid_path)

    # Frontend usually only checks res.ok, so return 200 when at least one succeeds
    if imported:
        return jsonify({
            "success": True,
            "message": "TextGrid import finished.",
            "imported": imported,
            "failed": failed
        }), 200

    return jsonify({
        "success": False,
        "message": "No TextGrid file was imported.",
        "failed": failed
    }), 400