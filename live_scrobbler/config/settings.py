"""
Configuration settings for the live scrobbler service.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Spotify API settings
SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SPOTIFY_SCOPE = "user-read-recently-played"

# Database settings
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "musicmuse_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

# Redis and Celery settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

# Application settings
SCROBBLE_INTERVAL = int(os.getenv("SCROBBLE_INTERVAL", 3600))  # Default: 60 minutes
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SECRET_KEY = os.getenv("SECRET_KEY", "dev_key")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Validate required settings
def validate_settings():
    """Validate that all required settings are present."""
    required_settings = [
        ("SPOTIFY_CLIENT_ID", SPOTIFY_CLIENT_ID),
        ("SPOTIFY_CLIENT_SECRET", SPOTIFY_CLIENT_SECRET),
        ("SPOTIFY_REDIRECT_URI", SPOTIFY_REDIRECT_URI),
        ("DB_CONFIG['password']", DB_CONFIG["password"]),
    ]
    
    missing_settings = [name for name, value in required_settings if not value]
    
    if missing_settings:
        raise ValueError(
            f"Missing required settings: {', '.join(missing_settings)}. "
            "Please check your .env file."
        ) 