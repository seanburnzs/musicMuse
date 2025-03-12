"""
Database module for the live scrobbler service.
"""
import logging
import psycopg2
from psycopg2 import pool
from datetime import datetime

from config import DB_CONFIG

# Configure logging
logger = logging.getLogger(__name__)

# Create a connection pool
connection_pool = None

def init_db_pool(min_connections=1, max_connections=10):
    """Initialize the database connection pool."""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            **DB_CONFIG
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        raise

def get_connection():
    """Get a connection from the pool."""
    if connection_pool is None:
        init_db_pool()
    return connection_pool.getconn()

def release_connection(conn):
    """Release a connection back to the pool."""
    if connection_pool is not None:
        connection_pool.putconn(conn)

def get_user(conn, user_id):
    """
    Get a user from the database.
    
    Args:
        conn: Database connection
        user_id: User ID
        
    Returns:
        dict: User information or None if not found
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, username, email, profile_image_url
            FROM users
            WHERE user_id = %s;
            """,
            (user_id,)
        )
        result = cur.fetchone()
        
        if result:
            return {
                "user_id": result[0],
                "username": result[1],
                "email": result[2],
                "profile_image_url": result[3]
            }
        return None
    finally:
        cur.close()

def get_or_create_artist(conn, artist_name, image_url=None):
    """Ensure an artist exists in the artists table and return its ID."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT artist_id FROM artists WHERE artist_name = %s;", (artist_name,))
        result = cur.fetchone()
        
        if result:
            # Update image_url if provided and different from current
            if image_url:
                cur.execute(
                    "UPDATE artists SET image_url = %s WHERE artist_id = %s AND (image_url IS NULL OR image_url != %s);",
                    (image_url, result[0], image_url)
                )
                conn.commit()
            return result[0]
        else:
            cur.execute(
                "INSERT INTO artists (artist_name, image_url) VALUES (%s, %s) RETURNING artist_id;",
                (artist_name, image_url)
            )
            artist_id = cur.fetchone()[0]
            conn.commit()
            return artist_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in get_or_create_artist: {e}")
        raise
    finally:
        cur.close()

def get_or_create_album(conn, album_name, artist_id, image_url=None):
    """Ensure an album exists in the albums table and return its ID."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT album_id FROM albums WHERE album_name = %s AND artist_id = %s;",
            (album_name, artist_id)
        )
        result = cur.fetchone()
        
        if result:
            # Update image_url if provided and different from current
            if image_url:
                cur.execute(
                    "UPDATE albums SET image_url = %s WHERE album_id = %s AND (image_url IS NULL OR image_url != %s);",
                    (image_url, result[0], image_url)
                )
                conn.commit()
            return result[0]
        else:
            cur.execute(
                "INSERT INTO albums (album_name, artist_id, image_url) VALUES (%s, %s, %s) RETURNING album_id;",
                (album_name, artist_id, image_url)
            )
            album_id = cur.fetchone()[0]
            conn.commit()
            return album_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in get_or_create_album: {e}")
        raise
    finally:
        cur.close()

def get_or_create_track(conn, track_name, album_id, popularity=None, image_url=None):
    """Ensure a track exists in the tracks table and return its ID."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT track_id FROM tracks WHERE track_name = %s AND album_id = %s;",
            (track_name, album_id)
        )
        result = cur.fetchone()
        
        if result:
            # Update popularity and image_url if provided
            update_fields = []
            params = []
            
            if popularity is not None:
                update_fields.append("popularity = %s")
                params.append(popularity)
            
            if image_url:
                update_fields.append("image_url = %s")
                params.append(image_url)
            
            if update_fields:
                params.append(result[0])
                cur.execute(
                    f"UPDATE tracks SET {', '.join(update_fields)} WHERE track_id = %s;",
                    params
                )
                conn.commit()
            
            return result[0]
        else:
            cur.execute(
                "INSERT INTO tracks (track_name, album_id, popularity, image_url) VALUES (%s, %s, %s, %s) RETURNING track_id;",
                (track_name, album_id, popularity, image_url)
            )
            track_id = cur.fetchone()[0]
            conn.commit()
            return track_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in get_or_create_track: {e}")
        raise
    finally:
        cur.close()

def record_exists(conn, user_id, played_at, track_id):
    """
    Check if a listening_history record already exists.
    Uniqueness is based on the user_id, played_at timestamp, and track_id.
    """
    cur = conn.cursor()
    try:
        query = """
            SELECT 1 FROM listening_history 
            WHERE user_id = %s AND timestamp = %s AND track_id = %s
            LIMIT 1;
        """
        cur.execute(query, (user_id, played_at, track_id))
        return cur.fetchone() is not None
    finally:
        cur.close()

def insert_listening_history(conn, user_id, played_at, track_id, ms_played, platform="Spotify",
                           country=None, reason_start="scrobble", reason_end="scrobble",
                           shuffle=False, skipped=False, moods=None):
    """
    Insert a record into the listening_history table.
    
    Args:
        conn: Database connection
        user_id: User ID
        played_at: Timestamp when the track was played
        track_id: Track ID
        ms_played: Duration played in milliseconds
        platform: Platform where the track was played
        country: Country code
        reason_start: Reason for starting playback
        reason_end: Reason for ending playback
        shuffle: Whether shuffle was enabled
        skipped: Whether the track was skipped
        moods: Mood tags
        
    Returns:
        True if inserted, False if skipped (already exists)
    """
    # Skip if record already exists
    if record_exists(conn, user_id, played_at, track_id):
        return False
    
    cur = conn.cursor()
    try:
        # Note: Using 'id' as the primary key column name based on the schema
        insert_query = """
            INSERT INTO listening_history (
                user_id, timestamp, platform, ms_played, country,
                track_id, reason_start, reason_end, shuffle,
                skipped, moods, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
        """
        cur.execute(insert_query, (
            user_id, played_at, platform, ms_played, country,
            track_id, reason_start, reason_end, shuffle,
            skipped, moods
        ))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in insert_listening_history: {e}")
        raise
    finally:
        cur.close()

def get_user_credentials(conn, user_id):
    """
    Get Spotify credentials for a user.
    
    Args:
        conn: Database connection
        user_id: User ID
        
    Returns:
        dict: User credentials including access_token, refresh_token, etc.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT access_token, refresh_token, token_expiry
            FROM user_spotify_credentials
            WHERE user_id = %s;
            """,
            (user_id,)
        )
        result = cur.fetchone()
        
        if result:
            return {
                "access_token": result[0],
                "refresh_token": result[1],
                "token_expiry": result[2]
            }
        return None
    finally:
        cur.close()

def update_user_credentials(conn, user_id, access_token, refresh_token, token_expiry):
    """
    Update Spotify credentials for a user.
    
    Args:
        conn: Database connection
        user_id: User ID
        access_token: Spotify access token
        refresh_token: Spotify refresh token
        token_expiry: Token expiry timestamp
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO user_spotify_credentials (user_id, access_token, refresh_token, token_expiry, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                token_expiry = EXCLUDED.token_expiry,
                updated_at = NOW();
            """,
            (user_id, access_token, refresh_token, token_expiry)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in update_user_credentials: {e}")
        raise
    finally:
        cur.close()

def get_active_users(conn):
    """
    Get all active users with valid credentials.
    
    Args:
        conn: Database connection
        
    Returns:
        list: List of user IDs with valid credentials
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT u.user_id, u.username
            FROM users u
            JOIN user_spotify_credentials usc ON u.user_id = usc.user_id
            WHERE usc.refresh_token IS NOT NULL;
            """
        )
        return cur.fetchall()
    finally:
        cur.close()

def close_db_pool():
    """Close the database connection pool."""
    if connection_pool is not None:
        connection_pool.closeall()
        logger.info("Database connection pool closed") 