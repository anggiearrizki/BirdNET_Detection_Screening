"""Continuous BirdNET-Go detection watcher.

This process repeatedly runs the BirdNET detection scanner and places
new unverified detections into the local review queue.

Important:
- BirdNET-Go is read only.
- No Gemini calls are made.
- No BirdNET notes are written.
- No verification statuses are changed.

Stop the watcher with Ctrl+C.
"""

import argparse
import time

from birdnet_detection_scanner import (
    scan_detections,
    print_scan_summary,
)


def watch_detections(
    island,
    limit=200,
    interval_seconds=60,
    max_cycles=None,
):
    """Continuously scan BirdNET-Go for new detections."""

    cycle = 0

    print("=" * 72)
    print("BIRDNET-GO AUTOMATIC DETECTION WATCHER")
    print("=" * 72)

    print(
        "Island:",
        island,
    )

    print(
        "Scan interval:",
        f"{interval_seconds} seconds",
    )

    print(
        "Detection window:",
        limit,
    )

    print(
        "BirdNET-Go write-back: NO"
    )

    print(
        "Gemini calls: NO"
    )

    print()

    try:

        while True:

            cycle += 1

            print()
            print("#" * 72)
            print(
                f"WATCH CYCLE {cycle}"
            )
            print("#" * 72)

            result = scan_detections(
                island=island,
                limit=limit,
                bootstrap=False,
            )

            print_scan_summary(
                result
            )

            if result[
                "newly_queued"
            ]:

                print()
                print(
                    "NEW DETECTIONS ARE WAITING "
                    "IN THE REVIEW QUEUE."
                )

            if (
                max_cycles is not None
                and cycle >= max_cycles
            ):
                print()
                print(
                    "Maximum watch cycles reached."
                )

                break

            print()
            print(
                f"Waiting {interval_seconds} seconds "
                "before next scan..."
            )

            time.sleep(
                interval_seconds
            )

    except KeyboardInterrupt:

        print()
        print()
        print("=" * 72)
        print("WATCHER STOPPED")
        print("=" * 72)

        print(
            "Stopped by user."
        )

        print(
            "Scanner state and review queue "
            "have been preserved."
        )


def parse_args():
    """Parse watcher command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Continuously scan BirdNET-Go "
            "for new unverified detections."
        )
    )

    parser.add_argument(
        "--island",
        required=True,
        help=(
            "Property/island associated with "
            "this BirdNET-Go deployment."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help=(
            "Number of recent detections "
            "checked per scan. Default: 200."
        ),
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help=(
            "Seconds between scans. Default: 60."
        ),
    )

    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help=(
            "Optional maximum number of scan cycles. "
            "Omit to run until Ctrl+C."
        ),
    )

    return parser.parse_args()


def main():
    """Run the BirdNET-Go detection watcher."""

    args = parse_args()

    watch_detections(
        island=args.island,
        limit=args.limit,
        interval_seconds=args.interval,
        max_cycles=args.max_cycles,
    )


if __name__ == "__main__":
    main()