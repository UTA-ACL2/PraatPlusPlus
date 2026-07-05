import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.utils.utils import get_user_folder_path, get_user_path
from flask import Blueprint, request, jsonify
import numpy as np
import librosa
import torch
# from panns_inference import SoundEventDetection, labels as PANNS_LABELS
from app.ai.panns.panns_inference import SoundEventDetection, labels as PANNS_LABELS

preannotate_bp = Blueprint("preannotate", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # Get the 'app/' directory
PANNS_DIR = Path(BASE_DIR) / "ai" / "panns"
CHECKPOINT_PATH = PANNS_DIR / "Cnn14_DecisionLevelMax.pth"
ANNOTATION_SUBDIR = "annotation"
# PANNs settings
PANNS_SAMPLE_RATE = 32000
PANNS_HOP_SIZE = 320  # 0.01s per frame if sr=32000
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

ALLOWED_LABELS = ["Speech", "Dog", "Bark", "Music", "Silence"]


# ====== PANNs model (loaded once) ======
_sed_model: Optional[SoundEventDetection] = None
_label_to_idx: Optional[Dict[str, int]] = None


def get_sed_model() -> SoundEventDetection:
    global _sed_model, _label_to_idx
    if _sed_model is None:
        _sed_model = SoundEventDetection(checkpoint_path=str(CHECKPOINT_PATH), device=DEVICE)
        _label_to_idx = {lab: i for i, lab in enumerate(PANNS_LABELS)}
    return _sed_model


def label_to_index(label: str) -> int:
    if _label_to_idx is None:
        get_sed_model()
    assert _label_to_idx is not None
    if label not in _label_to_idx:
        raise ValueError(f'Label "{label}" not found in PANNs label list.')
    return _label_to_idx[label]


def run_ffmpeg_extract_wav(media_path: Path, out_wav: Path) -> None:
    """
    Extract mono wav @ 32000Hz for PANNs.
    """
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(media_path),
        "-ac", "1",
        "-ar", str(PANNS_SAMPLE_RATE),
        "-vn",
        str(out_wav),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-1000:]}")

def scores_to_segments(
    scores: np.ndarray,
    threshold: float,
    min_duration_sec: float,
    label: str,
    score_mode: str = "max",
) -> List[Dict[str, float]]:
    """
    Convert framewise scores into merged segments with min_duration filtering.
    Returns list of {start, end, score}.
    """
    segments: List[Dict[str, float]] = []
    in_seg = False
    start_frame = 0

    def frame_to_time(i: int) -> float:
        return (i * PANNS_HOP_SIZE) / PANNS_SAMPLE_RATE

    for i, s in enumerate(scores):
        if s >= threshold:
            if not in_seg:
                start_frame = i
                in_seg = True
        else:
            if in_seg:
                end_frame = i
                start_t = frame_to_time(start_frame)
                end_t = frame_to_time(end_frame)
                if end_t - start_t >= min_duration_sec:
                    chunk = scores[start_frame:end_frame]
                    seg_score = float(chunk.max() if score_mode == "max" else chunk.mean())
                    segments.append({"start": start_t, "end": end_t, "score": seg_score})
                in_seg = False

    if in_seg:
        end_frame = len(scores)
        start_t = frame_to_time(start_frame)
        end_t = frame_to_time(end_frame)
        if end_t - start_t >= min_duration_sec:
            chunk = scores[start_frame:end_frame]
            seg_score = float(chunk.max() if score_mode == "max" else chunk.mean())
            segments.append({"start": start_t, "end": end_t, "score": seg_score})

    return segments


def panns_preannotate(audio_wav: Path, event_label: str, threshold: float, min_duration_sec: float) -> List[Dict[str, float]]:
    sed = get_sed_model()
    idx = label_to_index(event_label)

    y, _ = librosa.load(str(audio_wav), sr=PANNS_SAMPLE_RATE, mono=True)
    audio = y[None, :]  # [1, samples]

    framewise = sed.inference(audio)[0]  # [T, C]
    if hasattr(framewise, "detach"):
        framewise = framewise.detach().cpu().numpy()
    framewise = np.asarray(framewise)

    scores = framewise[:, idx]
    return scores_to_segments(scores, threshold, min_duration_sec, label=event_label, score_mode="max")


def load_annotations_json(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("annotations.json must be a LIST of tiers in your current format.")
    return data


def save_annotations_json(path: Path, tiers: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(tiers, f, ensure_ascii=False, indent=2)


def overwrite_target_tier(
    tiers: List[Dict[str, Any]],
    target_tier_name: str,
    event_label: str,
    segments: List[Dict[str, float]],
) -> int:
    """
    Find tier by tier["name"] == target_tier_name and overwrite its data.
    Returns number of written segments.
    """
    target = None
    for t in tiers:
        if t.get("name") == target_tier_name:
            target = t
            break
    if target is None:
        raise ValueError(f'Target tier "{target_tier_name}" not found in annotations.json.')

    # Force interval tier style output
    if target.get("type") != "IntervalTier":
        raise ValueError("Pre-annotation currently supports IntervalTier only.")

    # Overwrite
    target["data"] = [
        {
            "xmin": float(seg["start"]),
            "xmax": float(seg["end"]),
            "text": event_label,
            "confidence": 1 if float(seg["score"]) >= 0.7 else 0
        }
        for seg in segments
    ]
    target["finished"] = False
    return len(target["data"])


@preannotate_bp.route("/api/preannotate/file", methods=["POST"])
def preannotate_file():
    """
    Body:
    {
      "username": "...",
      "filename": "...",
      "event_label": "Speech",
      "threshold": 0.5,
      "min_duration_sec": 0.3,
      "target_tier_name": "bark type2",
      "overwrite": true
    }
    """
    try:
        payload = request.get_json(force=True)
        username = payload.get("username", "").strip()
        folder = Path(get_user_folder_path())
        filename = payload.get("filename", "").strip()
        fname_path = Path(filename)
        stem = fname_path.stem

        ann_path = folder / ANNOTATION_SUBDIR / stem / "annotations.json"
        audio_wav = folder / ANNOTATION_SUBDIR / stem / f"{stem}.wav"

        if not ann_path.exists():
            return jsonify({"error": f"annotations.json not found: {ann_path}"}), 404
        if not audio_wav.exists():
            return jsonify({"error": f"wav not found: {audio_wav}"}), 404

        event_label = payload.get("event_label", "").strip()
        threshold = float(payload.get("threshold", 0.5))
        min_duration_sec = float(payload.get("min_duration_sec", 0.3))

        target_tier_name = payload.get("target_tier_name", "").strip()
        overwrite = bool(payload.get("overwrite", True))

        if not username or not filename or not target_tier_name:
            return jsonify({"error": "username/filename/target_tier_name required"}), 400

        if event_label not in ALLOWED_LABELS:
            return jsonify({"error": f"event_label not allowed: {event_label}", "allowed": ALLOWED_LABELS}), 400

        if threshold < 0 or threshold > 1:
            return jsonify({"error": "threshold must be in [0, 1]"}), 400
        if min_duration_sec < 0:
            return jsonify({"error": "min_duration_sec must be >= 0"}), 400
        if not overwrite:
            return jsonify({"error": "overwrite=false not supported in current version"}), 400

        tiers = load_annotations_json(ann_path)
        segments = panns_preannotate(audio_wav, event_label, threshold, min_duration_sec)
        written = overwrite_target_tier(tiers, target_tier_name, event_label, segments)
        save_annotations_json(ann_path, tiers)

        return jsonify({
            "status": "done",
            "written": written,
            "target_tier_name": target_tier_name,
            "event_label": event_label,
            "threshold": threshold,
            "min_duration_sec": min_duration_sec,
            "annotation_json": str(ann_path)
        })

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500