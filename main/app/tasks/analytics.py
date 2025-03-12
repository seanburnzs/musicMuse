from celery_config import celery_app
import os
import psycopg2
import logging
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME", "musicmuse_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432)
}

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    return psycopg2.connect(**DB_PARAMS)

@celery_app.task(name="tasks.analytics.generate_user_summary")
def generate_user_summary(user_id):
    """
    Generate a summary of listening statistics for a user.
    Stores results in Redis cache for quick access.
    
    Args:
        user_id: The user ID to generate summary for
    """
    try:
        # Connect to the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Calculate total stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_streams,
                SUM(ms_played)/3600000.0 as total_hours,
                COUNT(DISTINCT track_id) as unique_tracks,
                COUNT(DISTINCT albums.album_id) as unique_albums,
                COUNT(DISTINCT artists.artist_id) as unique_artists
            FROM listening_history
            JOIN tracks ON listening_history.track_id = tracks.track_id
            JOIN albums ON tracks.album_id = albums.album_id
            JOIN artists ON albums.artist_id = artists.artist_id
            WHERE user_id = %s
        """, (user_id,))
        
        result = cur.fetchone()
        
        if not result:
            return {"error": "No data found for user"}
        
        total_streams, total_hours, unique_tracks, unique_albums, unique_artists = result
        
        # Get top 5 artists
        cur.execute("""
            SELECT artists.artist_name, COUNT(*) as stream_count
            FROM listening_history
            JOIN tracks ON listening_history.track_id = tracks.track_id
            JOIN albums ON tracks.album_id = albums.album_id
            JOIN artists ON albums.artist_id = artists.artist_id
            WHERE user_id = %s
            GROUP BY artists.artist_name
            ORDER BY stream_count DESC
            LIMIT 5
        """, (user_id,))
        
        top_artists = [{"name": name, "streams": count} for name, count in cur.fetchall()]
        
        # Get top 5 tracks
        cur.execute("""
            SELECT tracks.track_name, artists.artist_name, COUNT(*) as stream_count
            FROM listening_history
            JOIN tracks ON listening_history.track_id = tracks.track_id
            JOIN albums ON tracks.album_id = albums.album_id
            JOIN artists ON albums.artist_id = artists.artist_id
            WHERE user_id = %s
            GROUP BY tracks.track_name, artists.artist_name
            ORDER BY stream_count DESC
            LIMIT 5
        """, (user_id,))
        
        top_tracks = [
            {"name": track, "artist": artist, "streams": count} 
            for track, artist, count in cur.fetchall()
        ]
        
        # Calculate listening by hour of day
        cur.execute("""
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour, 
                COUNT(*) as count
            FROM listening_history
            WHERE user_id = %s
            GROUP BY hour
            ORDER BY hour
        """, (user_id,))
        
        listening_by_hour = [
            {"hour": int(hour), "count": count} 
            for hour, count in cur.fetchall()
        ]
        
        # Calculate listening by day of week
        cur.execute("""
            SELECT 
                EXTRACT(DOW FROM timestamp) as day, 
                COUNT(*) as count
            FROM listening_history
            WHERE user_id = %s
            GROUP BY day
            ORDER BY day
        """, (user_id,))
        
        listening_by_day = [
            {"day": int(day), "count": count} 
            for day, count in cur.fetchall()
        ]
        
        # Close database connection
        cur.close()
        conn.close()
        
        # Create summary object
        summary = {
            "user_id": user_id,
            "total_streams": total_streams,
            "total_hours": round(total_hours, 2),
            "unique_tracks": unique_tracks,
            "unique_albums": unique_albums,
            "unique_artists": unique_artists,
            "top_artists": top_artists,
            "top_tracks": top_tracks,
            "listening_by_hour": listening_by_hour,
            "listening_by_day": listening_by_day,
            "generated_at": datetime.now().isoformat()
        }
        
        # Store in Redis cache
        from app import redis_client
        redis_client.set(
            f"user_summary:{user_id}",
            json.dumps(summary),
            ex=86400  # Cache for 24 hours
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating user summary for user {user_id}: {str(e)}")
        raise