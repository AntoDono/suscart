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
    load_fresh_detection_model,
)


def create_app():
    """Create and configure Flask app"""
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes
    sock = Sock(app)  # Initialize WebSocket support
    
    # Database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///edgecart.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_db(app)
    
    # Initialize Knot API client
    knot_client = get_knot_client()
    
    # Load fresh detection model globally (once at startup)
    fresh_model = None
    fresh_device = None
    fresh_transform = None
    try:
        fresh_model, fresh_device, fresh_transform = load_fresh_detection_model("./model/fresh_detector.pth")
        print("✅ Fresh detection model loaded successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not load fresh detection model: {e}")
        print("   Video stream will work but without fresh detection")
    
    # Store app-level variables
    app.knot_client = knot_client
    app.fresh_model = fresh_model
    app.fresh_device = fresh_device
    app.fresh_transform = fresh_transform
    
    return app, sock

