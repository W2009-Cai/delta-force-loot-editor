from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from common import command_text, find_binary, probe_video, run_command, write_json


def extract_frames(
    video: str | Path,
    output_dir: str | Path,
    *,
    sample_fps: float = 4.0,
    analysis_width: int = 1280,
    ffmpeg: str | None = None,
    ffprobe: str | None = None,
) -> dict:
    if not 2.0 <= sample_fps <= 5.0:
        raise ValueError("sample_fps must be between 2 and 5")
    source = Path(video).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for old_frame in output.glob("frame_*.jpg"):
        old_frame.unlink()

    video_info = probe_video(source, ffprobe)
    binary = ffmpeg or find_binary("ffmpeg")
    pattern = output / "frame_%08d.jpg"
    vf = f"fps={sample_fps:g},scale={analysis_width}:-2"
    cmd = [
        binary,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        vf,
        "-q:v",
        "3",
        str(pattern),
    ]
    run_command(cmd)
    frame_paths = sorted(output.glob("frame_*.jpg"))
    if not frame_paths:
        raise RuntimeError("FFmpeg produced no analysis frames")
    first_data = np.fromfile(str(frame_paths[0]), dtype=np.uint8)
    first = cv2.imdecode(first_data, cv2.IMREAD_COLOR) if first_data.size else None
    if first is None:
        raise RuntimeError(f"Unable to read extracted frame: {frame_paths[0]}")
    height, width = first.shape[:2]
    frames = [
        {"index": index, "time": round((index - 1) / sample_fps, 3), "path": str(path.resolve())}
        for index, path in enumerate(frame_paths, start=1)
    ]
    manifest = {
        "source": str(source),
        "sample_fps": sample_fps,
        "analysis_width": width,
        "analysis_height": height,
        "source_info": video_info,
        "ffmpeg_command": command_text(cmd),
        "frames": frames,
    }
    write_json(output / "frames_manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract 2-5 analysis frames per second with FFmpeg")
    parser.add_argument("video")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--analysis-width", type=int, default=1280)
    args = parser.parse_args()
    manifest = extract_frames(args.video, args.output_dir, sample_fps=args.sample_fps, analysis_width=args.analysis_width)
    print(f"Extracted {len(manifest['frames'])} frames to {args.output_dir}")


if __name__ == "__main__":
    main()
