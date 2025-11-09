# Camera Proxy Setup Guide

This guide explains how to set up the camera proxy architecture where:
- **Camera** runs on your laptop (local access)
- **Backend** runs on cloud server (with GPU for processing)
- **Frontend** is deployed (connects to cloud backend)

## Architecture

```
Camera (Laptop)
    ↓
[Camera Proxy Script] ← reads camera locally
    ↓ (WebSocket WSS)
[Cloud Backend] ← processes frames with GPU
    ↓ (WebSocket WSS)
[Deployed Frontend] ← displays video stream
```

## Setup Steps

### 1. Deploy Backend to Cloud

Deploy your backend to a cloud server with:
- GPU support (for YOLO + freshness detection)
- Public HTTPS/WSS endpoint
- All dependencies installed

### 2. Configure Frontend

Update your frontend config to point to the cloud backend:

```bash
# In your frontend deployment
VITE_API_URL=https://your-backend-domain.com
VITE_WS_URL=wss://your-backend-domain.com
```

### 3. Configure Camera Proxy

Create a configuration file from the template:

```bash
cd backend
cp template.camera_proxy_config.json camera_proxy_config.json
```

Edit `camera_proxy_config.json` with your settings:

```json
{
  "cloud_backend_url": "wss://your-backend-domain.com/ws/stream_video",
  "camera_index": null,
  "fps_target": 30,
  "jpeg_quality": 85
}
```

**Configuration Options:**
- `cloud_backend_url`: WebSocket URL to your cloud backend (required)
- `camera_index`: Camera device index (null = auto-detect)
- `fps_target`: Target frames per second (default: 30)
- `jpeg_quality`: JPEG compression quality 1-100 (default: 85)

### 4. Run Camera Proxy on Laptop

```bash
cd backend
python camera_proxy.py
```

The script will:
- Load configuration from `camera_proxy_config.json`
- Auto-detect your camera (if camera_index is null)
- Connect to cloud backend
- Send frames continuously
- Handle reconnections automatically

**Note:** The config file is gitignored, so each developer needs to create their own copy.

## How It Works

### Camera Proxy (`camera_proxy.py`)
- Reads camera using OpenCV (local access)
- Encodes frames as JPEG (base64)
- Sends frames to cloud backend via WebSocket (`/ws/stream_video`)
- Handles connection errors and retries

### Cloud Backend (`/ws/stream_video` endpoint)
- **Proxy mode**: Receives frames from camera proxy, processes them, broadcasts to frontend
- **Local mode**: Reads from local camera, processes frames, sends to frontend
- Processes frames with YOLO detection
- Runs freshness analysis
- Updates database with inventory changes
- Broadcasts processed frames to all frontend connections

### Frontend (`/ws/stream_video` endpoint)
- Connects to cloud backend
- Receives processed frames
- Displays video stream with detections

## Benefits

✅ **Lower laptop compute** - GPU processing happens on cloud  
✅ **Works with deployed frontend** - No local IP issues  
✅ **Scalable** - Multiple frontends can connect  
✅ **Reliable** - Auto-reconnection handling  

## Troubleshooting

### Proxy can't connect to backend
- Check `CLOUD_BACKEND_URL` is set correctly
- Verify backend is accessible via HTTPS/WSS
- Check firewall/network settings

### No frames received
- Verify camera is accessible (test with `cv2.VideoCapture`)
- Check proxy logs for errors
- Verify backend is processing frames

### Frontend shows no video
- Check frontend WebSocket connection
- Verify backend is broadcasting frames
- Check browser console for errors

## Configuration

### Camera Proxy

The camera proxy reads configuration from `camera_proxy_config.json` (gitignored).

**Create config file:**
```bash
cp template.camera_proxy_config.json camera_proxy_config.json
```

**Config file options:**
- `cloud_backend_url` - WebSocket URL to cloud backend (required)
- `camera_index` - Camera device index (null = auto-detect)
- `fps_target` - Target FPS (default: 30)
- `jpeg_quality` - JPEG quality 1-100 (default: 85)

**Fallback:** If config file doesn't exist, it will use:
- `CLOUD_BACKEND_URL` environment variable
- Default values

### Backend

**Set camera mode:**
```bash
# For proxy mode (receives frames from camera proxy)
export CAMERA_MODE=proxy

# For local mode (uses local camera directly)
export CAMERA_MODE=local  # default
```

**Other environment variables:**
- Standard backend environment variables
- Must support HTTPS/WSS for WebSocket connections

### Frontend
- `VITE_API_URL` - Backend API URL
- `VITE_WS_URL` - Backend WebSocket URL (optional, auto-detected from API_URL)

