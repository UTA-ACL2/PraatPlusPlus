import re
import shutil
from flask import Blueprint, request, session, redirect, url_for, flash, jsonify
import os
from app.config import URL_PREFIX
from app.utils.utils import get_user_folder_path

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
                for ext in ['.mp4', '.wav', 'mp3']:
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

    return redirect(URL_PREFIX + url_for('login.general_form'))


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
