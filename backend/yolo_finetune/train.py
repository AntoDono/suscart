from ultralytics import YOLO

# Load a pretrained YOLOv8s model
model = YOLO("yolov8s.pt")

# Train the model
results = model.train(
    data="data.yaml",
    epochs=20,
    imgsz=640,
    batch=16,
    pretrained=True
)