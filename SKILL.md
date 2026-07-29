---
name: delta-force-loot-editor
description: Automate Chinese PC gameplay editing for Delta Force (《三角洲行动》) by detecting inventory, container searches and subtypes, safes, room-card pickup/use, ability activation, loot details, red/gold high-value loot, extraction, and settlement screens; preserve conversational context and produce auditable records, JianYing/剪映 handoff files, or optional 1080p cuts. Use for 三角洲行动剪辑、跑刀唠嗑视频、搜容器片段、拾取或刷房卡、放技能片段、红金出货、撤离视频、自动删跑图、背包 UI 自动剪辑, or equivalent gameplay-editing requests.
---

# Delta Force Loot Editor

Use this workflow for local gameplay footage. Preserve the source file and write every run to a separate output directory.

## Prerequisites

Verify `python`, `ffmpeg`, and `ffprobe` first. Install Python dependencies from `requirements.txt` in an isolated environment. On Windows, prefer `<skill_dir>\\.venv\\Scripts\\python.exe` when that runtime exists. Do not process footage until `ffprobe` succeeds.

Read [references/ui-regions.md](references/ui-regions.md) when calibrating a new UI resolution, operator, or game update. Read [references/event-taxonomy.md](references/event-taxonomy.md) when detecting containers, safes, room-card pickup/use, switch/power-pull route events, or red/gold loot. Read [references/editing-rules.md](references/editing-rules.md) before changing timeline or encoding defaults. Read [references/chat-loot-style.md](references/chat-loot-style.md) when the requested style combines casual commentary with container search, card use, and abilities.

## Workflow

1. Obtain one representative original-resolution recording. Extract positive frames for every requested event type: inventory, each container subtype, small/large safes, room-card pickup and use, each operator ability, loot detail, extraction, and settlement. Also extract ordinary-play negative frames.
2. Calibrate normalized ROIs and save stable cropped templates under `assets/templates/`; update `assets/templates/manifest.json`. Keep any uncalibrated detector inactive instead of lowering thresholds.
3. Scan without rendering first:

```powershell
python scripts/scan_video.py input.mp4 --output-dir output
```

4. Open `output/review_uncertain.html` for model-assisted review. Open `output/review.html` only when the user requests a full audit. Keep `events.json` unchanged as the full candidate record. Verify `loot_search` first, then classify its `subtype` from the preceding world view. Verify `room_card_pickup`, `card_use`, `safe_open`, `switch_pull`, and `ability_use` separately against their debug frames.
5. Review speech at each selected boundary. Preserve the complete sentence or thought around a detected event; event-specific padding in the manifest supplies the first pass, but use overrides to move boundaries to a natural pause. Do not claim automatic speech understanding from game audio.
6. Apply manual decisions with an overrides JSON when needed:

```json
{
  "exclude": [{"start": 80.0, "end": 95.0}],
  "include": [{"start": 210.0, "end": 224.0, "event": "manual_highlight"}]
}
```

```powershell
python scripts/build_timeline.py output/events.json --video-info output/video_info.json --output-dir output --overrides overrides.json
```

7. Default to the low-quota JianYing handoff: render the merged timeline clips, then verify them with `ffprobe`:

```powershell
python scripts/render_video.py input.mp4 --timeline output/timeline.json --output-dir output --timeline-clips-only
```

8. Render a preview or final 1080p outputs only when requested:

```powershell
python scripts/render_video.py input.mp4 --timeline output/timeline.json --output-dir output --mode preview
python scripts/render_video.py input.mp4 --timeline output/timeline.json --events output/events.json --config assets/templates/manifest.json --output-dir output --mode final --variant all
```

9. Generate one clip per exact event only when explicitly requested:

```powershell
python scripts/render_video.py input.mp4 --events output/events.json --output-dir output --event-clips-only
```

10. Verify output metadata with `ffprobe`, listen across every conversational cut, and sample frames around every visual cut. Fix false detections by changing templates/thresholds or event gates, not by hiding them from `events.json`.

For loot-route videos, do not reduce the story to only the container-open frame. Preserve switch/power-pull route events and, when there is a long ordinary-running gap before the next selected search/card/safe event, add a short arrival/transition context clip before that next event so the viewer understands the relocation path without keeping the full empty run.

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
