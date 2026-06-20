from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import detector_core  # noqa: E402
from detector_core import detect_events  # noqa: E402


class DetectorTests(unittest.TestCase):
    def test_template_hysteresis_builds_one_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = np.zeros((40, 80, 3), dtype=np.uint8)
            cv2.rectangle(template, (3, 3), (76, 36), (20, 220, 250), 3)
            cv2.line(template, (10, 20), (70, 20), (255, 255, 255), 2)
            cv2.imwrite(str(root / "inventory.png"), template)
            frames = []
            for index in range(10):
                image = np.zeros((100, 200, 3), dtype=np.uint8)
                if 2 <= index <= 6:
                    image[10:50, 20:100] = template
                path = root / f"frame_{index:02d}.jpg"
                cv2.imwrite(str(path), image)
                frames.append({"index": index, "time": index * 0.25, "path": str(path)})
            (root / "frames.json").write_text(json.dumps({"frames": frames}), encoding="utf-8")
            config = {
                "state": {"enter_frames": 2, "exit_frames": 3, "candidate_threshold": 0.45},
                "rois": {"inventory": {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4}},
                "events": {"inventory_open": {"roi": "inventory", "template": "inventory.png", "required_template": True}},
            }
            (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
            events = detect_events(root / "frames.json", root / "config.json", ["inventory_open"], "test")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["raw_start"], 0.5)
            self.assertEqual(events[0]["raw_end"], 1.5)
            self.assertGreater(events[0]["confidence"], 0.7)

    def test_multiple_events_read_each_frame_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            template = np.zeros((20, 40, 3), dtype=np.uint8)
            cv2.rectangle(template, (2, 2), (37, 17), (255, 255, 255), 2)
            cv2.imwrite(str(root / "ui.png"), template)
            frames = []
            for index in range(4):
                image = np.zeros((50, 100, 3), dtype=np.uint8)
                path = root / f"frame_{index:02d}.jpg"
                cv2.imwrite(str(path), image)
                frames.append({"index": index, "time": index * 0.25, "path": str(path)})
            (root / "frames.json").write_text(json.dumps({"sample_fps": 4, "frames": frames}), encoding="utf-8")
            config = {
                "rois": {"ui": {"x": 0, "y": 0, "w": 1, "h": 1}},
                "events": {
                    "inventory_open": {"roi": "ui", "template": "ui.png", "required_template": True},
                    "loot_search": {"roi": "ui", "template": "ui.png", "required_template": True},
                },
            }
            (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
            with patch("detector_core.read_image", wraps=detector_core.read_image) as mocked:
                detect_events(root / "frames.json", root / "config.json", list(config["events"]), "test")
            self.assertEqual(mocked.call_count, len(frames) + 1)


if __name__ == "__main__":
    unittest.main()
