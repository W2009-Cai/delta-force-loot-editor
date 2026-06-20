from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import find_binary  # noqa: E402
from detector_core import write_image  # noqa: E402


EVENT_WINDOWS = {
    "inventory_open": (2.0, 3.0),
    "high_value_loot": (4.0, 5.0),
    "extraction_success": (7.0, 8.0),
    "settlement_screen": (9.0, 10.0),
}


def pattern(color: tuple[int, int, int], text: str) -> np.ndarray:
    image = np.zeros((72, 192, 3), dtype=np.uint8)
    cv2.rectangle(image, (3, 3), (188, 68), color, 4)
    cv2.line(image, (15, 48), (175, 48), (255, 255, 255), 3)
    cv2.putText(image, text, (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    return image


def create_fixture(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    templates = output_dir / "templates"
    templates.mkdir(exist_ok=True)
    colors = {
        "inventory_open": (200, 170, 20),
        "high_value_loot": (180, 30, 220),
        "extraction_success": (30, 220, 30),
        "settlement_screen": (20, 170, 250),
    }
    images = {name: pattern(color, name.split("_")[0].upper()) for name, color in colors.items()}
    for name, image in images.items():
        if not write_image(templates / f"{name}.png", image):
            raise RuntimeError(f"Could not write template: {name}")

    width, height, fps, duration = 640, 360, 30, 12
    silent = output_dir / "synthetic_silent.mp4"
    writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV VideoWriter could not create synthetic fixture")
    for frame_index in range(fps * duration):
        time = frame_index / fps
        frame = np.full((height, width, 3), (24, 28, 34), dtype=np.uint8)
        cv2.circle(frame, (int((time * 60) % width), 300), 20, (60, 80, 100), -1)
        for event, (start, end) in EVENT_WINDOWS.items():
            if start <= time <= end:
                frame[36:108, 64:256] = images[event]
        writer.write(frame)
    writer.release()

    video = output_dir / "synthetic_gameplay.mp4"
    ffmpeg = find_binary("ffmpeg")
    subprocess.run(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent),
            "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "18",
            "-c:a", "aac", "-b:a", "256k", "-shortest", str(video),
        ],
        check=True,
    )
    silent.unlink(missing_ok=True)

    roi = {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.2}
    config = {
        "version": 1,
        "analysis_width": 640,
        "state": {"enter_frames": 2, "exit_frames": 3, "candidate_threshold": 0.90},
        "rois": {
            "inventory_grid": roi,
            "container_title": None,
            "safe_panel": None,
            "item_detail": roi,
            "extraction_text": roi,
            "settlement_value": roi,
        },
        "events": {
            name: {"roi": roi_name, "template": f"{name}.png", "required_template": True, "auto_threshold": 0.95}
            for name, roi_name in {
                "inventory_open": "inventory_grid",
                "high_value_loot": "item_detail",
                "extraction_success": "extraction_text",
                "settlement_screen": "settlement_value",
            }.items()
        },
        "zoom_roi": "item_detail",
    }
    config_path = templates / "manifest.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return video, config_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir")
    args = parser.parse_args()
    video, config = create_fixture(Path(args.output_dir).resolve())
    print(video)
    print(config)


if __name__ == "__main__":
    main()
