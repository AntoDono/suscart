#!/usr/bin/env python3
"""
Camera Proxy Script
Runs on laptop to read camera and forward frames to cloud backend.
This allows the cloud backend to process frames with GPU while keeping camera access local.
"""

import cv2
import websockets
import asyncio
import json
import base64
import time
import os
import sys
from datetime import datetime

# Add parent directory to path to import detect_fruits
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detect_fruits import get_best_camera_index

def load_config():
    """Load configuration from camera_proxy_config.json or use defaults"""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'camera_proxy_config.json')
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'template.camera_proxy_config.json')
    
    # Default configuration
    default_config = {
        'cloud_backend_url': os.getenv('CLOUD_BACKEND_URL', 'wss://your-backend-domain.com/ws/stream_video'),
        'camera_index': None,  # None = auto-detect
        'fps_target': 30,
        'jpeg_quality': 85
    }
    
    # Try to load from config file
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                # Merge with defaults (file config takes precedence)
                default_config.update(file_config)
                print(f"✅ Loaded configuration from {config_path}")
        except Exception as e:
            print(f"⚠️ Failed to load config file: {e}")
            print(f"   Using defaults. Check {template_path} for template.")
    else:
        # Check if template exists
        if os.path.exists(template_path):
            print(f"⚠️ Config file not found: {config_path}")
            print(f"   Copy {template_path} to {config_path} and update with your settings")
        else:
            print(f"⚠️ Config file not found: {config_path}")
            print(f"   Using environment variables or defaults")
    
    return default_config

# Load configuration
config = load_config()
CLOUD_BACKEND_URL = config['cloud_backend_url']
CAMERA_INDEX = config.get('camera_index')
FPS_TARGET = config.get('fps_target', 30)
JPEG_QUALITY = config.get('jpeg_quality', 85)

class CameraProxy:
    def __init__(self, backend_url, camera_index=None):
        self.backend_url = backend_url
        self.camera_index = camera_index
        self.camera = None
        self.ws = None
        self.running = False
        self.frame_count = 0
        self.start_time = None
        
    def connect_camera(self):
        """Initialize camera connection"""
        if self.camera_index is None:
            # Try to auto-detect camera
            try:
                self.camera_index = get_best_camera_index()
                print(f"📹 Auto-detected camera index: {self.camera_index}")
            except Exception as e:
                print(f"⚠️ Auto-detection failed: {e}")
                print("   Trying camera index 0...")
                self.camera_index = 0
        
        # Try to open camera
        self.camera = cv2.VideoCapture(self.camera_index)
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {self.camera_index}. Make sure camera is connected and not in use by another application.")
        
        # Set camera properties for better performance
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.camera.set(cv2.CAP_PROP_FPS, FPS_TARGET)
        
        # Verify camera can actually read frames
        ret, frame = self.camera.read()
        if not ret or frame is None:
            self.camera.release()
            raise RuntimeError(f"Camera {self.camera_index} opened but cannot read frames. Check camera permissions.")
        
        print(f"✅ Camera connected (index: {self.camera_index})")
        
    def release_camera(self):
        """Release camera resources"""
        if self.camera is not None:
            self.camera.release()
            self.camera = None
            print("📹 Camera released")
    
    def encode_frame(self, frame):
        """Encode frame as JPEG"""
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        _, buffer = cv2.imencode('.jpg', frame, encode_param)
        return base64.b64encode(buffer).decode('utf-8')
    
    async def connect_to_backend(self):
        """Connect to cloud backend WebSocket"""
        try:
            print(f"🔌 Connecting to backend: {self.backend_url}")
            self.ws = await websockets.connect(
                self.backend_url,
                ping_interval=20,
                ping_timeout=10
            )
            print("✅ Connected to cloud backend")
            
            # Send initialization message
            await self.ws.send(json.dumps({
                'type': 'proxy_connected',
                'message': 'Camera proxy connected',
                'timestamp': datetime.utcnow().isoformat()
            }))
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to backend: {e}")
            return False
    
    def is_ws_connected(self):
        """Check if WebSocket connection is still open"""
        if self.ws is None:
            return False
        try:
            # For websockets library, check closed property
            # If it doesn't exist, assume connection is open (will fail on send if closed)
            closed = getattr(self.ws, 'closed', None)
            if closed is None:
                # Try to check connection state differently
                return True  # Assume open, actual send will fail if closed
            return not closed
        except (AttributeError, Exception):
            # If we can't check, assume connection is open
            # The actual send will fail if it's closed
            return True
    
    async def send_frame(self, frame):
        """Send frame to backend"""
        if not self.is_ws_connected():
            return False
        
        try:
            # Encode frame as base64 JPEG
            frame_data = self.encode_frame(frame)
            
            # Send frame data
            await self.ws.send(json.dumps({
                'type': 'frame',
                'data': frame_data,
                'timestamp': datetime.utcnow().isoformat(),
                'frame_id': self.frame_count
            }))
            
            self.frame_count += 1
            return True
        except (websockets.exceptions.ConnectionClosed, AttributeError) as e:
            print(f"⚠️ WebSocket connection closed: {e}")
            self.running = False
            return False
        except Exception as e:
            print(f"❌ Error sending frame: {e}")
            return False
    
    async def handle_backend_messages(self):
        """Handle messages from backend"""
        try:
            async for message in self.ws:
                try:
                    # Check if message is binary (bytes) or text (str)
                    if isinstance(message, bytes):
                        # Backend sends binary frame data - we don't need to process it
                        # (it's meant for frontend clients, not the proxy)
                        continue
                    
                    # Try to parse as JSON (text message)
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'start':
                        print("▶️ Backend requested stream start")
                        self.running = True
                    elif msg_type == 'stop':
                        print("⏹️ Backend requested stream stop")
                        self.running = False
                    elif msg_type == 'ping':
                        # Respond to ping
                        await self.ws.send(json.dumps({'type': 'pong'}))
                    elif msg_type == 'frame_meta':
                        # Backend broadcasts frame_meta to all clients (including proxy)
                        # We can ignore this since we're just sending frames, not receiving them
                        pass
                    else:
                        print(f"📨 Received message: {msg_type}")
                except json.JSONDecodeError:
                    print(f"⚠️ Invalid JSON from backend: {message[:100]}...")
        except websockets.exceptions.ConnectionClosed:
            print("❌ Backend connection closed")
            self.running = False
        except Exception as e:
            print(f"❌ Error handling backend messages: {e}")
            self.running = False
    
    async def stream_frames(self):
        """Main loop: read camera and send frames"""
        frame_interval = 1.0 / FPS_TARGET
        last_frame_time = 0
        frames_read = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Control frame rate
                if current_time - last_frame_time < frame_interval:
                    await asyncio.sleep(0.001)  # Small sleep to prevent busy waiting
                    continue
                
                # Read frame from camera
                ret, frame = self.camera.read()
                if not ret:
                    print("⚠️ Failed to read frame from camera")
                    await asyncio.sleep(0.1)
                    continue
                
                frames_read += 1
                
                # Send frame to backend
                success = await self.send_frame(frame)
                if not success:
                    print(f"⚠️ Failed to send frame {frames_read}")
                
                last_frame_time = current_time
                
                # Print FPS every 30 frames (but only if we've sent at least 1 frame)
                if self.frame_count > 0 and self.frame_count % 30 == 0:
                    elapsed = current_time - self.start_time if self.start_time else 1
                    fps = self.frame_count / elapsed if elapsed > 0 else 0
                    print(f"📊 Sent {self.frame_count} frames ({fps:.1f} FPS) | Read {frames_read} frames from camera")
                elif frames_read == 1:
                    # Print on first frame read
                    print(f"✅ Started reading frames from camera...")
                
            except Exception as e:
                print(f"❌ Error in stream loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.1)
    
    async def run(self):
        """Main entry point"""
        try:
            # Connect camera
            self.connect_camera()
            
            # Connect to backend
            if not await self.connect_to_backend():
                return
            
            # Start message handler
            message_task = asyncio.create_task(self.handle_backend_messages())
            
            # Wait for start command
            print("⏳ Waiting for backend to start stream...")
            await asyncio.sleep(1)
            
            # Start streaming
            self.running = True
            self.start_time = time.time()
            
            # Stream frames
            await self.stream_frames()
            
            # Wait for message handler to finish
            message_task.cancel()
            try:
                await message_task
            except asyncio.CancelledError:
                pass
                
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
        except Exception as e:
            print(f"❌ Fatal error: {e}")
        finally:
            self.running = False
            self.release_camera()
            if self.ws:
                try:
                    if self.is_ws_connected():
                        await self.ws.close()
                except Exception as e:
                    print(f"⚠️ Error closing WebSocket: {e}")
            print("👋 Camera proxy stopped")

async def main():
    """Main function"""
    backend_url = CLOUD_BACKEND_URL
    
    if backend_url == 'wss://your-backend-domain.com/ws/stream_video' or 'your-backend-domain.com' in backend_url:
        print("❌ Please configure cloud_backend_url in camera_proxy_config.json")
        print("   Copy template.camera_proxy_config.json to camera_proxy_config.json and update it")
        return
    
    proxy = CameraProxy(backend_url, camera_index=CAMERA_INDEX)
    
    # Retry connection logic
    max_retries = 5
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            await proxy.run()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Connection failed, retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
            else:
                print(f"❌ Failed after {max_retries} attempts: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("📹 Camera Proxy - Forwarding frames to cloud backend")
    print("=" * 60)
    asyncio.run(main())

