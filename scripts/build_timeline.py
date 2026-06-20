from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

from common import EVENT_PRIORITY, label_for, read_json, seconds_to_clock, seconds_to_srt, write_json


def _subtract_interval(segment: dict[str, Any], cut_start: float, cut_end: float) -> list[dict[str, Any]]:
    start, end = float(segment["start"]), float(segment["end"])
    if cut_end <= start or cut_start >= end:
        return [segment]
    pieces: list[dict[str, Any]] = []
    if cut_start > start:
        left = dict(segment)
        left["end"] = round(min(cut_start, end), 3)
        pieces.append(left)
    if cut_end < end:
        right = dict(segment)
        right["start"] = round(max(cut_end, start), 3)
        pieces.append(right)
    return [piece for piece in pieces if piece["end"] - piece["start"] >= 0.1]


def _merge_segments(segments: list[dict[str, Any]], merge_gap: float) -> list[dict[str, Any]]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda item: (item["start"], item["end"]))
    merged: list[dict[str, Any]] = []
    for segment in ordered:
        events = list(dict.fromkeys(segment.get("events") or [segment.get("event", "unknown")]))
        current = {
            **segment,
            "events": events,
            "source_event_ids": list(segment.get("source_event_ids", [])),
        }
        if not merged or current["start"] - merged[-1]["end"] >= merge_gap:
            merged.append(current)
            continue
        target = merged[-1]
        target["end"] = round(max(float(target["end"]), float(current["end"])), 3)
        target["confidence"] = round(max(float(target.get("confidence", 0)), float(current.get("confidence", 0))), 5)
        target["events"] = list(dict.fromkeys(target["events"] + current["events"]))
        target["source_event_ids"] = list(dict.fromkeys(target["source_event_ids"] + current["source_event_ids"]))
        target["debug_frames"] = list(dict.fromkeys(target.get("debug_frames", []) + current.get("debug_frames", [])))
    for index, segment in enumerate(merged, start=1):
        segment["id"] = f"clip_{index:04d}"
        segment["event"] = max(segment["events"], key=lambda name: EVENT_PRIORITY.get(name, 0))
        segment["duration"] = round(float(segment["end"]) - float(segment["start"]), 3)
        segment["keep"] = True
    return merged


def build_timeline(
    events: list[dict[str, Any]],
    *,
    duration: float,
    pre_roll: float = 3.0,
    post_roll: float = 2.0,
    merge_gap: float = 8.0,
    overrides: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_events: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for index, raw in enumerate(sorted(events, key=lambda item: (item.get("raw_start", 0), item.get("event", ""))), start=1):
        event = dict(raw)
        event["id"] = event.get("id") or f"event_{index:04d}"
        event["raw_start"] = round(max(0.0, float(event.get("raw_start", event.get("start", 0)))), 3)
        event["raw_end"] = round(min(duration, max(event["raw_start"], float(event.get("raw_end", event.get("end", 0))))), 3)
        event["start"] = round(max(0.0, event["raw_start"] - pre_roll), 3)
        event["end"] = round(min(duration, event["raw_end"] + post_roll), 3)
        event["duration"] = round(event["raw_end"] - event["raw_start"], 3)
        event["auto_selected"] = bool(event.get("auto_selected", True))
        event["keep"] = event["auto_selected"]
        normalized_events.append(event)
        if event["auto_selected"]:
            selected.append(
                {
                    "start": event["start"],
                    "end": event["end"],
                    "event": event["event"],
                    "events": [event["event"]],
                    "confidence": event.get("confidence", 0.0),
                    "source_event_ids": [event["id"]],
                    "debug_frames": [event["debug_frame"]] if event.get("debug_frame") else [],
                }
            )

    rules = overrides or {}
    for manual_index, manual in enumerate(rules.get("include", []), start=1):
        start = max(0.0, float(manual["start"]))
        end = min(duration, float(manual["end"]))
        if end > start:
            selected.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "event": manual.get("event", "manual_highlight"),
                    "events": [manual.get("event", "manual_highlight")],
                    "confidence": 1.0,
                    "source_event_ids": [f"manual_{manual_index:04d}"],
                    "debug_frames": [],
                }
            )

    for exclusion in rules.get("exclude", []):
        cut_start = float(exclusion["start"])
        cut_end = float(exclusion["end"])
        next_selected: list[dict[str, Any]] = []
        for segment in selected:
            next_selected.extend(_subtract_interval(segment, cut_start, cut_end))
        selected = next_selected

    return normalized_events, _merge_segments(selected, merge_gap)


def write_events_csv(path: Path, events: list[dict[str, Any]]) -> None:
    fields = [
        "id", "event", "event_label", "raw_start", "raw_end", "raw_timecode", "raw_duration",
        "suggested_start", "suggested_end", "confidence", "peak_confidence", "auto_selected", "debug_frame",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "id": event["id"],
                    "event": event["event"],
                    "event_label": label_for(event["event"]),
                    "raw_start": event["raw_start"],
                    "raw_end": event["raw_end"],
                    "raw_timecode": seconds_to_clock(event["raw_start"]),
                    "raw_duration": event["duration"],
                    "suggested_start": event["start"],
                    "suggested_end": event["end"],
                    "confidence": event.get("confidence", 0),
                    "peak_confidence": event.get("peak_confidence", 0),
                    "auto_selected": event["auto_selected"],
                    "debug_frame": event.get("debug_frame", ""),
                }
            )


def write_event_srt(path: Path, events: list[dict[str, Any]]) -> None:
    blocks: list[str] = []
    for index, event in enumerate(events, start=1):
        start = float(event["raw_start"])
        end = max(start + 1.0, float(event["raw_end"]))
        confidence = round(float(event.get("confidence", 0)) * 100)
        blocks.append(
            f"{index}\n{seconds_to_srt(start)} --> {seconds_to_srt(end)}\n"
            f"[{label_for(event['event'])}] 置信度 {confidence}%\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8-sig")


def write_review_html(path: Path, events: list[dict[str, Any]], merge_gap: float) -> None:
    safe_json = json.dumps(events, ensure_ascii=False).replace("</", "<\\/")
    rows: list[str] = []
    for event in events:
        debug = event.get("debug_frame", "")
        debug_src = html.escape(debug.replace("\\", "/"), quote=True)
        image = f'<img src="{debug_src}" alt="debug">' if debug else "—"
        checked = "checked" if event.get("auto_selected") else ""
        rows.append(
            "<tr>"
            f'<td><input class="keep" type="checkbox" data-id="{html.escape(event["id"])}" {checked}></td>'
            f"<td>{html.escape(label_for(event['event']))}</td>"
            f"<td>{seconds_to_clock(event['raw_start'])}</td>"
            f"<td>{seconds_to_clock(event['raw_end'])}</td>"
            f"<td>{float(event.get('confidence', 0)):.1%}</td>"
            f"<td>{image}</td></tr>"
        )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>三角洲事件审核</title>
<style>body{{font-family:Segoe UI,Microsoft YaHei,sans-serif;background:#111;color:#eee;margin:24px}}button{{padding:9px 14px;margin-right:8px}}table{{border-collapse:collapse;width:100%;margin-top:16px}}th,td{{border:1px solid #444;padding:8px;text-align:left}}th{{background:#252525;position:sticky;top:0}}img{{width:240px;max-height:135px;object-fit:contain}}.muted{{color:#aaa}}</style></head>
<body><h1>《三角洲行动》事件审核</h1><p class="muted">所有候选均保留在 events.json。复选框只影响导出的审核时间线。</p>
<button onclick="exportTimeline()">导出审核后的 timeline.json</button><button onclick="selectAll(true)">全选</button><button onclick="selectAll(false)">全不选</button>
<table><thead><tr><th>保留</th><th>事件</th><th>开始</th><th>结束</th><th>置信度</th><th>调试截图</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<script>const events={safe_json};const mergeGap={merge_gap};
function selectAll(v){{document.querySelectorAll('.keep').forEach(x=>x.checked=v)}}
function exportTimeline(){{
 const ids=new Set([...document.querySelectorAll('.keep:checked')].map(x=>x.dataset.id));
 let clips=events.filter(e=>ids.has(e.id)).map(e=>({{start:e.start,end:e.end,event:e.event,events:[e.event],confidence:e.confidence,source_event_ids:[e.id],debug_frames:e.debug_frame?[e.debug_frame]:[],keep:true}})).sort((a,b)=>a.start-b.start);
 const merged=[]; for(const c of clips){{const p=merged[merged.length-1];if(!p||c.start-p.end>=mergeGap)merged.push(c);else{{p.end=Math.max(p.end,c.end);p.events=[...new Set([...p.events,...c.events])];p.source_event_ids.push(...c.source_event_ids);p.confidence=Math.max(p.confidence,c.confidence)}}}}
 merged.forEach((c,i)=>{{c.id=`clip_${{String(i+1).padStart(4,'0')}}`;c.duration=+(c.end-c.start).toFixed(3)}});
 const blob=new Blob([JSON.stringify(merged,null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='timeline.reviewed.json';a.click();URL.revokeObjectURL(a.href);
}}</script></body></html>"""
    path.write_text(document, encoding="utf-8")


def prepare_jianying_package(output_dir: Path) -> None:
    package = output_dir / "jianying_package"
    package.mkdir(parents=True, exist_ok=True)
    for name in ("events.csv", "events_markers.srt"):
        source = output_dir / name
        if source.exists():
            shutil.copy2(source, package / name)
    instructions = (
        "剪映导入步骤\r\n"
        "1. 导入原始完整录像。\r\n"
        "2. 导入 events_markers.srt 作为事件字幕轨。\r\n"
        "3. 按字幕时间定位所有原始事件。\r\n"
        "4. event_clips 文件夹可作为已裁切素材直接导入。\r\n"
        "5. events.csv 保存原始时间码、置信度和建议剪辑区间。\r\n"
    )
    (package / "导入说明.txt").write_text(instructions, encoding="utf-8-sig")


def build_outputs(
    events_path: str | Path,
    video_info_path: str | Path,
    output_dir: str | Path,
    *,
    overrides_path: str | Path | None = None,
    pre_roll: float = 3.0,
    post_roll: float = 2.0,
    merge_gap: float = 8.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    events = read_json(events_path)
    video_info = read_json(video_info_path)
    overrides = read_json(overrides_path) if overrides_path else None
    normalized, timeline = build_timeline(
        events,
        duration=float(video_info["duration"]),
        pre_roll=pre_roll,
        post_roll=post_roll,
        merge_gap=merge_gap,
        overrides=overrides,
    )
    write_json(output / "events.json", normalized)
    write_json(output / "timeline.json", timeline)
    write_events_csv(output / "events.csv", normalized)
    write_event_srt(output / "events_markers.srt", normalized)
    write_review_html(output / "review.html", normalized, merge_gap)
    prepare_jianying_package(output)
    return normalized, timeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Build auditable event files and automatic timeline")
    parser.add_argument("events")
    parser.add_argument("--video-info", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--overrides")
    parser.add_argument("--pre-roll", type=float, default=3.0)
    parser.add_argument("--post-roll", type=float, default=2.0)
    parser.add_argument("--merge-gap", type=float, default=8.0)
    args = parser.parse_args()
    events, timeline = build_outputs(
        args.events,
        args.video_info,
        args.output_dir,
        overrides_path=args.overrides,
        pre_roll=args.pre_roll,
        post_roll=args.post_roll,
        merge_gap=args.merge_gap,
    )
    print(f"Wrote {len(events)} events and {len(timeline)} timeline clips to {args.output_dir}")


if __name__ == "__main__":
    main()
