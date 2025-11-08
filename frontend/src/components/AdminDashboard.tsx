import { useState, useEffect, useRef } from 'react';
import './AdminDashboard.css';
import { config } from '../config';

interface Detection {
  bbox: [number, number, number, number];
  class: string;
  confidence: number;
  freshness_score?: number | null;
}

interface FrameMeta {
  detections: Detection[];
  fps: number;
  frame_size: number;
  timestamp: string;
}

interface DetectionWithImage extends Detection {
  croppedImageUrl?: string;
  index?: number;
}

interface DetectionCardProps {
  detection: DetectionWithImage;
  side: 'left' | 'right';
  canvasRef: React.RefObject<HTMLCanvasElement>;
  panelRef: React.RefObject<HTMLDivElement>;
}

const DetectionCard = ({ detection }: DetectionCardProps) => {
  if (!detection.croppedImageUrl) return null;

  return (
    <div className={`detection-card ${detection.index !== undefined && detection.index % 2 === 0 ? 'left' : 'right'}`} data-detection-index={detection.index}>
      <div className="detection-image-wrapper">
        <img 
          src={detection.croppedImageUrl} 
          alt={detection.class}
          className="detection-image"
        />
        <div className="detection-overlay">
          <div className="detection-label">{detection.class}</div>
          <div className="detection-confidence">
            {(detection.confidence * 100).toFixed(1)}%
          </div>
          {detection.freshness_score !== null && detection.freshness_score !== undefined && (
            <div className="detection-fresh">
              Fresh: {detection.freshness_score.toFixed(1)}%
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

interface ArrowProps {
  detection: DetectionWithImage;
  side: 'left' | 'right';
  canvasRef: React.RefObject<HTMLCanvasElement>;
  panelRef: React.RefObject<HTMLDivElement>;
  containerRef: React.RefObject<HTMLDivElement>;
}

const Arrow = ({ detection, side, canvasRef, panelRef, containerRef }: ArrowProps) => {
  const [path, setPath] = useState<string>('');
  const [arrowHead, setArrowHead] = useState<{ x: number; y: number; angle: number } | null>(null);

  useEffect(() => {
    const updateArrow = () => {
      const canvas = canvasRef.current;
      const panel = panelRef.current;
      const container = containerRef.current;
      
      if (!canvas || !panel || !container) return;

      const canvasRect = canvas.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      const [x1, y1, x2, y2] = detection.bbox;
      const bboxCenterY = (y1 + y2) / 2;

      // Scale bbox coordinates to canvas display size
      const scaleX = canvasRect.width / canvas.width;
      const scaleY = canvasRect.height / canvas.height;
      
      // Point arrow to left edge for left panel, right edge for right panel
      const bboxEdgeX = side === 'left' ? x1 : x2;
      const bboxScreenX = bboxEdgeX * scaleX + canvasRect.left - containerRect.left;
      const bboxScreenY = bboxCenterY * scaleY + canvasRect.top - containerRect.top;

      // Find the detection card position
      const detectionCard = panel.querySelector(`[data-detection-index="${detection.index}"]`);
      if (!detectionCard) return;

      const cardRect = detectionCard.getBoundingClientRect();
      const cardCenterY = cardRect.top + cardRect.height / 2 - containerRect.top;

      // Calculate arrow path
      const startX = side === 'left' ? cardRect.right - containerRect.left : cardRect.left - containerRect.left;
      const startY = cardCenterY;
      const endX = bboxScreenX;
      const endY = bboxScreenY;

      // Control points for curved arrow
      const controlX1 = startX + (endX - startX) * 0.3;
      const controlY1 = startY;
      const controlX2 = endX - (endX - startX) * 0.3;
      const controlY2 = endY;

      const pathStr = `M ${startX} ${startY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${endX} ${endY}`;
      setPath(pathStr);

      // Arrow head angle
      const angle = Math.atan2(endY - controlY2, endX - controlX2);
      setArrowHead({ x: endX, y: endY, angle });
    };

    updateArrow();
    const interval = setInterval(updateArrow, 100); // Update frequently for smooth arrows
    window.addEventListener('resize', updateArrow);
    return () => {
      clearInterval(interval);
      window.removeEventListener('resize', updateArrow);
    };
  }, [detection, side, canvasRef, panelRef, containerRef]);

  if (!path || !arrowHead) return null;

  const arrowLength = 10;
  const arrowWidth = 6;

  return (
    <g className="arrow-group">
      <path
        d={path}
        stroke="#7ECA9C"
        strokeWidth="2"
        fill="none"
        strokeDasharray="5,5"
        opacity="0.6"
      />
      <path
        d={`M ${arrowHead.x} ${arrowHead.y} L ${arrowHead.x - arrowLength * Math.cos(arrowHead.angle) + arrowWidth * Math.sin(arrowHead.angle)} ${arrowHead.y - arrowLength * Math.sin(arrowHead.angle) - arrowWidth * Math.cos(arrowHead.angle)}`}
        stroke="#7ECA9C"
        strokeWidth="2"
        fill="none"
      />
      <path
        d={`M ${arrowHead.x} ${arrowHead.y} L ${arrowHead.x - arrowLength * Math.cos(arrowHead.angle) - arrowWidth * Math.sin(arrowHead.angle)} ${arrowHead.y - arrowLength * Math.sin(arrowHead.angle) + arrowWidth * Math.cos(arrowHead.angle)}`}
        stroke="#7ECA9C"
        strokeWidth="2"
        fill="none"
      />
    </g>
  );
};

const AdminDashboard = () => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [fps, setFps] = useState(0);
  const [detectionCount, setDetectionCount] = useState(0);
  const [detections, setDetections] = useState<DetectionWithImage[]>([]);
  const [classCounts, setClassCounts] = useState<Record<string, number>>({});
  const [freshModelLoaded, setFreshModelLoaded] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pendingFrameMetaRef = useRef<FrameMeta | null>(null);
  const autoStartedRef = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryTimeoutRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const videoContainerRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<HTMLDivElement>(null);
  const rightPanelRef = useRef<HTMLDivElement>(null);

  const handleTextMessage = (data: any) => {
    if (data.type === 'connected') {
      setFreshModelLoaded(data.fresh_model_loaded || false);
      setConnectionError(null); // Clear any previous errors on successful connection
    } else if (data.type === 'started') {
      setIsStreaming(true);
      setConnectionError(null); // Clear errors when stream starts
    } else if (data.type === 'stopped') {
      setIsStreaming(false);
    } else if (data.type === 'frame_meta') {
      pendingFrameMetaRef.current = data;
    } else if (data.type === 'error') {
      // Handle backend errors (like camera issues)
      const errorMsg = data.message || 'Unknown error';
      if (errorMsg.includes('I/O operation on closed file') || errorMsg.includes('camera') || errorMsg.includes('Failed to')) {
        setConnectionError(`Camera error: ${errorMsg}. Make sure a camera is connected and available.`);
      } else {
        setConnectionError(`Backend error: ${errorMsg}`);
      }
    }
  };

  const displayFrame = (imageUrl: string, detections: Detection[]) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;

      ctx.drawImage(img, 0, 0);

      // Create a temporary canvas for cropping
      const tempCanvas = document.createElement('canvas');
      const tempCtx = tempCanvas.getContext('2d');
      if (!tempCtx) return;

      // Process detections and create cropped images
      const detectionsWithImages: DetectionWithImage[] = detections.map((detection, index) => {
        const [x1, y1, x2, y2] = detection.bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        // Crop the detection from the original image
        tempCanvas.width = width;
        tempCanvas.height = height;
        tempCtx.drawImage(img, x1, y1, width, height, 0, 0, width, height);
        
        // Convert cropped canvas to blob URL
        const croppedImageUrl = tempCanvas.toDataURL('image/jpeg', 0.9);

        // Draw bounding box in white
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.strokeRect(x1, y1, width, height);
        
        // Add corner markers for sci-fi look
        const cornerSize = 8;
        ctx.beginPath();
        // Top-left
        ctx.moveTo(x1, y1 + cornerSize);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x1 + cornerSize, y1);
        // Top-right
        ctx.moveTo(x2 - cornerSize, y1);
        ctx.lineTo(x2, y1);
        ctx.lineTo(x2, y1 + cornerSize);
        // Bottom-right
        ctx.moveTo(x2, y2 - cornerSize);
        ctx.lineTo(x2, y2);
        ctx.lineTo(x2 - cornerSize, y2);
        // Bottom-left
        ctx.moveTo(x1 + cornerSize, y2);
        ctx.lineTo(x1, y2);
        ctx.lineTo(x1, y2 - cornerSize);
        ctx.stroke();
        
        // Draw class label on top left of bbox
        ctx.font = '14px "Geist Mono", monospace';
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(detection.class, x1 + 4, y1 - 6);

        return {
          ...detection,
          croppedImageUrl,
          index
        };
      });

      // Update detections with cropped images
      setDetections(detectionsWithImages);
      
      // Calculate class counts
      const counts: Record<string, number> = {};
      detections.forEach(detection => {
        counts[detection.class] = (counts[detection.class] || 0) + 1;
      });
      setClassCounts(counts);
    };
    img.src = imageUrl;
  };

  const handleBinaryFrame = (arrayBuffer: ArrayBuffer) => {
    const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
    const imageUrl = URL.createObjectURL(blob);

    const meta = pendingFrameMetaRef.current;
    if (meta) {
      displayFrame(imageUrl, meta.detections);
      setDetectionCount(meta.detections.length);
      setFps(meta.fps);
      pendingFrameMetaRef.current = null;
    } else {
      displayFrame(imageUrl, []);
      setDetections([]);
      setClassCounts({});
    }

    setTimeout(() => URL.revokeObjectURL(imageUrl), 100);
  };

  const connectWebSocketWithRetry = () => {
    // Clear any existing retry timeout
    if (retryTimeoutRef.current !== null) {
      window.clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }

    try {
      const websocket = new WebSocket(`${config.wsUrl}/ws/stream_video`);
      websocket.binaryType = 'arraybuffer';
      wsRef.current = websocket;

      websocket.onopen = () => {
        setIsConnected(true);
        setWs(websocket);
        setConnectionError(null);
        retryCountRef.current = 0;
        setRetryCount(0);
      };

      websocket.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          handleBinaryFrame(event.data);
        } else {
          try {
            const data = JSON.parse(event.data);
            handleTextMessage(data);
          } catch (e) {
            console.error('Failed to parse JSON:', e);
          }
        }
      };

      websocket.onclose = (event) => {
        setIsConnected(false);
        setIsStreaming(false);
        setWs(null);
        autoStartedRef.current = false;
        wsRef.current = null;

        // Only retry if it wasn't a manual close (code 1000) and we haven't exceeded retry limit
        const currentRetryCount = retryCountRef.current;
        const isNormalClose = event.code === 1000;
        const isAbnormalClose = event.code === 1006 || event.code === 1001 || event.code === 1002;
        
        if (!isNormalClose && currentRetryCount < 5) {
          retryCountRef.current = currentRetryCount + 1;
          setRetryCount(retryCountRef.current);
          
          if (isAbnormalClose) {
            setConnectionError(`Connection lost. Retrying... (${retryCountRef.current}/5)`);
          } else {
            setConnectionError(`Connection closed (code: ${event.code}). Retrying... (${retryCountRef.current}/5)`);
          }
          
          retryTimeoutRef.current = window.setTimeout(() => {
            connectWebSocketWithRetry();
          }, 2000 * retryCountRef.current); // Exponential backoff
        } else if (!isNormalClose && currentRetryCount >= 5) {
          setConnectionError('Failed to connect after 5 attempts. Please check if the backend server is running on port 3000.');
        } else if (isNormalClose) {
          // Normal close, clear error
          setConnectionError(null);
        }
      };

      websocket.onerror = () => {
        // Only log if we're not already handling a close event
        // The error event often fires before onclose, so we'll handle it there
        if (websocket.readyState === WebSocket.CONNECTING) {
          setConnectionError('Connection error. Make sure the backend server is running on port 3000.');
        }
      };

      setWs(websocket);
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionError('Failed to create WebSocket connection.');
      
      // Retry after delay
      const currentRetryCount = retryCountRef.current;
      if (currentRetryCount < 5) {
        retryCountRef.current = currentRetryCount + 1;
        setRetryCount(retryCountRef.current);
        retryTimeoutRef.current = window.setTimeout(() => {
          connectWebSocketWithRetry();
        }, 2000 * retryCountRef.current);
      }
    }
  };

  // Auto-connect and auto-start stream on mount
  useEffect(() => {
    connectWebSocketWithRetry();
    
    return () => {
      if (retryTimeoutRef.current !== null) {
        window.clearTimeout(retryTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000); // Normal closure
      }
    };
  }, []);

  // Auto-start stream once connected
  useEffect(() => {
    if (isConnected && !autoStartedRef.current && ws) {
      autoStartedRef.current = true;
      // Small delay to ensure connection is fully established
      setTimeout(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ command: 'start' }));
        }
      }, 500);
    }
  }, [isConnected, ws]);

  const connectWebSocket = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return; // Already connected
    }
    retryCountRef.current = 0;
    setRetryCount(0);
    setConnectionError(null);
    connectWebSocketWithRetry();
  };

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard-header">
        <h1 className="admin-dashboard-title">ADMIN DASHBOARD</h1>
        <div className="top-stats">
          <div className="stat-card">
            <div className="stat-label">FPS</div>
            <div className="stat-value">{fps.toFixed(1)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">DETECTIONS</div>
            <div className="stat-value">{detectionCount}</div>
          </div>
        </div>
        <div className="status-indicators">
          <button 
            className="control-btn view-inventory-btn" 
            onClick={() => { window.location.hash = '#admin-inventory'; }}
            style={{ marginRight: '1rem' }}
          >
            VIEW INVENTORY
          </button>
          <span className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
          <span className={`status-badge ${isStreaming ? 'streaming' : 'idle'}`}>
            {isStreaming ? 'STREAMING' : 'IDLE'}
          </span>
          {freshModelLoaded && (
            <span className="status-badge model-loaded">MODEL LOADED</span>
          )}
        </div>
      </div>

      {connectionError && (
        <div className="connection-error">
          <span className="error-icon">⚠️</span>
          <span className="error-message">{connectionError}</span>
          {retryCount < 5 && (
            <button className="retry-btn" onClick={connectWebSocket}>
              RETRY NOW
            </button>
          )}
        </div>
      )}

      <div className="video-wrapper">
        <div className="detection-panel left-panel" ref={leftPanelRef}>
          {detections.filter((_, idx) => idx % 2 === 0).map((detection) => (
            <DetectionCard 
              key={detection.index} 
              detection={detection} 
              side="left"
              canvasRef={canvasRef}
              panelRef={leftPanelRef}
            />
          ))}
        </div>

        <div className="middle-section">
          <div className="video-container" ref={videoContainerRef}>
            <canvas ref={canvasRef} className="video-canvas" />
            <svg className="arrow-overlay" preserveAspectRatio="none">
              {detections.map((detection) => {
                const isLeft = detection.index !== undefined && detection.index % 2 === 0;
                return (
                  <Arrow
                    key={detection.index}
                    detection={detection}
                    side={isLeft ? 'left' : 'right'}
                    canvasRef={canvasRef}
                    panelRef={isLeft ? leftPanelRef : rightPanelRef}
                    containerRef={videoContainerRef}
                  />
                );
              })}
            </svg>
          </div>

          <div className="class-counts-section">
            <h3 className="class-counts-title">DETECTED CLASSES</h3>
            <div className="class-counts-grid">
              {Object.keys(classCounts).length === 0 ? (
                <div className="class-count-item empty">No detections</div>
              ) : (
                Object.entries(classCounts)
                  .sort((a, b) => b[1] - a[1]) // Sort by count descending
                  .map(([className, count]) => (
                    <div key={className} className="class-count-item">
                      <span className="class-name">{className}</span>
                      <span className="class-count">{count}</span>
                    </div>
                  ))
              )}
            </div>
          </div>
        </div>

        <div className="detection-panel right-panel" ref={rightPanelRef}>
          {detections.filter((_, idx) => idx % 2 === 1).map((detection) => (
            <DetectionCard 
              key={detection.index} 
              detection={detection} 
              side="right"
              canvasRef={canvasRef}
              panelRef={rightPanelRef}
            />
          ))}
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;

