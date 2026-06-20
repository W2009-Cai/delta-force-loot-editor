from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_timeline import build_timeline  # noqa: E402


class TimelineTests(unittest.TestCase):
    def test_buffers_merges_and_keeps_raw_boundaries(self) -> None:
        events = [
            {"event": "container_open", "raw_start": 10.0, "raw_end": 12.0, "confidence": 0.8, "auto_selected": True},
            {"event": "high_value_loot", "raw_start": 17.0, "raw_end": 18.0, "confidence": 0.9, "auto_selected": True},
        ]
        normalized, timeline = build_timeline(events, duration=60.0)
        self.assertEqual((normalized[0]["raw_start"], normalized[0]["raw_end"]), (10.0, 12.0))
        self.assertEqual(len(timeline), 1)
        self.assertEqual((timeline[0]["start"], timeline[0]["end"]), (7.0, 20.0))
        self.assertIn("high_value_loot", timeline[0]["events"])

    def test_exclusion_splits_and_manual_include_survives(self) -> None:
        events = [
            {"event": "inventory_open", "raw_start": 20.0, "raw_end": 30.0, "confidence": 0.9, "auto_selected": True}
        ]
        overrides = {
            "exclude": [{"start": 23.0, "end": 27.0}],
            "include": [{"start": 40.0, "end": 42.0, "event": "manual_highlight"}],
        }
        _, timeline = build_timeline(events, duration=60.0, pre_roll=0, post_roll=0, merge_gap=1, overrides=overrides)
        self.assertEqual([(item["start"], item["end"]) for item in timeline], [(20.0, 23.0), (27.0, 30.0), (40.0, 42.0)])

    def test_unselected_event_stays_in_audit_only(self) -> None:
        events = [
            {"event": "loot_search", "raw_start": 3.0, "raw_end": 4.0, "confidence": 0.5, "auto_selected": False}
        ]
        normalized, timeline = build_timeline(events, duration=10.0)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(timeline, [])


if __name__ == "__main__":
    unittest.main()
