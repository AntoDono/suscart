from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt") 

# Define the source image (can be a local path, a URL, or even a video file)
source_image = "image.png" 

# Run prediction/inference on the image
# The 'save=True' argument saves the output image with bounding boxes drawn.
# The results will be saved in a directory like 'runs/detect/predict/'
results = model.predict(source_image, save=True, conf=0.5) 

# Optional: Accessing the results programmatically
for result in results:
    # 'boxes' contains bounding box coordinates, class labels, and confidence scores
    boxes = result.boxes
    print(f"Detected {len(boxes)} objects.")
    
    # Get class names from the model
    class_names = model.names
    
    # Get the annotated image with bounding boxes and labels drawn
    annotated_image = result.plot()
    
    # Save the annotated image
    output_path = "detected_image.jpg"
    cv2.imwrite(output_path, annotated_image)
    print(f"Annotated image saved to {output_path}")
    
    for box in boxes:
        # box.xyxy: bounding box coordinates (x1, y1, x2, y2)
        # box.conf: confidence score
        # box.cls: class ID
        cls_id = int(box.cls.item())
        conf = box.conf.item()
        class_name = class_names[cls_id]
        coords = box.xyxy[0].cpu().numpy()
        print(f"Class: {class_name}, Confidence: {conf:.2f}, Box: {coords}")