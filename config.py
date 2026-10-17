"""Optional settings for local WildSentinel AI."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "best.pt"
EVIDENCE_DIR = BASE_DIR / "evidence"
LOG_DIR = BASE_DIR / "logs"

CONFIDENCE_THRESHOLD = float(os.getenv("WILDSENTINEL_CONFIDENCE", "0.80"))
EVENT_COOLDOWN_SECONDS = int(os.getenv("WILDSENTINEL_COOLDOWN", "30"))
CAMERA_ID = os.getenv("WILDSENTINEL_CAMERA_ID", "camera-01")
API_URL = os.getenv("WILDSENTINEL_API_URL", "").strip()
API_TOKEN = os.getenv("WILDSENTINEL_API_TOKEN", "").strip()

EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
