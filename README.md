# WildSentinel AI — Laptop 1

Local leopard detection using the trained YOLO model in `models/best.pt`.

## Run
Activate the virtual environment, then:
`python main.py --source webcam`

For a video file:
`python main.py --source "C:\path\to\video.mp4" --save-video`

Press Q in the preview window to stop.

## Backend
When Laptop 2 is configured, set `WILDSENTINEL_API_URL` to its private
base URL, for example `http://100.x.y.z:8000`. The server must implement
`POST /api/events` accepting multipart `event` JSON and `evidence` JPEG.

Events are stored locally in `logs/events.jsonl`; evidence is saved under
`evidence/`. Backend delivery has no automatic retry queue in this version.
