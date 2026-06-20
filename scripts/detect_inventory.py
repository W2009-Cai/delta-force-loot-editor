from __future__ import annotations

import argparse

from common import write_json
from detector_core import detect_events


EVENTS = ["inventory_open", "container_open", "safe_open"]


def run_detection(frames_manifest: str, config: str) -> list[dict]:
    return detect_events(frames_manifest, config, EVENTS, "inventory")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect inventory, container, and safe UI events")
    parser.add_argument("frames_manifest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    events = run_detection(args.frames_manifest, args.config)
    write_json(args.output, events)
    print(f"Detected {len(events)} inventory-related candidates")


if __name__ == "__main__":
    main()
