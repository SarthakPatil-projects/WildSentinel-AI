
"""Leopard detection component for WildSentinel AI."""

from ultralytics import YOLO

from config import MODEL_PATH, CONFIDENCE_THRESHOLD


class LeopardDetector:
    """Loads the trained model and detects leopards in video frames."""

    def __init__(self, confidence=None):
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"Trained model not found: {MODEL_PATH}"
            )

        self.confidence = (
            CONFIDENCE_THRESHOLD if confidence is None else confidence
        )
        self.model = YOLO(str(MODEL_PATH))

    def detect(self, frame):
        """
        Analyze one OpenCV frame.

        Returns:
            annotated_frame: frame with model-drawn bounding boxes
            detections: list of detected leopard objects
        """
        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            verbose=False,
        )

        result = results[0]
        annotated_frame = result.plot()
        detections = []

        if result.boxes is not None:
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                class_name = self.model.names[class_id]

                # This trained model is intended to detect leopards.
                if str(class_name).lower() != "leopard":
                    continue

                detections.append({
                    "class_name": "leopard",
                    "confidence": round(float(box.conf[0].item()), 4),
                    "bbox_xyxy": [
                        round(float(value), 2)
                        for value in box.xyxy[0].tolist()
                    ],
                })

        return annotated_frame, detections
