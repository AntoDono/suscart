# Video Streaming Protocol

This document explains the video streaming implementation for real-time fruit detection and ripeness analysis.

## Overview

The video streaming system uses WebSocket connections to stream video frames from the backend camera to the frontend. Each frame is processed for object detection (YOLO) and ripeness analysis, then sent to the client with detection metadata.

## WebSocket Endpoint

**Endpoint:** `ws://localhost:3000/ws/stream_video`

**Protocol:** WebSocket (supports both text and binary messages)

## Message Protocol

The backend sends **two messages per frame**:

### 1. Frame Metadata (JSON Text Message)

Sent first, contains detection results and frame information:

```json
{
  "type": "frame_meta",
  "detections": [
    {
      "bbox": [x1, y1, x2, y2],      // Bounding box coordinates (pixels)
      "class": "apple",               // Detected object class name
      "confidence": 0.95,             // Detection confidence (0-1)
      "ripe_score": 87.5             // Ripeness percentage (0-100) or null
    }
  ],
  "fps": 12.5,                       // Current frames per second
  "frame_size": 45678,                // Size of binary frame in bytes
  "timestamp": "2025-01-15T10:30:45.123456"
}
```

**Fields:**
- `type`: Always `"frame_meta"` for metadata messages
- `detections`: Array of detection objects (empty if no objects detected)
  - `bbox`: Bounding box `[x1, y1, x2, y2]` in pixel coordinates
  - `class`: Object class name (e.g., "apple", "banana", "orange")
  - `confidence`: Detection confidence score (0.0 to 1.0)
  - `ripe_score`: Ripeness percentage (0-100) or `null` if not available
- `fps`: Current processing frames per second (calculated over last 30 frames)
- `frame_size`: Size of the binary frame data in bytes
- `timestamp`: ISO 8601 timestamp of when frame was processed

### 2. Frame Data (Binary Message)

Sent immediately after metadata, contains the actual video frame:

**Format:** JPEG compressed image (binary)

**Encoding:**
- **Codec:** JPEG
- **Quality:** 85% (configurable via `cv2.IMWRITE_JPEG_QUALITY`)
- **Color Space:** BGR (OpenCV format, converted to RGB by browser)
- **Encoding:** Raw binary bytes (not base64)

**Size:** Typically 20-100 KB per frame depending on:
- Image resolution
- Scene complexity
- JPEG quality setting

## Frame Encoding Details

### Backend Processing Pipeline

1. **Frame Capture**
   ```python
   ret, frame = camera.read()  # Capture from camera (BGR format)
   ```

2. **Object Detection**
   ```python
   result = detect(frame, allowed_classes=['*'], save=False, verbose=False)
   # Uses YOLOv8 model for object detection
   ```

3. **Ripeness Analysis** (for each detection)
   ```python
   cropped = crop_bounding_box(frame, bbox)
   ripe_score = get_ripe_percentage(cropped, ripe_model, device, transform)
   # Uses custom CNN model for ripeness classification
   ```

4. **Frame Encoding**
   ```python
   _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
   frame_bytes = buffer.tobytes()
   ```

5. **Transmission**
   - Send JSON metadata message
   - Send binary JPEG frame data

### Why Binary Instead of Base64?

**Base64 encoding:**
- Increases data size by ~33% (4 bytes → 6 characters)
- Requires encoding/decoding overhead
- Example: 50 KB frame → ~67 KB base64 string

**Binary encoding:**
- No size overhead
- Direct transmission of compressed JPEG
- Example: 50 KB frame → 50 KB binary data
- **Result: ~33% bandwidth savings**

## Client-Side Handling

### WebSocket Setup

```javascript
const ws = new WebSocket('ws://localhost:3000/ws/stream_video');
ws.binaryType = 'arraybuffer';  // Important: handle binary as ArrayBuffer
```

### Message Handling

```javascript
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Binary frame data
    handleBinaryFrame(event.data);
  } else {
    // JSON metadata
    const data = JSON.parse(event.data);
    handleTextMessage(data);
  }
};
```

### Frame Display

1. **Receive metadata** → Store detection data
2. **Receive binary frame** → Convert to Blob URL
3. **Display frame** → Draw on canvas
4. **Draw annotations** → Overlay bounding boxes and labels

```javascript
// Convert binary to image
const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
const imageUrl = URL.createObjectURL(blob);

// Display frame
const img = new Image();
img.src = imageUrl;
img.onload = () => {
  ctx.drawImage(img, 0, 0);
  // Draw bounding boxes and labels from metadata
};
```

## Frame Rate Control

### Adaptive Rate Limiting

The backend uses adaptive frame rate control:

```python
elapsed = time.time() - frame_start_time
target_frame_time = 0.05  # Target 20 FPS
if elapsed < target_frame_time:
    time.sleep(target_frame_time - elapsed)
```

**Behavior:**
- If processing is fast (< 50ms): Sleep to cap at ~20 FPS
- If processing is slow (> 50ms): No sleep, run as fast as possible
- FPS is calculated from actual processing time (rolling average of last 30 frames)

### Performance Considerations

**Typical Processing Times:**
- Frame capture: ~5-10ms
- YOLO detection: ~30-100ms (depends on hardware)
- Ripeness analysis: ~10-20ms per detection
- JPEG encoding: ~5-10ms
- Network transmission: ~1-5ms

**Expected FPS:**
- CPU-only: ~5-10 FPS
- With GPU acceleration: ~15-30 FPS
- Maximum theoretical: ~20 FPS (limited by target_frame_time)

## Control Commands

### Start Streaming

**Client → Server:**
```json
{
  "command": "start"
}
```

**Server → Client:**
```json
{
  "type": "started",
  "message": "Camera started, streaming frames"
}
```

### Stop Streaming

**Client → Server:**
```json
{
  "command": "stop"
}
```

**Server → Client:**
```json
{
  "type": "stopped",
  "message": "Camera stopped"
}
```

## Error Handling

### Error Messages

```json
{
  "type": "error",
  "message": "Error description"
}
```

**Common Errors:**
- `"Failed to open camera"` - Camera device unavailable
- `"Failed to capture frame"` - Camera read error
- `"Camera already started"` - Start command sent while streaming
- `"Error processing frame: ..."` - Processing exception

## Data Flow Diagram

```
┌─────────────┐
│   Camera    │
└──────┬──────┘
       │ BGR Frame
       ▼
┌─────────────┐
│   YOLO      │ ──► Detections
│ Detection   │
└──────┬──────┘
       │ Frame + Detections
       ▼
┌─────────────┐
│  Ripeness   │ ──► Ripe Scores
│   Model     │
└──────┬──────┘
       │ Frame + Detections + Scores
       ▼
┌─────────────┐
│   JPEG      │ ──► Compressed Frame
│  Encoding   │
└──────┬──────┘
       │
       ├──► JSON Metadata (detections, fps, size)
       │
       └──► Binary JPEG Frame
            │
            ▼
    ┌──────────────┐
    │   WebSocket  │
    │  Connection  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   Frontend   │
    │   Display    │
    └──────────────┘
```

## Optimization Tips

1. **Reduce JPEG Quality** (if bandwidth is limited)
   ```python
   cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
   ```

2. **Resize Frames** (if resolution is too high)
   ```python
   frame = cv2.resize(frame, (640, 480))
   ```

3. **Skip Frames** (process every Nth frame)
   ```python
   if frame_count % 2 == 0:  # Process every 2nd frame
       # process frame
   ```

4. **Reduce Detection Frequency** (run detection every N frames)
   ```python
   if frame_count % 3 == 0:  # Detect every 3rd frame
       detections = detect(frame)
   ```

## Example Usage

### Backend (Python)

```python
# Already implemented in main.py
@sock.route('/ws/stream_video')
def stream_video_websocket(ws):
    # Handles camera activation and frame streaming
```

### Frontend (JavaScript)

```javascript
// Connect to stream
const ws = new WebSocket('ws://localhost:3000/ws/stream_video');
ws.binaryType = 'arraybuffer';

// Start streaming
ws.send(JSON.stringify({ command: 'start' }));

// Handle frames
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    // Binary frame
    displayFrame(event.data);
  } else {
    // JSON metadata
    const meta = JSON.parse(event.data);
    updateDetections(meta.detections);
  }
};
```

## Testing

Use the test client at: `http://localhost:3000/ws_test_video.html`

Features:
- Connect/disconnect controls
- Start/stop streaming
- Real-time frame display
- Detection visualization
- FPS counter
- Detection list

## Technical Notes

- **Camera Format:** BGR (OpenCV standard)
- **Display Format:** RGB (browser standard, automatic conversion)
- **Frame Order:** Metadata always sent before binary frame
- **Threading:** Frame processing runs in separate thread
- **Memory:** Frames are processed and immediately released
- **Compression:** JPEG provides good balance of quality and size

## References

- [OpenCV JPEG Encoding](https://docs.opencv.org/4.x/d4/da8/group__imgcodecs.html)
- [WebSocket Binary Messages](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/binaryType)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [JPEG Compression](https://en.wikipedia.org/wiki/JPEG)

