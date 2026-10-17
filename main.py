
"""WildSentinel AI — Laptop 1 edge detection application."""

import argparse
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

from config import (
    CAMERA_ID,
    CONFIDENCE_THRESHOLD,
    EVIDENCE_DIR,
    EVENT_COOLDOWN_SECONDS,
    LOG_DIR,
)
from detector import LeopardDetector
from event_manager import record_event

# Windows sound support
try:
    import winsound
except ImportError:
    winsound = None


LOG_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            LOG_DIR / "wildsentinel.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("WildSentinelAI")

# Minimum confidence required to create an event or play an alert.
MIN_EVENT_CONFIDENCE = 0.80


def parse_source(value):
    """Interpret webcam, camera index, or video source."""
    if value.lower() == "webcam":
        return 0
    if value.isdigit():
        return int(value)
    return value.strip().strip('"')


def play_alert_sound():
    """Play a repeating two-tone siren on Laptop 1."""
    if winsound is None:
        logger.warning("Sound alert unavailable on this system.")
        return

    def siren():
        try:
            # Repeat the siren three times.
            for _ in range(3):
                winsound.Beep(700, 350)
                winsound.Beep(1100, 350)
                time.sleep(0.15)
        except Exception:
            logger.exception("Could not play the siren alert.")

    threading.Thread(target=siren, daemon=True).start()


def run(args):
    detector = LeopardDetector(confidence=args.confidence)
    source = parse_source(args.source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video source: {args.source}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS) or 20.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Could not determine video dimensions.")

    writer = None
    output_path = None

    if args.save_video:
        output_path = EVIDENCE_DIR / (
            f"annotated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(
                f"Could not create output video: {output_path}"
            )

    frame_count = 0
    detected_frames = 0
    events_count = 0
    last_event_time = 0.0
    last_detection_time = 0.0
    encounter_active = False
    encounter_reset_seconds = 5.0

    logger.info("WildSentinel AI started.")
    logger.info("Source: %s | Camera ID: %s", args.source, CAMERA_ID)
    logger.info("Model confidence threshold: %.2f", args.confidence)
    logger.info(
        "Event confidence threshold: %.2f",
        MIN_EVENT_CONFIDENCE,
    )
    logger.info("Event cooldown: %.1f seconds", args.cooldown)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                logger.info("Video ended or no frame was received.")
                break

            frame_count += 1
            now = time.monotonic()

            annotated, detections = detector.detect(frame)

            # Only leopard detections with confidence >= 80% qualify.
            qualified_detections = [
                detection
                for detection in detections
                if (
                    str(detection.get("class_name", "leopard")).lower()
                    == "leopard"
                    and float(detection.get("confidence", 0.0))
                    >= MIN_EVENT_CONFIDENCE
                )
            ]

            if qualified_detections:
                detected_frames += 1
                last_detection_time = now

                if not encounter_active:
                    encounter_active = True

                    if now - last_event_time >= args.cooldown:
                        timestamp = datetime.now().strftime(
                            "%Y%m%d_%H%M%S_%f"
                        )[:-3]
                        evidence_path = (
                            EVIDENCE_DIR / f"leopard_{timestamp}.jpg"
                        )

                        if not cv2.imwrite(
                            str(evidence_path), annotated
                        ):
                            logger.error("Could not save evidence image.")
                        else:
                            try:
                                event = record_event(
                                    detections=qualified_detections,
                                    camera_id=CAMERA_ID,
                                    source=args.source,
                                    evidence_path=evidence_path,
                                )

                                events_count += 1
                                last_event_time = now

                                logger.warning(
                                    "LEOPARD DETECTED | confidence=%.2f "
                                    "| event=%s",
                                    event["confidence"],
                                    event["event_id"],
                                )

                                if args.sound_alert:
                                    play_alert_sound()

                            except Exception:
                                logger.exception(
                                    "Failed to record the leopard event."
                                )

            elif encounter_active and (
                now - last_detection_time >= encounter_reset_seconds
            ):
                encounter_active = False

            if writer is not None:
                writer.write(annotated)

            if not args.no_display:
                cv2.imshow(
                    "WildSentinel AI — Press Q to quit",
                    annotated,
                )
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Stopped by user.")
                    break

            if args.max_frames and frame_count >= args.max_frames:
                logger.info("Maximum frame count reached.")
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    logger.info(
        "Session finished: frames=%d, detection_frames=%d, events=%d",
        frame_count,
        detected_frames,
        events_count,
    )

    if output_path:
        logger.info("Annotated video saved to %s", output_path)


def main():
    parser = argparse.ArgumentParser(
        description="WildSentinel AI leopard detection"
    )
    parser.add_argument(
        "--source",
        default="webcam",
        help="Use webcam, camera index, or video stream/path",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=CONFIDENCE_THRESHOLD,
        help="Model confidence threshold between 0 and 1",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=EVENT_COOLDOWN_SECONDS,
        help="Minimum seconds between recorded encounters",
    )
    parser.add_argument(
        "--save-video",
        action="store_true",
        help="Save annotated video in the evidence folder",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="Run without opening a preview window",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional frame limit; 0 means unlimited",
    )
    parser.add_argument(
        "--sound-alert",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable or disable the Laptop 1 siren",
    )

    args = parser.parse_args()

    if not 0 < args.confidence <= 1:
        parser.error("--confidence must be greater than 0 and at most 1")
    if args.cooldown < 0 or args.max_frames < 0:
        parser.error("--cooldown and --max-frames cannot be negative")

    run(args)


if __name__ == "__main__":
    main()
