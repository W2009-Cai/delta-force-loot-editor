# Editing and delivery rules

- Sample at 4 fps by default; accept only 2-5 fps.
- Enter an event after 2 consecutive candidate frames and leave after 3 consecutive misses.
- Preserve raw event boundaries in `events.json`.
- Build automatic clips with 3 seconds before and 2 seconds after each event.
- Merge selected clips separated by less than 8 seconds.
- Apply exclusions after buffering and split a clip when an exclusion cuts through it.
- Apply manual includes before the final merge.
- Add 30ms audio fades at every output segment boundary.
- Render final files directly from the original source in one FFmpeg encode per deliverable.
- Master: 1920x1080, source fps, H.264 High, yuv420p, CRF 18, AAC 48kHz/256kbps, faststart.
- Douyin: 1920x1080 full 16:9 frame and source fps, CRF 19, event labels only; no unlicensed music.
- Preview: 1280x720, CRF 28, ultrafast.
- Keep `events.json` as the immutable detection audit; edits belong in `overrides.json` or a reviewed timeline.
- Gate high-value loot candidates on an overlapping inventory event unless a calibrated detector proves that the item detail UI is independently reliable.
- Use `review_uncertain.html` for model review; reserve the full review page for explicit audits.
- Default delivery is merged `timeline_clips/`. Exact event clips and final master/Douyin renders are opt-in.
- Run FFmpeg with error-only logging and no progress stats. Save commands to `ffmpeg_commands.txt` and return only summaries to the model.
