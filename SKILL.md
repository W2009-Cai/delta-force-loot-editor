---
name: delta-force-loot-editor
description: Automate Chinese PC gameplay highlight editing for Delta Force (《三角洲行动》) by detecting inventory, containers, safes, loot details, high-value loot, extraction success, and settlement screens, then producing auditable event records, JianYing/剪映 handoff files, and 1920x1080 (1K) horizontal cuts. Use for 三角洲行动剪辑、三角洲出货视频、跑刀视频、搜物资视频、撤离视频、游戏录像高光、自动去掉跑图时间、根据背包 UI 自动剪辑, or equivalent requests about extracting loot events from gameplay recordings.
---

# Delta Force Loot Editor

Use this workflow for local gameplay footage. Preserve the source file and write every run to a separate output directory.

## Prerequisites

Verify `python`, `ffmpeg`, and `ffprobe` first. Install Python dependencies from `requirements.txt` in an isolated environment. On Windows, prefer `<skill_dir>\\.venv\\Scripts\\python.exe` when that runtime exists. Do not process footage until `ffprobe` succeeds.

Read [references/ui-regions.md](references/ui-regions.md) when calibrating a new UI resolution or game update. Read [references/editing-rules.md](references/editing-rules.md) before changing timeline or encoding defaults.

## Workflow

1. Ask for one original-resolution inventory screenshot and one representative recording when calibrated templates are absent.
2. Calibrate normalized ROIs and save cropped templates under `assets/templates/`; update `assets/templates/manifest.json`.
3. Scan without rendering first:

```powershell
python scripts/scan_video.py input.mp4 --output-dir output
```

4. Open `output/review_uncertain.html` for model-assisted review. Open `output/review.html` only when the user requests a full audit. Keep `events.json` unchanged as the full candidate record.
5. Apply manual decisions with an overrides JSON when needed:

```json
{
  "exclude": [{"start": 80.0, "end": 95.0}],
  "include": [{"start": 210.0, "end": 224.0, "event": "manual_highlight"}]
}
```

```powershell
python scripts/build_timeline.py output/events.json --video-info output/video_info.json --output-dir output --overrides overrides.json
```

6. Default to the low-quota JianYing handoff: render the merged timeline clips, then verify them with `ffprobe`:

```powershell
python scripts/render_video.py input.mp4 --timeline output/timeline.json --output-dir output --timeline-clips-only
```

7. Render a preview or final 1080p outputs only when requested:

```powershell
python scripts/render_video.py input.mp4 --timeline output/timeline.json --output-dir output --mode preview
python scripts/render_video.py input.mp4 --timeline output/timeline.json --events output/events.json --config assets/templates/manifest.json --output-dir output --mode final --variant all
```

8. Generate one clip per exact event only when explicitly requested:

```powershell
python scripts/render_video.py input.mp4 --events output/events.json --output-dir output --event-clips-only
```

9. Verify output metadata with `ffprobe` and sample frames around every cut. Fix false detections by changing templates/thresholds or event gates, not by hiding them from `events.json`.

Keep model context small: read targeted source ranges, never return FFmpeg progress logs, and use local HTML review instead of attaching all debug frames to the conversation.

## Output Contract

- `events.json` and `events.csv`: every detected candidate, including candidates excluded from the automatic cut.
- `timeline.json`: only segments selected for automatic rendering.
- `events_markers.srt`: original-source event markers importable by JianYing.
- `review.html`, `review_uncertain.html`, and `debug_frames/`: human review evidence.
- `timeline_clips/` and `jianying_package/`: default secondary-editing handoff.
- `event_clips/`: optional exact-event handoff.
- `master_1k.mp4`: optional clean 1920x1080 cut.
- `douyin_1k.mp4`: optional 1920x1080 16:9 cut with event labels and loot magnifier.
- `ffmpeg_commands.txt`: complete commands used by the renderer.

Never add unlicensed music. Never overwrite source footage. Do not claim detection quality before testing against the user's actual UI screenshot and recording.
