from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from build_timeline import build_outputs, write_review_html
from common import probe_video, read_json, write_json
from detector_core import detect_events
from extract_frames import extract_frames


def _default_config() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "templates" / "manifest.json"


def _calibration_warnings(config_path: Path) -> list[str]:
    config = read_json(config_path)
    warnings: list[str] = []
    templates_dir = config_path.parent
    for roi_name, roi in config.get("rois", {}).items():
        if roi is None:
            warnings.append(f"ROI not calibrated: {roi_name}")
    for event_name, event in config.get("events", {}).items():
        template = event.get("template")
        if event.get("required_template") and template and not (templates_dir / template).exists():
            warnings.append(f"Template missing for {event_name}: {template}")
    return warnings


def _overlaps(first: dict[str, Any], second: dict[str, Any], padding: float = 0.0) -> bool:
    return (
        float(first["raw_end"]) + padding > float(second["raw_start"])
        and float(first["raw_start"]) - padding < float(second["raw_end"])
    )


def _passes_event_gate(
    event: dict[str, Any],
    all_events: list[dict[str, Any]],
    event_config: dict[str, Any],
) -> tuple[bool, str | None]:
    required = event_config.get("requires_any_overlap", event_config.get("requires_overlap"))
    if not required:
        return True, None
    required_events = [required] if isinstance(required, str) else list(required)
    padding = max(0.0, float(event_config.get("overlap_padding", 0.5)))
    passed = any(
        candidate.get("event") in required_events and _overlaps(event, candidate, padding)
        for candidate in all_events
    )
    return passed, " | ".join(required_events)


def scan_video(
    video: str | Path,
    output_dir: str | Path,
    *,
    config_path: str | Path | None = None,
    sample_fps: float = 4.0,
    analysis_width: int | None = None,
    pre_roll: float = 3.0,
    post_roll: float = 2.0,
    merge_gap: float = 8.0,
    overrides_path: str | Path | None = None,
    keep_analysis_frames: bool = False,
    review_margin: float = 0.08,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source = Path(video).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = Path(config_path).resolve() if config_path else _default_config()
    if not config.exists():
        raise FileNotFoundError(config)
    config_data = read_json(config)
    analysis_width = int(analysis_width or config_data.get("analysis_width", 1280))

    video_info = probe_video(source)
    write_json(output / "video_info.json", video_info)
    warnings = _calibration_warnings(config)
    for warning in warnings:
        print(f"WARNING: {warning}")

    analysis_dir = output / ".analysis_frames"
    frames_manifest = extract_frames(
        source,
        analysis_dir,
        sample_fps=sample_fps,
        analysis_width=analysis_width,
    )
    manifest_path = analysis_dir / "frames_manifest.json"
    detector_events = detect_events(
        str(manifest_path),
        str(config),
        list(config_data.get("events", {})),
        "combined",
    )
    detector_events.sort(key=lambda item: (item["raw_start"], item["event"]))
    debug_dir = output / "debug_frames"
    debug_dir.mkdir(parents=True, exist_ok=True)
    raw_events: list[dict[str, Any]] = []
    for index, event in enumerate(detector_events, start=1):
        current = dict(event)
        event_config = config_data.get("events", {}).get(current["event"], {})
        threshold = float(event_config.get("auto_threshold", 0.75))
        gate_passed, gate_event = _passes_event_gate(current, detector_events, event_config)
        current["auto_threshold"] = threshold
        current["suggested_pre_roll"] = max(0.0, float(event_config.get("pre_roll", pre_roll)))
        current["suggested_post_roll"] = max(0.0, float(event_config.get("post_roll", post_roll)))
        current["gate_passed"] = gate_passed
        if gate_event:
            current["requires_overlap"] = gate_event
        current["auto_selected"] = float(current.get("confidence", 0)) >= threshold and gate_passed
        peak_path = Path(current.pop("peak_frame", ""))
        if peak_path.exists():
            debug_name = f"{index:04d}_{current['raw_start']:010.3f}_{current['event']}.jpg"
            shutil.copy2(peak_path, debug_dir / debug_name)
            current["debug_frame"] = f"debug_frames/{debug_name}"
        raw_events.append(current)
    raw_path = output / "events.raw.json"
    write_json(raw_path, raw_events)
    events, timeline = build_outputs(
        raw_path,
        output / "video_info.json",
        output,
        overrides_path=overrides_path,
        pre_roll=pre_roll,
        post_roll=post_roll,
        merge_gap=merge_gap,
    )
    review_margin = max(0.0, float(review_margin))
    uncertain_events = [
        event
        for event in events
        if abs(float(event.get("confidence", 0)) - float(event.get("auto_threshold", 0.75))) <= review_margin
        or not bool(event.get("gate_passed", True))
    ]
    write_review_html(output / "review_uncertain.html", uncertain_events, merge_gap)
    report = {
        "source": str(source),
        "config": str(config),
        "warnings": warnings,
        "sample_fps": sample_fps,
        "analysis_width": frames_manifest["analysis_width"],
        "analysis_height": frames_manifest["analysis_height"],
        "analysis_frame_count": len(frames_manifest["frames"]),
        "event_count": len(events),
        "selected_event_count": sum(1 for event in events if event["auto_selected"]),
        "uncertain_event_count": len(uncertain_events),
        "timeline_clip_count": len(timeline),
        "frame_extraction_command": frames_manifest["ffmpeg_command"],
    }
    write_json(output / "scan_report.json", report)
    if not keep_analysis_frames and analysis_dir.parent == output and analysis_dir.name == ".analysis_frames":
        shutil.rmtree(analysis_dir)
    return events, timeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan a Delta Force recording for loot and extraction events")
    parser.add_argument("video")
    parser.add_argument("--output-dir")
    parser.add_argument("--config")
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--analysis-width", type=int)
    parser.add_argument("--pre-roll", type=float, default=3.0)
    parser.add_argument("--post-roll", type=float, default=2.0)
    parser.add_argument("--merge-gap", type=float, default=8.0)
    parser.add_argument("--overrides")
    parser.add_argument("--keep-analysis-frames", action="store_true")
    parser.add_argument("--review-margin", type=float, default=0.08)
    args = parser.parse_args()
    source = Path(args.video).resolve()
    output = Path(args.output_dir).resolve() if args.output_dir else source.parent / "delta-force-output" / source.stem
    events, timeline = scan_video(
        source,
        output,
        config_path=args.config,
        sample_fps=args.sample_fps,
        analysis_width=args.analysis_width,
        pre_roll=args.pre_roll,
        post_roll=args.post_roll,
        merge_gap=args.merge_gap,
        overrides_path=args.overrides,
        keep_analysis_frames=args.keep_analysis_frames,
        review_margin=args.review_margin,
    )
    print(f"Scan complete: {len(events)} candidates, {len(timeline)} automatic clips")
    print(f"Review: {output / 'review.html'}")


if __name__ == "__main__":
    main()
