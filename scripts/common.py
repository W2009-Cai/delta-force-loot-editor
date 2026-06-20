from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


EVENT_LABELS = {
    "inventory_open": "打开背包",
    "container_open": "打开容器",
    "safe_open": "打开保险箱",
    "loot_search": "搜索物资",
    "high_value_loot": "高价值物品",
    "extraction_success": "成功撤离",
    "settlement_screen": "结算价值",
    "manual_highlight": "手动高光",
}

EVENT_PRIORITY = {
    "extraction_success": 100,
    "settlement_screen": 90,
    "high_value_loot": 80,
    "safe_open": 70,
    "container_open": 60,
    "loot_search": 50,
    "inventory_open": 40,
    "manual_highlight": 30,
}


def find_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        link = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"
        if link.exists():
            return str(link)
    raise RuntimeError(f"Required executable not found: {name}")


def run_command(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )


def command_text(cmd: list[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in cmd])


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_rate(value: str | int | float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        return float(numerator) / denominator_value if denominator_value else 0.0
    return float(value)


def probe_video(video: str | Path, ffprobe: str | None = None) -> dict[str, Any]:
    binary = ffprobe or find_binary("ffprobe")
    result = run_command(
        [binary, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
        capture=True,
    )
    payload = json.loads(result.stdout)
    video_stream = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video_stream:
        raise RuntimeError(f"No video stream found: {video}")
    audio_stream = next((stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"), None)
    rotation = 0
    for side_data in video_stream.get("side_data_list", []):
        if "rotation" in side_data:
            rotation = int(side_data["rotation"])
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    if abs(rotation) in (90, 270):
        width, height = height, width
    avg_rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    duration = video_stream.get("duration") or payload.get("format", {}).get("duration") or 0
    return {
        "source": str(Path(video).resolve()),
        "duration": float(duration),
        "width": width,
        "height": height,
        "fps": parse_rate(avg_rate),
        "fps_rate": avg_rate,
        "rotation": rotation,
        "codec": video_stream.get("codec_name"),
        "profile": video_stream.get("profile"),
        "pixel_format": video_stream.get("pix_fmt"),
        "has_audio": audio_stream is not None,
        "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        "audio_sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream else None,
    }


def seconds_to_clock(seconds: float, *, milliseconds: bool = True) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        whole_seconds += 1
        millis = 0
    if milliseconds:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"


def seconds_to_srt(seconds: float) -> str:
    return seconds_to_clock(seconds).replace(".", ",")


def label_for(event: str) -> str:
    return EVENT_LABELS.get(event, event)
