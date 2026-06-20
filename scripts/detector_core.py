from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from common import read_json


def read_image(path: str | Path) -> np.ndarray | None:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def write_image(path: str | Path, image: np.ndarray) -> bool:
    suffix = Path(path).suffix or ".png"
    success, encoded = cv2.imencode(suffix, image)
    if not success:
        return False
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))
    return True


def _crop_roi(image: np.ndarray, roi: dict[str, float] | None) -> np.ndarray | None:
    if not roi:
        return None
    height, width = image.shape[:2]
    x1 = max(0, min(width - 1, round(float(roi["x"]) * width)))
    y1 = max(0, min(height - 1, round(float(roi["y"]) * height)))
    x2 = max(x1 + 1, min(width, round((float(roi["x"]) + float(roi["w"])) * width)))
    y2 = max(y1 + 1, min(height, round((float(roi["y"]) + float(roi["h"])) * height)))
    return image[y1:y2, x1:x2]


def _template_scores(crop: np.ndarray, template: np.ndarray) -> tuple[float, float]:
    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    if template_gray.shape[0] > crop_gray.shape[0] or template_gray.shape[1] > crop_gray.shape[1]:
        template_gray = cv2.resize(template_gray, (crop_gray.shape[1], crop_gray.shape[0]), interpolation=cv2.INTER_AREA)
    match = cv2.matchTemplate(crop_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    template_score = float(np.nan_to_num(match, nan=0.0).max())
    resized = cv2.resize(template_gray, (crop_gray.shape[1], crop_gray.shape[0]), interpolation=cv2.INTER_AREA)
    a = crop_gray.astype(np.float32)
    b = resized.astype(np.float32)
    a -= a.mean()
    b -= b.mean()
    denominator = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    structure_score = float((a * b).sum() / denominator) if denominator else 0.0
    return max(0.0, template_score), max(0.0, structure_score)


def _color_score(crop: np.ndarray, ranges: list[dict[str, Any]]) -> tuple[float, float]:
    if not ranges:
        return 0.0, 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    best_score = 0.0
    best_ratio = 0.0
    for item in ranges:
        mask = cv2.inRange(hsv, np.array(item["lower"], dtype=np.uint8), np.array(item["upper"], dtype=np.uint8))
        ratio = float(np.count_nonzero(mask)) / float(mask.size)
        minimum = max(float(item.get("min_ratio", 0.01)), 1e-6)
        best_score = max(best_score, min(1.0, ratio / minimum))
        best_ratio = max(best_ratio, ratio)
    return best_score, best_ratio


def _edge_score(crop: np.ndarray, minimum: float = 0.04, target: float = 0.16) -> tuple[float, float]:
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    density = float(np.count_nonzero(edges)) / float(edges.size)
    score = max(0.0, min(1.0, (density - minimum) / max(target - minimum, 1e-6)))
    return score, density


def score_frame(
    frame: np.ndarray,
    event_config: dict[str, Any],
    manifest: dict[str, Any],
    templates_dir: Path,
    template_cache: dict[str, np.ndarray | None] | None = None,
) -> tuple[float, dict[str, float]]:
    roi = manifest.get("rois", {}).get(event_config.get("roi"))
    crop = _crop_roi(frame, roi)
    if crop is None or crop.size == 0:
        return 0.0, {"missing_roi": 1.0}

    evidence: dict[str, float] = {}
    scores: list[tuple[float, float]] = []
    template_name = event_config.get("template")
    template_path = templates_dir / template_name if template_name else None
    template = None
    if template_path and template_path.exists():
        cache_key = str(template_path.resolve())
        if template_cache is None:
            template = read_image(template_path)
        else:
            if cache_key not in template_cache:
                template_cache[cache_key] = read_image(template_path)
            template = template_cache[cache_key]
    if template is not None:
        template_score, structure_score = _template_scores(crop, template)
        evidence["template"] = round(template_score, 5)
        evidence["structure"] = round(structure_score, 5)
        scores.extend([(template_score, 0.55), (structure_score, 0.20)])
    elif event_config.get("required_template", False):
        return 0.0, {"missing_template": 1.0}

    color_score, color_ratio = _color_score(crop, event_config.get("hsv_ranges", []))
    if event_config.get("hsv_ranges"):
        evidence["color"] = round(color_score, 5)
        evidence["color_ratio"] = round(color_ratio, 5)
        scores.append((color_score, 0.20))

    edge_score, edge_density = _edge_score(
        crop,
        float(event_config.get("edge_density_min", 0.04)),
        float(event_config.get("edge_density_target", 0.16)),
    )
    evidence["edge"] = round(edge_score, 5)
    evidence["edge_density"] = round(edge_density, 5)
    scores.append((edge_score, 0.05 if template is not None else 0.35))

    weight = sum(item[1] for item in scores)
    confidence = sum(score * item_weight for score, item_weight in scores) / weight if weight else 0.0
    return max(0.0, min(1.0, confidence)), evidence


def observations_to_events(
    event_name: str,
    observations: list[dict[str, Any]],
    state_config: dict[str, Any],
    detector_name: str,
) -> list[dict[str, Any]]:
    threshold = float(state_config.get("candidate_threshold", 0.45))
    enter_frames = max(1, int(state_config.get("enter_frames", 2)))
    exit_frames = max(1, int(state_config.get("exit_frames", 3)))
    active = False
    positive_run: list[dict[str, Any]] = []
    active_samples: list[dict[str, Any]] = []
    misses = 0
    events: list[dict[str, Any]] = []

    def finish() -> None:
        nonlocal active, active_samples, misses
        if not active_samples:
            active = False
            misses = 0
            return
        peak = max(active_samples, key=lambda item: item["confidence"])
        sample_interval = max(0.0, float(state_config.get("sample_interval", 0.0)))
        events.append(
            {
                "event": event_name,
                "raw_start": round(active_samples[0]["time"], 3),
                "raw_end": round(active_samples[-1]["time"] + sample_interval, 3),
                "confidence": round(sum(item["confidence"] for item in active_samples) / len(active_samples), 5),
                "peak_confidence": round(peak["confidence"], 5),
                "peak_frame": peak["frame"],
                "evidence": peak["evidence"],
                "detector": detector_name,
            }
        )
        active = False
        active_samples = []
        misses = 0

    for observation in observations:
        if observation["confidence"] >= threshold:
            misses = 0
            if active:
                active_samples.append(observation)
            else:
                positive_run.append(observation)
                if len(positive_run) >= enter_frames:
                    active = True
                    active_samples = positive_run[:]
                    positive_run = []
        else:
            positive_run = []
            if active:
                misses += 1
                if misses >= exit_frames:
                    finish()
    if active:
        finish()
    return events


def detect_events(
    frames_manifest_path: str | Path,
    config_path: str | Path,
    event_names: list[str],
    detector_name: str,
) -> list[dict[str, Any]]:
    frames_manifest = read_json(frames_manifest_path)
    config = read_json(config_path)
    templates_dir = Path(config_path).resolve().parent
    event_configs = {
        event_name: config.get("events", {}).get(event_name)
        for event_name in event_names
        if config.get("events", {}).get(event_name)
    }
    observations: dict[str, list[dict[str, Any]]] = {event_name: [] for event_name in event_configs}
    template_cache: dict[str, np.ndarray | None] = {}
    for frame_info in frames_manifest.get("frames", []):
        frame = read_image(frame_info["path"])
        if frame is None:
            continue
        for event_name, event_config in event_configs.items():
            confidence, evidence = score_frame(frame, event_config, config, templates_dir, template_cache)
            observations[event_name].append(
                {
                    "time": float(frame_info["time"]),
                    "frame": frame_info["path"],
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )

    output: list[dict[str, Any]] = []
    for event_name in event_names:
        if event_name not in event_configs:
            continue
        state = dict(config.get("state", {}))
        sample_fps = float(frames_manifest.get("sample_fps", 0) or 0)
        state["sample_interval"] = 1.0 / sample_fps if sample_fps else 0.0
        output.extend(observations_to_events(event_name, observations[event_name], state, detector_name))
    return output
