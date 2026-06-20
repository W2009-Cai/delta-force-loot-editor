from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from common import command_text, find_binary, label_for, probe_video, read_json, run_command


PREVIEW_SIZE = (1280, 720)
FINAL_SIZE = (1920, 1080)
FINAL_OUTPUTS = {"master": "master_1k.mp4", "douyin": "douyin_1k.mp4"}


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    value = seconds % 60
    return f"{hours}:{minutes:02d}:{value:05.2f}"


def _map_events_to_output(timeline: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    offset = 0.0
    for segment in timeline:
        segment_start = float(segment["start"])
        segment_end = float(segment["end"])
        for event in events:
            raw_start = float(event.get("raw_start", event.get("start", 0)))
            raw_end = float(event.get("raw_end", event.get("end", raw_start)))
            if raw_end <= segment_start or raw_start >= segment_end:
                continue
            mapped_start = offset + max(0.0, raw_start - segment_start)
            mapped_end = offset + min(segment_end - segment_start, max(raw_end, raw_start + 1.0) - segment_start)
            mapped.append({**event, "output_start": mapped_start, "output_end": max(mapped_start + 0.25, mapped_end)})
        offset += segment_end - segment_start
    unique: dict[tuple[str, int], dict[str, Any]] = {}
    for event in mapped:
        key = (event.get("id", event.get("event", "event")), round(event["output_start"] * 1000))
        unique[key] = event
    return sorted(unique.values(), key=lambda item: item["output_start"])


def _write_event_ass(path: Path, timeline: list[dict[str, Any]], events: list[dict[str, Any]], width: int, height: int) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Event,Microsoft YaHei,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,0,8,80,80,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = []
    mapped = _map_events_to_output(timeline, events)
    if not mapped:
        mapped = [
            {"event": segment.get("event", "highlight"), "output_start": offset, "output_end": offset + min(2.0, float(segment["end"]) - float(segment["start"]))}
            for offset, segment in _segment_offsets(timeline)
        ]
    for event in mapped:
        start = float(event["output_start"])
        display_end = min(float(event["output_end"]), start + 2.0)
        label = label_for(event.get("event", "highlight")).replace(",", "，")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(display_end)},Event,,0,0,0,,{label}")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8-sig")


def _escape_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", "\\:").replace("'", "\\'")
    return value


def _segment_offsets(timeline: list[dict[str, Any]]) -> list[tuple[float, dict[str, Any]]]:
    offset = 0.0
    result: list[tuple[float, dict[str, Any]]] = []
    for segment in timeline:
        result.append((offset, segment))
        offset += float(segment["end"]) - float(segment["start"])
    return result


def _timeline_zoom_windows(timeline: list[dict[str, Any]], events: list[dict[str, Any]]) -> list[tuple[float, float]]:
    return [
        (max(0.0, float(item["output_start"]) - 0.5), float(item["output_end"]) + 0.75)
        for item in _map_events_to_output(timeline, events)
        if item.get("event") == "high_value_loot"
    ]


def _build_filter(
    timeline: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    has_audio: bool,
    width: int,
    height: int,
    fps_rate: str,
    douyin: bool,
    ass_path: Path | None,
    config: dict[str, Any] | None,
    enable_zoom: bool,
) -> tuple[str, str, str | None]:
    lines: list[str] = []
    labels: list[str] = []
    for index, segment in enumerate(timeline):
        start = float(segment["start"])
        end = float(segment["end"])
        duration = end - start
        if duration <= 0:
            continue
        lines.append(f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{index}]")
        labels.append(f"[v{index}]")
        if has_audio:
            fade_out = max(0.0, duration - 0.03)
            lines.append(
                f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out:.6f}:d=0.03[a{index}]"
            )
            labels.append(f"[a{index}]")
    count = len(timeline)
    if not count:
        raise ValueError("timeline contains no renderable clips")
    if has_audio:
        lines.append("".join(labels) + f"concat=n={count}:v=1:a=1[concatv][outa]")
    else:
        lines.append("".join(labels) + f"concat=n={count}:v=1:a=0[concatv]")
    lines.append(
        f"[concatv]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps_rate}[scaledv]"
    )
    current = "[scaledv]"
    if douyin and enable_zoom and config:
        roi_name = config.get("zoom_roi")
        roi = config.get("rois", {}).get(roi_name)
        windows = _timeline_zoom_windows(timeline, events)
        if roi and windows:
            crop_x = round(float(roi["x"]) * width)
            crop_y = round(float(roi["y"]) * height)
            crop_w = max(2, round(float(roi["w"]) * width))
            crop_h = max(2, round(float(roi["h"]) * height))
            enable = "+".join(f"between(t,{start:.3f},{end:.3f})" for start, end in windows)
            lines.append(f"{current}split=2[zoommain][zoomsource]")
            lines.append(
                f"[zoomsource]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
                "scale=640:-2,drawbox=x=0:y=0:w=iw:h=ih:color=white@0.9:t=6[zoomed]"
            )
            lines.append(f"[zoommain][zoomed]overlay=W-w-80:80:enable='{enable}'[zoomv]")
            current = "[zoomv]"
    if douyin and ass_path:
        escaped = _escape_filter_path(ass_path)
        lines.append(f"{current}ass='{escaped}'[outv]")
        current = "[outv]"
    return ";\n".join(lines), current, "[outa]" if has_audio else None


def render_variant(
    video: Path,
    timeline: list[dict[str, Any]],
    events: list[dict[str, Any]],
    output: Path,
    *,
    mode: str,
    douyin: bool,
    config: dict[str, Any] | None,
    enable_zoom: bool,
    ffmpeg: str,
    video_info: dict[str, Any],
) -> list[str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    preview = mode == "preview"
    width, height = PREVIEW_SIZE if preview else FINAL_SIZE
    crf = "28" if preview else ("19" if douyin else "18")
    preset = "ultrafast" if preview else "medium"
    ass_path = output.parent / "event_labels.ass" if douyin and not preview else None
    if ass_path:
        _write_event_ass(ass_path, timeline, events, width, height)
    filter_text, video_label, audio_label = _build_filter(
        timeline,
        events,
        has_audio=bool(video_info["has_audio"]),
        width=width,
        height=height,
        fps_rate=video_info["fps_rate"],
        douyin=douyin,
        ass_path=ass_path,
        config=config,
        enable_zoom=enable_zoom,
    )
    filter_path = output.parent / f"{output.stem}_filter.txt"
    filter_path.write_text(filter_text, encoding="utf-8")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
        "-i", str(video), "-filter_complex_script", str(filter_path), "-map", video_label,
    ]
    if audio_label:
        cmd.extend(["-map", audio_label])
    cmd.extend(
        [
            "-c:v", "libx264", "-profile:v", "high", "-preset", preset, "-crf", crf,
            "-pix_fmt", "yuv420p", "-r", video_info["fps_rate"],
        ]
    )
    if audio_label:
        cmd.extend(["-c:a", "aac", "-ac", "2", "-ar", "48000", "-b:a", "256k"])
    cmd.extend(["-movflags", "+faststart", str(output)])
    run_command(cmd)
    return cmd


def _clip_command(
    ffmpeg: str,
    video: Path,
    target: Path,
    start: float,
    end: float,
    has_audio: bool,
) -> list[str]:
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
        "-ss", f"{start:.6f}", "-t", f"{end - start:.6f}", "-i", str(video),
        "-map", "0:v:0",
    ]
    if has_audio:
        cmd.extend(["-map", "0:a?"])
    cmd.extend(["-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"])
    if has_audio:
        cmd.extend(["-c:a", "aac", "-ac", "2", "-ar", "48000", "-b:a", "256k"])
    cmd.extend(["-movflags", "+faststart", str(target)])
    return cmd


def _publish_clip(target: Path, package_target: Path) -> None:
    if package_target.exists():
        package_target.unlink()
    try:
        os.link(target, package_target)
    except OSError:
        shutil.copy2(target, package_target)


def _valid_existing_clip(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        return float(probe_video(path).get("duration", 0)) > 0
    except (OSError, RuntimeError, ValueError):
        return False


def render_event_clips(video: Path, events: list[dict[str, Any]], output_dir: Path, ffmpeg: str, has_audio: bool) -> list[list[str]]:
    clips_dir = output_dir / "event_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    package_clips = output_dir / "jianying_package" / "event_clips"
    package_clips.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for index, event in enumerate(events, start=1):
        start = float(event.get("start", event.get("raw_start", 0)))
        end = float(event.get("end", event.get("raw_end", start)))
        if end <= start:
            continue
        timecode = f"{int(start // 3600):02d}h{int(start % 3600 // 60):02d}m{int(start % 60):02d}s"
        name = f"{index:04d}_{timecode}_{event['event']}.mp4"
        target = clips_dir / name
        cmd = _clip_command(ffmpeg, video, target, start, end, has_audio)
        if not _valid_existing_clip(target):
            run_command(cmd)
            commands.append(cmd)
        _publish_clip(target, package_clips / name)
    return commands


def render_timeline_clips(video: Path, timeline: list[dict[str, Any]], output_dir: Path, ffmpeg: str, has_audio: bool) -> list[list[str]]:
    clips_dir = output_dir / "timeline_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    package_clips = output_dir / "jianying_package" / "timeline_clips"
    package_clips.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for index, segment in enumerate(timeline, start=1):
        start = float(segment["start"])
        end = float(segment["end"])
        if end <= start:
            continue
        timecode = f"{int(start // 3600):02d}h{int(start % 3600 // 60):02d}m{int(start % 60):02d}s"
        name = f"{index:04d}_{timecode}_{segment.get('event', 'highlight')}.mp4"
        target = clips_dir / name
        cmd = _clip_command(ffmpeg, video, target, start, end, has_audio)
        if not _valid_existing_clip(target):
            run_command(cmd)
            commands.append(cmd)
        _publish_clip(target, package_clips / name)
    return commands


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Delta Force timeline and JianYing event clips")
    parser.add_argument("video")
    parser.add_argument("--timeline")
    parser.add_argument("--events")
    parser.add_argument("--config")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=["preview", "final"], default="final")
    parser.add_argument("--variant", choices=["all", "master", "douyin"], default="all")
    parser.add_argument("--enable-loot-zoom", action="store_true")
    parser.add_argument("--event-clips-only", action="store_true")
    parser.add_argument("--timeline-clips-only", action="store_true")
    args = parser.parse_args()

    video = Path(args.video).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_binary("ffmpeg")
    info = probe_video(video)
    commands: list[list[str]] = []

    if args.timeline_clips_only:
        if not args.timeline:
            parser.error("--timeline is required with --timeline-clips-only")
        commands.extend(render_timeline_clips(video, read_json(args.timeline), output_dir, ffmpeg, bool(info["has_audio"])))
    elif args.event_clips_only:
        if not args.events:
            parser.error("--events is required with --event-clips-only")
        commands.extend(render_event_clips(video, read_json(args.events), output_dir, ffmpeg, bool(info["has_audio"])))
    else:
        if not args.timeline:
            parser.error("--timeline is required for video rendering")
        timeline = read_json(args.timeline)
        events = read_json(args.events) if args.events else []
        config = read_json(args.config) if args.config else None
        if args.mode == "preview":
            commands.append(render_variant(video, timeline, events, output_dir / "preview.mp4", mode="preview", douyin=False, config=config, enable_zoom=False, ffmpeg=ffmpeg, video_info=info))
        else:
            if args.variant in ("all", "master"):
                commands.append(render_variant(video, timeline, events, output_dir / FINAL_OUTPUTS["master"], mode="final", douyin=False, config=config, enable_zoom=False, ffmpeg=ffmpeg, video_info=info))
            if args.variant in ("all", "douyin"):
                commands.append(render_variant(video, timeline, events, output_dir / FINAL_OUTPUTS["douyin"], mode="final", douyin=True, config=config, enable_zoom=args.enable_loot_zoom, ffmpeg=ffmpeg, video_info=info))
    command_log = output_dir / "ffmpeg_commands.txt"
    with command_log.open("a", encoding="utf-8") as handle:
        for command in commands:
            handle.write(command_text(command) + "\n")
    print(f"Completed {len(commands)} FFmpeg command(s). Log: {command_log}")


if __name__ == "__main__":
    main()
