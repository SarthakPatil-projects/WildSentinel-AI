import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
import mysql.connector
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException

load_dotenv()

app = FastAPI(title="WildSentinel AI API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WildSentinelAI")

MIN_ALERT_CONFIDENCE = 0.80
UPLOAD_DIR = Path("uploads")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3307")),
        database=os.getenv("DB_NAME", "wildsentinel"),
        user=os.getenv("DB_USER", "wildsentinel_app"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def init_db():
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                event_time VARCHAR(40),
                camera_id VARCHAR(100),
                confidence FLOAT,
                details JSON,
                evidence_path VARCHAR(500),
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
    finally:
        conn.close()


def send_telegram_alert(message, evidence_path=None):
    """Send a Telegram message and optionally attach the evidence image."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "Telegram is not configured; event remains stored in MySQL."
        )
        return False

    base_url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    )

    try:
        if evidence_path and Path(evidence_path).is_file():
            with Path(evidence_path).open("rb") as image:
                response = requests.post(
                    f"{base_url}/sendPhoto",
                    data={
                        "chat_id": TELEGRAM_CHAT_ID,
                        "caption": message[:1024],
                    },
                    files={
                        "photo": (
                            Path(evidence_path).name,
                            image,
                            "image/jpeg",
                        )
                    },
                    timeout=15,
                )
        else:
            response = requests.post(
                f"{base_url}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                },
                timeout=10,
            )

        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            logger.error("Telegram API reported that sending failed.")
            return False

        logger.info("Telegram alert sent successfully.")
        return True

    except (requests.RequestException, ValueError):
        logger.exception(
            "Telegram alert failed; the database event is retained."
        )
        return False


@app.on_event("startup")
def startup():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        logger.info("Telegram alert configuration found.")
    else:
        logger.warning(
            "Telegram credentials are missing from the .env file."
        )


@app.get("/health")
def health():
    return {"status": "ok", "service": "WildSentinel AI"}


@app.post("/api/events")
async def receive_event(
    event: str = Form(...),
    evidence: UploadFile = File(...),
):
    try:
        data = json.loads(event)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="event must be valid JSON",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400,
            detail="event must be a JSON object",
        )

    if not evidence.filename:
        raise HTTPException(
            status_code=400,
            detail="Evidence filename missing",
        )

    suffix = Path(evidence.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        suffix = ".jpg"

    filename = (
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
        f"{suffix}"
    )
    path = UPLOAD_DIR / filename

    content = await evidence.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Evidence file is empty",
        )

    path.write_bytes(content)

    detections = data.get("detections", [])
    if not isinstance(detections, list):
        detections = []

    confidences = []
    for detection in detections:
        if not isinstance(detection, dict):
            continue
        try:
            value = float(detection.get("confidence", 0))
            if 0 <= value <= 1:
                confidences.append(value)
        except (TypeError, ValueError):
            continue

    confidence = max(confidences, default=0.0)

    event_time = str(
        data.get(
            "timestamp_utc",
            data.get(
                "timestamp",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    )
    camera_id = str(data.get("camera_id", "unknown"))
    event_uuid = str(data.get("event_id", "unknown"))

    # Save the event first, so Telegram failure cannot lose the record.
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO events
                (event_time, camera_id, confidence, details, evidence_path)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                event_time,
                camera_id,
                confidence,
                json.dumps(data),
                str(path),
            ),
        )
        conn.commit()
        event_id = cur.lastrowid
        cur.close()
    except Exception:
        path.unlink(missing_ok=True)
        logger.exception("Could not store event in MySQL.")
        raise HTTPException(
            status_code=500,
            detail="Could not store event",
        )
    finally:
        conn.close()

    # Notify Telegram only for qualifying leopard detections.
    class_name = str(data.get("class_name", "leopard")).lower()

    if class_name == "leopard" and confidence >= MIN_ALERT_CONFIDENCE:
        message = (
            "🚨 WILDSENTINEL AI — LEOPARD ALERT\n\n"
            f"Confidence: {confidence:.1%}\n"
            f"Camera: {camera_id}\n"
            f"Time (UTC): {event_time}\n"
            f"Event ID: {event_uuid}\n"
            f"Database ID: {event_id}\n\n"
            "Please verify the evidence and follow local wildlife "
            "safety procedures. Do not approach the animal."
        )

        send_telegram_alert(message, path)
    else:
        logger.info(
            "Event stored without Telegram alert "
            "(class=%s, confidence=%.2f).",
            class_name,
            confidence,
        )

    return {
        "status": "stored",
        "event_id": event_id,
        "telegram_eligible": (
            class_name == "leopard"
            and confidence >= MIN_ALERT_CONFIDENCE
        ),
    }