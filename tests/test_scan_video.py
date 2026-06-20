from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from scan_video import _passes_event_gate  # noqa: E402


class ScanVideoTests(unittest.TestCase):
    def test_high_value_gate_requires_inventory_overlap(self) -> None:
        high_value = {"event": "high_value_loot", "raw_start": 10.0, "raw_end": 11.0}
        config = {"requires_overlap": "inventory_open", "overlap_padding": 0.5}
        passed, required = _passes_event_gate(
            high_value,
            [high_value, {"event": "inventory_open", "raw_start": 9.75, "raw_end": 10.25}],
            config,
        )
        self.assertTrue(passed)
        self.assertEqual(required, "inventory_open")

        passed, _ = _passes_event_gate(
            high_value,
            [high_value, {"event": "inventory_open", "raw_start": 20.0, "raw_end": 21.0}],
            config,
        )
        self.assertFalse(passed)


if __name__ == "__main__":
    unittest.main()
