"""Local event storage and optional backend delivery."""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import EVIDENCE_DIR, LOG_DIR, API_URL, API_TOKEN

EVENT_LOG = LOG_DIR / "events.jsonl"
logger = logging.getLogger("WildSentinelAI.events")


def record_event(detections, camera_id, source, evidence_path):
    """Save one encounter locally and attempt backend delivery."""
    best = max(detections, key=lambda item: item["confidence"])
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "leopard_detected",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "camera_id": camera_id,
        "source": str(source),
        "class_name": "leopard",
        "confidence": best["confidence"],
        "bbox_xyxy": best["bbox_xyxy"],
        "detections": detections,
        "evidence_filename": Path(evidence_path).name,
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    if not API_URL:
        logger.info("Event saved locally; backend URL is not configured.")
        return event

    endpoint = API_URL.rstrip("/")
    if not endpoint.endswith("/api/events"):
        endpoint += "/api/events"
    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}

    try:
        with open(evidence_path, "rb") as image:
            response = requests.post(
                endpoint,
                headers=headers,
                data={"event": json.dumps(event)},
                files={"evidence": (Path(evidence_path).name, image, "image/jpeg")},
                timeout=(5, 20),
            )
        response.raise_for_status()
        logger.info("Event delivered to backend: %s", event["event_id"])
    except requests.RequestException:
        logger.exception("Backend delivery failed; local event was retained.")

    return event
