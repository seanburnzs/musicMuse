import psycopg2
from dotenv import load_dotenv
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("migrations.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("db_migrations")

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

def create_indexes():
    """Create indexes to optimize query performance."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # List of indexes to create
        indexes = [
            # Primary tables
            ("idx_listening_history_timestamp", "listening_history", "timestamp"),
            ("idx_listening_history_user_id", "listening_history", "user_id"),
            ("idx_listening_history_track_id", "listening_history", "track_id"),
            ("idx_tracks_album_id", "tracks", "album_id"),
            ("idx_albums_artist_id", "albums", "artist_id"),
            
            # User-related tables
            ("idx_user_events_user_id", "user_events", "user_id"),
            ("idx_user_events_start_date", "user_events", "start_date"),
            ("idx_user_events_end_date", "user_events", "end_date"),
            ("idx_user_follows_follower_id", "user_follows", "follower_id"),
            ("idx_user_follows_followed_id", "user_follows", "followed_id"),
            
            # Combined indexes for frequent queries
            ("idx_listening_history_user_track", "listening_history", "user_id, track_id"),
            ("idx_listening_history_user_timestamp", "listening_history", "user_id, timestamp")
        ]
        
        # Create each index
        for index_name, table, columns in indexes:
            try:
                logger.info(f"Creating index {index_name} on {table}({columns})...")
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({columns});")
                logger.info(f"Index {index_name} created successfully.")
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {str(e)}")
                conn.rollback()
                continue
        
        # Commit changes
        conn.commit()
        logger.info("All indexes created successfully.")
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    create_indexes()