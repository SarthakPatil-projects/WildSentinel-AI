from ultralytics import YOLO

# Load our trained leopard detection model
model = YOLO("models/best.pt")

# Display the model's class names
print("Model loaded successfully!")
print("Class names:", model.names)