from ultralytics import YOLO
import cv2
import numpy as np
import torch
import time
import os
import sys
from PIL import Image
from torchvision import transforms
from ripe_detector import load_model

# Global YOLO model
model = YOLO("yolov8n.pt") 

def detect(image, allowed_classes=['*'], save=True, verbose=True):
    """
    Detect objects in an image and filter by allowed classes.
    
    Args:
        image: Path to image file or numpy array
        allowed_classes: List of class names to filter (default: ['Rubik'])
        save: Whether to save the annotated image (default: True)
        verbose: Whether to print detection info (default: True)
    
    Returns:
        dict: Contains 'detections' (list of filtered detections), 
              'annotated_image' (numpy array), and 'output_path' (str or None)
    """
    results = model.predict(image, save=save, conf=0.5, verbose=verbose) 

    # Optional: Accessing the results programmatically
    filtered_detections = []
    allow_all = "*" in allowed_classes
    annotated_image = None
    output_path = None
    
    for result in results:
        # 'boxes' contains bounding box coordinates, class labels, and confidence scores
        boxes = result.boxes
        if verbose:
            print(f"Detected {len(boxes)} objects.")
        
        # Get class names from the model
        class_names = model.names
        
        # Filter boxes by allowed classes
        for box in boxes:
            # box.xyxy: bounding box coordinates (x1, y1, x2, y2)
            # box.conf: confidence score
            # box.cls: class ID
            cls_id = int(box.cls.item())
            conf = box.conf.item()
            class_name = class_names[cls_id]
            coords = box.xyxy[0].cpu().numpy()
            
            # Only include detections that match allowed classes
            if allow_all or class_name in allowed_classes:
                detection = {
                    'class': class_name,
                    'confidence': conf,
                    'bbox': coords.tolist(),
                    'class_id': cls_id
                }
                filtered_detections.append(detection)
                if verbose:
                    print(f"Class: {class_name}, Confidence: {conf:.2f}, Box: {coords}")
        
        if verbose:
            print(f"Filtered to {len(filtered_detections)} objects matching allowed classes.")
        
        # Get the annotated image with bounding boxes and labels drawn
        annotated_image = result.plot()
        
        # Save the annotated image if requested
        if save:
            output_path = "detected_image.jpg"
            cv2.imwrite(output_path, annotated_image)
            if verbose:
                print(f"Annotated image saved to {output_path}")
    
    return {
        'detections': filtered_detections,
        'annotated_image': annotated_image,
        'output_path': output_path
    }


def get_ripe_transform():
    """
    Get the preprocessing transform for ripe detection model.
    
    Returns:
        transforms.Compose: Preprocessing transform pipeline
    """
    return transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])


def load_ripe_detection_model(model_path="./model/ripe_detector.pth"):
    """
    Load and setup the ripe detection model.
    
    Args:
        model_path: Path to the ripe detection model file
    
    Returns:
        tuple: (model, device, transform) - The loaded model, device, and transform
    """
    # Determine target device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    
    # Load model with proper device mapping (handles CUDA->CPU conversion)
    ripe_model = load_model(model_path, device=device)
    ripe_model.eval()
    transform = get_ripe_transform()
    return ripe_model, device, transform

def inference_ripe_from_array(model, image_array, device, transform):
    """
    Run ripe detection inference on a numpy array (BGR format from OpenCV).
    
    Args:
        model: The ripe detection model
        image_array: numpy array in BGR format (from cv2)
        device: torch device
        transform: preprocessing transform
    
    Returns:
        float: Probability of being fresh (0-1, where 1 = fresh, 0 = rotten)
    """
    # Convert BGR to RGB
    rgb_image = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
    # Convert numpy array to PIL Image
    pil_image = Image.fromarray(rgb_image)
    # Apply transform
    image_tensor = transform(pil_image)
    image_tensor = image_tensor.unsqueeze(0).to(device)
    
    with torch.no_grad():
        output = model(image_tensor)
        probability = torch.sigmoid(output).item()
    
    return probability


def normalize_bbox_coordinates(bbox, frame_shape):
    """
    Ensure bounding box coordinates are within frame bounds.
    
    Args:
        bbox: List of [x1, y1, x2, y2] coordinates
        frame_shape: Tuple of (height, width) of the frame
    
    Returns:
        tuple: (x1, y1, x2, y2) normalized coordinates
    """
    x1, y1, x2, y2 = map(int, bbox)
    height, width = frame_shape[:2]
    
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(width, x2)
    y2 = min(height, y2)
    
    return x1, y1, x2, y2


def crop_bounding_box(frame, bbox):
    """
    Crop a bounding box region from a frame.
    
    Args:
        frame: Input frame (numpy array)
        bbox: List of [x1, y1, x2, y2] coordinates
    
    Returns:
        numpy array or None: Cropped image, or None if invalid bbox
    """
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = normalize_bbox_coordinates(bbox, (height, width))
    
    if x2 > x1 and y2 > y1:
        return frame[y1:y2, x1:x2]
    return None


def get_ripe_percentage(cropped_image, ripe_model, device, transform):
    """
    Get ripe percentage for a cropped image.
    
    Args:
        cropped_image: Cropped image as numpy array
        ripe_model: The ripe detection model
        device: torch device
        transform: preprocessing transform
    
    Returns:
        float or None: Ripe percentage (0-100), or None if error
    """
    try:
        ripe_probability = inference_ripe_from_array(ripe_model, cropped_image, device, transform)
        return ripe_probability * 100  # Convert to percentage
    except Exception as e:
        print(f"Error in ripe detection: {e}")
        return None


def create_detection_label(class_name, confidence, ripe_percentage=None):
    """
    Create a label string for a detection.
    
    Args:
        class_name: Detected class name
        confidence: Detection confidence score
        ripe_percentage: Ripe percentage (optional)
    
    Returns:
        str: Formatted label string
    """
    label_parts = [f"{class_name}: {confidence:.2f}"]
    if ripe_percentage is not None:
        label_parts.append(f"Ripe: {ripe_percentage:.1f}%")
    return " | ".join(label_parts)


def draw_detection_label(frame, bbox, label, color=(0, 255, 0)):
    """
    Draw a bounding box and label on a frame.
    
    Args:
        frame: Frame to draw on (numpy array, modified in place)
        bbox: List of [x1, y1, x2, y2] coordinates
        label: Label text to display
        color: BGR color tuple for bounding box and label background
    """
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = normalize_bbox_coordinates(bbox, (height, width))
    
    # Draw bounding box
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    
    # Calculate text size and position
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    (label_width, label_height), baseline = cv2.getTextSize(
        label, font, font_scale, thickness
    )
    label_y = max(y1, label_height + 10)
    
    # Draw label background rectangle
    cv2.rectangle(
        frame,
        (x1, label_y - label_height - 10),
        (x1 + label_width, label_y + 5),
        color, -1
    )
    
    # Draw label text
    cv2.putText(
        frame, label,
        (x1, label_y),
        font, font_scale, (0, 0, 0), thickness
    )


def draw_fps(frame, fps, position=(10, 30), color=(0, 255, 0)):
    """
    Draw FPS counter on a frame.
    
    Args:
        frame: Frame to draw on (numpy array, modified in place)
        fps: FPS value to display
        position: Tuple of (x, y) position for FPS text
        color: BGR color tuple for FPS text
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    
    fps_text = f"FPS: {fps:.1f}"
    
    # Draw text with background for better visibility
    (text_width, text_height), baseline = cv2.getTextSize(
        fps_text, font, font_scale, thickness
    )
    
    # Draw background rectangle
    cv2.rectangle(
        frame,
        (position[0] - 5, position[1] - text_height - 5),
        (position[0] + text_width + 5, position[1] + 5),
        (0, 0, 0), -1
    )
    
    # Draw FPS text
    cv2.putText(
        frame, fps_text,
        position,
        font, font_scale, color, thickness
    )


def get_best_camera_index():
    """
    Find the best available camera index.
    Uses the lowest index (typically index 0, built-in camera).
    
    Returns:
        int: Camera index to use, or 0 if no cameras found
    """
    available_cameras = []
    
    # Suppress OpenCV warnings while detecting cameras
    from contextlib import redirect_stderr, redirect_stdout
    
    with open(os.devnull, 'w') as devnull:
        with redirect_stderr(devnull), redirect_stdout(devnull):
            for i in range(11):  # Check indices 0-10
                try:
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        # Try to read a frame to confirm it's working
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            available_cameras.append(i)
                        cap.release()
                except Exception:
                    # Silently ignore any errors
                    pass
    
    if not available_cameras:
        print("Warning: No cameras found, defaulting to index 0")
        return 0
    
    # Return the lowest index (typically built-in camera)
    best_index = min(available_cameras)
    if len(available_cameras) > 1:
        print(f"Found {len(available_cameras)} camera(s). Using camera index {best_index} (lowest index).")
    else:
        print(f"Using camera index {best_index}.")
    
    return best_index


class FPSCounter:
    """
    Simple FPS counter that calculates average FPS over a window of frames.
    """
    def __init__(self, window_size=30):
        """
        Initialize FPS counter.
        
        Args:
            window_size: Number of frames to average over
        """
        self.window_size = window_size
        self.frame_times = []
        self.last_time = time.time()
    
    def update(self):
        """
        Update FPS counter with current frame time.
        
        Returns:
            float: Current FPS
        """
        current_time = time.time()
        frame_time = current_time - self.last_time
        self.last_time = current_time
        
        # Add frame time to list
        self.frame_times.append(frame_time)
        
        # Keep only last window_size frames
        if len(self.frame_times) > self.window_size:
            self.frame_times.pop(0)
        
        # Calculate average FPS
        if len(self.frame_times) > 0:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0.0
        else:
            fps = 0.0
        
        return fps


def process_detections_with_ripe(frame, detections, ripe_model, device, transform):
    """
    Process detections and add ripe information, then draw on frame.
    
    Args:
        frame: Input frame (numpy array, will be modified)
        detections: List of detection dictionaries
        ripe_model: The ripe detection model
        device: torch device
        transform: preprocessing transform
    
    Returns:
        numpy array: Annotated frame with detections and ripe percentages
    """
    annotated_frame = frame.copy()
    
    for detection in detections:
        bbox = detection['bbox']
        class_name = detection['class']
        confidence = detection['confidence']
        
        # Crop the bounding box
        cropped = crop_bounding_box(frame, bbox)
        
        # Get ripe percentage if crop is valid
        ripe_percentage = None
        if cropped is not None:
            ripe_percentage = get_ripe_percentage(cropped, ripe_model, device, transform)
        
        # Create label with class, confidence, and ripe percentage
        label = create_detection_label(class_name, confidence, ripe_percentage)
        
        # Draw detection on frame
        draw_detection_label(annotated_frame, bbox, label)
    
    return annotated_frame


def run_webcam_detection(allowed_classes=['*'], ripe_model_path="./model/ripe_detector.pth"):
    """
    Run real-time detection with ripe analysis on webcam feed.
    
    Args:
        allowed_classes: List of allowed class names for detection (default: ['*'] for all)
        ripe_model_path: Path to the ripe detection model
    """
    # Load ripe detection model
    try:
        ripe_model, device, ripe_transform = load_ripe_detection_model(ripe_model_path)
    except Exception as e:
        print(f"Error loading ripe model: {e}")
        print("Continuing without ripe detection...")
        ripe_model, device, ripe_transform = None, None, None
    
    # Open webcam - use highest available camera index (prefers USB cameras)
    camera_index = get_best_camera_index()
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print("Error: Could not open webcam")
        return
    
    print("Starting real-time detection with ripe analysis. Press 'q' to quit.")
    
    # Initialize FPS counter
    fps_counter = FPSCounter(window_size=30)
    
    try:
        while True:
            # Read frame from webcam
            ret, frame = cap.read()
            
            if not ret:
                print("Error: Failed to grab frame")
                break
            
            # Get detections
            result = detect(frame, allowed_classes=allowed_classes, save=False, verbose=False)
            detections = result['detections']
            
            # Process detections with ripe analysis
            if ripe_model is not None:
                annotated_frame = process_detections_with_ripe(
                    frame, detections, ripe_model, device, ripe_transform
                )
            else:
                # Fallback: use YOLO's annotated image if ripe model not available
                annotated_frame = result['annotated_image']
            
            # Update and draw FPS
            fps = fps_counter.update()
            draw_fps(annotated_frame, fps)
            
            # Display the annotated frame
            cv2.imshow('Real-time Detection', annotated_frame)
            
            # Break loop on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        # Release webcam and close windows
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released and windows closed")


if __name__ == "__main__":
    import sys
    
    # If an image path is provided as argument, run detection on it
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        allowed_classes = sys.argv[2:] if len(sys.argv) > 2 else ['*']
        print(f"Running detection on: {image_path}")
        print(f"Allowed classes: {allowed_classes}")
        result = detect(image_path, allowed_classes=allowed_classes, save=True, verbose=True)
        print(f"\n✅ Detection complete!")
        print(f"Found {len(result['detections'])} objects")
        if result['output_path']:
            print(f"Output saved to: {result['output_path']}")
    else:
        # Run webcam detection
        run_webcam_detection(allowed_classes=['*'])