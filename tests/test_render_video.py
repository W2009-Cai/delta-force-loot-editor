from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from render_video import FINAL_OUTPUTS, FINAL_SIZE, PREVIEW_SIZE, _clip_command, _valid_existing_clip, render_variant  # noqa: E402


class RenderVideoTests(unittest.TestCase):
    def test_output_sizes_and_names(self) -> None:
        self.assertEqual(PREVIEW_SIZE, (1280, 720))
        self.assertEqual(FINAL_SIZE, (1920, 1080))
        self.assertEqual(FINAL_OUTPUTS["master"], "master_1k.mp4")
        self.assertEqual(FINAL_OUTPUTS["douyin"], "douyin_1k.mp4")

    def test_clip_seek_happens_before_input(self) -> None:
        command = _clip_command("ffmpeg", Path("input.mp4"), Path("output.mp4"), 120.0, 125.0, True)
        self.assertLess(command.index("-ss"), command.index("-i"))
        self.assertIn("-nostats", command)
        self.assertEqual(command[command.index("-loglevel") + 1], "error")

    def test_final_render_suppresses_progress_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch("render_video.run_command") as run:
            render_variant(
                Path("input.mp4"),
                [{"start": 0.0, "end": 1.0, "event": "inventory_open"}],
                [],
                Path(temporary) / "master_1k.mp4",
                mode="final",
                douyin=False,
                config=None,
                enable_zoom=False,
                ffmpeg="ffmpeg",
                video_info={"has_audio": False, "fps_rate": "30/1"},
            )
            command = run.call_args.args[0]
            self.assertIn("-nostats", command)
            self.assertEqual(command[command.index("-loglevel") + 1], "error")

    def test_existing_valid_clip_can_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            clip = Path(temporary) / "clip.mp4"
            clip.write_bytes(b"complete")
            with patch("render_video.probe_video", return_value={"duration": 5.0}):
                self.assertTrue(_valid_existing_clip(clip))


if __name__ == "__main__":
    unittest.main()
