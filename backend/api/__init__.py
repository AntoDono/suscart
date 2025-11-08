"""App initialization and configuration"""

from flask import Flask
from flask_cors import CORS
from flask_sock import Sock
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import models and database
from models import db
from database import init_db

# Import Knot client with fallback support
try:
    from knot_fallback import KnotClientWithFallback
    use_fallback = os.getenv('KNOT_FALLBACK_TO_TUNNEL', 'true').lower() == 'true'
    if use_fallback and os.getenv('KNOT_ENV', 'tunnel') != 'tunnel' and os.getenv('KNOT_USE_REAL', 'false').lower() == 'true':
        from knot_fallback import KnotClientWithFallback as get_knot_client_class
        def get_knot_client():
            return KnotClientWithFallback()
    else:
        from knot_integration import get_knot_client
except ImportError:
    from knot_integration import get_knot_client

# Import detection functions
from detect_fruits import (
    load_ripe_detection_model,
)


def create_app():
    """Create and configure Flask app"""
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes
    sock = Sock(app)  # Initialize WebSocket support
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///suscart.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_db(app)
    
    # Initialize Knot API client
    knot_client = get_knot_client()
    
    # Load ripe detection model globally (once at startup)
    ripe_model = None
    ripe_device = None
    ripe_transform = None
    try:
        ripe_model, ripe_device, ripe_transform = load_ripe_detection_model("./model/ripe_detector.pth")
        print("✅ Ripe detection model loaded successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not load ripe detection model: {e}")
        print("   Video stream will work but without ripe detection")
    
    # Store app-level variables
    app.knot_client = knot_client
    app.ripe_model = ripe_model
    app.ripe_device = ripe_device
    app.ripe_transform = ripe_transform
    
    return app, sock

