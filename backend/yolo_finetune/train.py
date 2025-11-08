from ultralytics import YOLO
import os
import shutil

# Load a pretrained YOLOv8s model
model = YOLO("yolov8s.pt")

# Train the model
# By default, YOLO saves models to: runs/detect/train/weights/
# - best.pt: best model based on validation metrics
# - last.pt: last checkpoint from training
results = model.train(
    data="./dataset_fruits_detection/data.yaml",
    epochs=20,
    imgsz=640,
    batch=64,
    pretrained=True,
    project="./yolo_finetune",  # Project directory
    name="fruits_detection",     # Experiment name
    save=True,                   # Save checkpoints (default: True)
    save_period=5                # Save checkpoint every N epochs (optional)
)

# After training, the model is automatically saved, but you can also copy it to a custom location:
# Get the path to the best model
best_model_path = results.save_dir / "weights" / "best.pt"
print(f"✅ Best model saved to: {best_model_path}")

# Optionally, copy to a custom location for easier access
custom_save_path = "./yolo_finetune/fruits_detection_model.pt"
if best_model_path.exists():
    shutil.copy(best_model_path, custom_save_path)
    print(f"✅ Model also copied to: {custom_save_path}")

# Optional: Export to different formats (ONNX, TensorRT, etc.)
# model.export(format="onnx")  # Export to ONNX format
# print("✅ Model exported to ONNX format")

