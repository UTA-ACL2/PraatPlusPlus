import os
import shutil
from flask import Blueprint, request, jsonify, render_template, url_for, session
from app.config import IS_SERVER, URL_PREFIX
from app.utils.utils import execute_command
import parselmouth
from parselmouth.praat import call
import numpy as np
from app.utils.utils import get_user_folder_path

general_bp = Blueprint('general', __name__)

# Configure path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
SCRIPTS_FOLDER = os.path.join(BASE_DIR, "static", "scripts")
if IS_SERVER:
    PRAAT_LOCATION = "/home/peter/praat_barren"  # Server path
else:
    PRAAT_LOCATION = "D:/praat.exe"  # Local Windows Path


# Utility function.
def save_file(uploaded_file, save_path):
    uploaded_file.save(save_path)


def create_directory_if_not_exists(path):
    os.makedirs(path, exist_ok=True)


def file_exists(*file_paths):
    return all(os.path.exists(p) for p in file_paths)

def extract_pitch_intensity(audio_path, output_path):
    snd = parselmouth.Sound(audio_path)
    pitch = call(snd, "To Pitch", 0.0, 75, 600)
    intensity = call(snd, "To Intensity", 100.0, 0.0, "yes")

    start_time = max(pitch.xmin, intensity.xmin)
    end_time = min(pitch.xmax, intensity.xmax)
    times = np.arange(start_time, end_time, 0.01)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("time\tpitch\tintensity\n")
        for t in times:
            p = call(pitch, "Get value at time", t, "Hertz", "Linear")
            i = call(intensity, "Get value at time", t, "Cubic")
            p_str = "--undefined--" if np.isnan(p) or p <= 0 else f"{p:.2f}"
            i_str = "--undefined--" if np.isnan(i) or i <= 0 else f"{i:.2f}"
            f.write(f"{t:.3f}\t{p_str}\t{i_str}\n")


@general_bp.route('/general', methods=['GET', 'POST'])
def general():
    try:
        if request.method == 'GET':
            return render_template('general_form.html')

        folder_name = session.get("current_folder")
        audio_file = request.files.get('audioFile')
        username = request.form.get("username")

        if not audio_file:
            return jsonify({"error": "No audio provided"}), 400

        audio_filename = audio_file.filename
        audio_basename = os.path.splitext(audio_filename)[0]
        print(f"audio_basename:{audio_basename}")

        # Final save directory
        user_folder_path = get_user_folder_path()
        target_dir = os.path.join(user_folder_path, "annotation", audio_basename, "")
        create_directory_if_not_exists(target_dir)

        # Required file path
        audio_file_path_mp4 = os.path.join(target_dir, f"{audio_basename}.mp4")
        audio_file_path_wav = os.path.join(target_dir, f"{audio_basename}.wav")
        graph_file_path = os.path.join(target_dir, f"{audio_basename}.graph")

        # If all three files exist, load them directly
        if file_exists(audio_file_path_mp4, audio_file_path_wav, graph_file_path):
            return jsonify({
                "redirect": URL_PREFIX + url_for("general.viewer", username=username, fileName=audio_basename, folderName=folder_name)
            })

        # Otherwise reprocess
        save_file(audio_file, audio_file_path_mp4)

        # Convert format
        ffmpeg_command = ["ffmpeg", "-i", audio_file_path_mp4, audio_file_path_wav]
        # ffmpeg_command = ["ffmpeg", "-y", "-i", audio_file_path_mp4, audio_file_path_wav]
        try:
            execute_command(ffmpeg_command, timeout=300)
        except Exception as e:
            print(f"ffmpeg failed")
            shutil.rmtree(target_dir, ignore_errors=True)
            return jsonify({"error": f"ffmpeg failed: {str(e)}"}), 500

        try:
            extract_pitch_intensity(audio_file_path_wav, graph_file_path)
        except Exception as e:
            print(f"Pitch/Intensity extraction failed: {e}")
            shutil.rmtree(target_dir, ignore_errors=True)
            return jsonify({"error": f"Pitch/Intensity extraction failed: {str(e)}"}), 500

        # Extract Pitch and Intensity
        # extract_command = [
        #     PRAAT_LOCATION, "--run", "--no-pref-files",
        #     os.path.join(SCRIPTS_FOLDER, "extractPitchIntensity.praat"),
        #     target_dir,
        #     audio_basename
        # ]
        # try:
        #     execute_command(extract_command, timeout=300)
        # except Exception as e:
        #     print(f"extractPitchIntensity.praat failed")
        #     shutil.rmtree(target_dir, ignore_errors=True)
        #     return jsonify({"error": f"extractPitchIntensity failed: {str(e)}"}), 500

        # pitch_intensity_command = [
        #     PRAAT_LOCATION, "--run", "--no-pref-files",
        #     os.path.join(SCRIPTS_FOLDER, "pitchIntensityScript.praat"),
        #     target_dir,
        #     audio_basename
        # ]
        # try:
        #     execute_command(pitch_intensity_command, timeout=300)
        # except Exception as e:
        #     print(f"pitchIntensityScript.praat failed")
        #     shutil.rmtree(target_dir, ignore_errors=True)
        #     return jsonify({"error": f"pitchIntensityScript failed: {str(e)}"}), 500

        return jsonify({
            "redirect": URL_PREFIX + url_for("general.viewer", username=username, fileName=audio_basename, folderName=folder_name)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@general_bp.route("/viewer")
def viewer():
    username = request.args.get("username")
    file_name = request.args.get("fileName")
    folder_name = request.args.get("folderName")
    base = f"{URL_PREFIX}/static/videos/pool/{username}/{folder_name}/annotation/{file_name}/{file_name}"
    return render_template(
        "viewer.html",
        audioFile=f"{base}.wav",
        videoFile=f"{base}.mp4",
        graphData=f"{base}.graph",
        fileName=file_name,
        userName=username
    )