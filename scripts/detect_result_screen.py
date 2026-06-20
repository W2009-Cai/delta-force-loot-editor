from __future__ import annotations

import argparse

from common import write_json
from detector_core import detect_events


EVENTS = ["extraction_success", "settlement_screen"]


def run_detection(frames_manifest: str, config: str) -> list[dict]:
    return detect_events(frames_manifest, config, EVENTS, "result")


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect extraction success and settlement screens")
    parser.add_argument("frames_manifest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    events = run_detection(args.frames_manifest, args.config)
    write_json(args.output, events)
    print(f"Detected {len(events)} result-screen candidates")


if __name__ == "__main__":
    main()
