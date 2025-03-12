"""
Celery tasks for the live scrobbler service.
"""
import logging
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab

from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, SCROBBLE_INTERVAL
from .database import (
    get_connection, release_connection, get_active_users, get_user,
    get_user_credentials, update_user_credentials,
    get_or_create_artist, get_or_create_album, get_or_create_track,
    insert_listening_history
)
from .spotify_client import SpotifyClient

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Celery app
app = Celery(
    "live_scrobbler",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_max_tasks_per_child=1000,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
)

# Configure periodic tasks
app.conf.beat_schedule = {
    "schedule-scrobble-tasks": {
        "task": "src.tasks.schedule_scrobble_tasks",
        "schedule": timedelta(seconds=SCROBBLE_INTERVAL),
    },
}

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def schedule_scrobble_tasks(self):
    """
    Schedule scrobble tasks for all active users.
    This task runs periodically and creates individual tasks for each user.
    """
    logger.info("Scheduling scrobble tasks for active users")
    conn = None
    try:
        conn = get_connection()
        active_users = get_active_users(conn)
        
        for user_id, username in active_users:
            logger.info(f"Scheduling scrobble task for user {user_id} ({username})")
            scrobble_user_recently_played.delay(user_id)
            
        return f"Scheduled scrobble tasks for {len(active_users)} users"
    except Exception as e:
        logger.error(f"Error scheduling scrobble tasks: {e}")
        raise self.retry(exc=e)
    finally:
        if conn:
            release_connection(conn)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def scrobble_user_recently_played(self, user_id):
    """
    Fetch and store recently played tracks for a user.
    
    Args:
        user_id: User ID
    """
    logger.info(f"Scrobbling recently played tracks for user {user_id}")
    conn = None
    try:
        conn = get_connection()
        
        # Get user info
        user = get_user(conn, user_id)
        if not user:
            logger.warning(f"User {user_id} not found")
            return f"User {user_id} not found"
        
        # Get user credentials
        credentials = get_user_credentials(conn, user_id)
        if not credentials:
            logger.warning(f"No credentials found for user {user_id}")
            return f"No credentials found for user {user_id}"
        
        access_token = credentials["access_token"]
        refresh_token = credentials["refresh_token"]
        token_expiry = credentials["token_expiry"]
        
        # Check if token is expired and refresh if needed
        if token_expiry and datetime.now() >= token_expiry:
            logger.info(f"Refreshing access token for user {user_id}")
            spotify = SpotifyClient(access_token, refresh_token)
            token_info = spotify.refresh_access_token(refresh_token)
            
            access_token = token_info["access_token"]
            refresh_token = token_info.get("refresh_token", refresh_token)
            token_expiry = datetime.fromtimestamp(token_info["expires_at"])
            
            # Update credentials in database
            update_user_credentials(conn, user_id, access_token, refresh_token, token_expiry)
        
        # Initialize Spotify client with user credentials
        spotify = SpotifyClient(access_token, refresh_token)
        
        # Fetch recently played tracks
        recently_played = spotify.get_recently_played(limit=50)
        
        # Process and store tracks
        inserted_count = 0
        for item in recently_played:
            track_info = spotify.format_track_info(item)
            if not track_info:
                continue
            
            # Extract track details
            played_at = track_info["played_at"]
            track_name = track_info["track_name"]
            album_name = track_info["album_name"]
            artist_name = track_info["artist_name"]
            ms_played = track_info["ms_played"]
            platform = track_info["platform"]
            country = track_info["country"]
            reason_start = track_info["reason_start"]
            reason_end = track_info["reason_end"]
            shuffle = track_info["shuffle"]
            skipped = track_info["skipped"]
            moods = track_info["moods"]
            album_image_url = track_info.get("album_image_url")
            popularity = track_info.get("popularity")
            
            # Get artist image URL if not available from track info
            artist_image_url = spotify.get_artist_image_url(artist_name)
            
            # Insert normalized metadata into artists, albums, tracks
            artist_id = get_or_create_artist(conn, artist_name, artist_image_url)
            album_id = get_or_create_album(conn, album_name, artist_id, album_image_url)
            track_id = get_or_create_track(conn, track_name, album_id, popularity, album_image_url)
            
            # Insert into listening_history
            inserted = insert_listening_history(
                conn, user_id, played_at, track_id, ms_played, platform,
                country, reason_start, reason_end, shuffle, skipped, moods
            )
            
            if inserted:
                inserted_count += 1
        
        logger.info(f"Inserted {inserted_count} new scrobbles for user {user_id}")
        return f"Inserted {inserted_count} new scrobbles for user {user_id}"
    except Exception as e:
        logger.error(f"Error scrobbling recently played tracks for user {user_id}: {e}")
        raise self.retry(exc=e)
    finally:
        if conn:
            release_connection(conn)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_auth_callback(self, code, user_id, redirect_uri=None):
    """
    Process an OAuth callback and store user credentials.
    
    Args:
        code: Authorization code from the OAuth callback
        user_id: User ID from your application
        redirect_uri: Optional redirect URI override
    """
    logger.info(f"Processing OAuth callback for user {user_id}")
    conn = None
    try:
        # Initialize Spotify client
        spotify = SpotifyClient()
        if redirect_uri:
            spotify.auth_manager.redirect_uri = redirect_uri
        
        # Exchange code for tokens
        token_info = spotify.get_tokens(code)
        access_token = token_info["access_token"]
        refresh_token = token_info["refresh_token"]
        token_expiry = datetime.fromtimestamp(token_info["expires_at"])
        
        # Get user profile to verify
        spotify = SpotifyClient(access_token, refresh_token)
        user_profile = spotify.get_user_profile()
        
        # Store user credentials
        conn = get_connection()
        
        # Check if user exists
        user = get_user(conn, user_id)
        if not user:
            logger.error(f"User {user_id} not found in database")
            return {"error": f"User {user_id} not found in database"}
        
        # Store credentials
        update_user_credentials(conn, user_id, access_token, refresh_token, token_expiry)
        
        logger.info(f"Successfully processed OAuth callback for user {user_id}")
        return {"user_id": user_id, "spotify_id": user_profile["id"]}
    except Exception as e:
        logger.error(f"Error processing OAuth callback: {e}")
        raise self.retry(exc=e)
    finally:
        if conn:
            release_connection(conn)

# Import at the end to avoid circular imports
from .database import get_or_create_user 