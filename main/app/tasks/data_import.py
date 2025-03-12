from celery_config import celery_app
import os
import psycopg2
import json
import logging
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

@celery_app.task(bind=True, name="tasks.data_import.process_spotify_file")
def process_spotify_file(self, file_path, user_id):
    """
    Process a Spotify JSON file and import the data into the database.
    
    Args:
        file_path: Path to the JSON file
        user_id: User ID to associate with the imported data
    """
    logger.info(f"Processing file {file_path} for user {user_id}")
    
    try:
        # Open and read the JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Connect to the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Track progress
        total_items = len(data)
        processed_items = 0
        
        # Process each item in batches
        batch_size = 100
        batch = []
        
        for item in data:
            # Extract track details
            track_name = item.get("trackName", "Unknown Track")
            artist_name = item.get("artistName", "Unknown Artist")
            album_name = item.get("albumName", "Unknown Album")
            ms_played = item.get("msPlayed", 0)
            timestamp_str = item.get("endTime")
            
            # Skip tracks with very short play duration (likely skipped)
            if ms_played < 30000:  # Less than 30 seconds
                continue
                
            # Process timestamp
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M")
            except:
                # Try alternative format
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
                except:
                    # Skip if timestamp can't be parsed
                    continue
            
            # Add to batch
            batch.append((
                track_name, artist_name, album_name, 
                ms_played, timestamp, user_id
            ))
            
            processed_items += 1
            
            # Process batch if it reaches the batch size
            if len(batch) >= batch_size:
                self._process_batch(cur, batch)
                batch = []
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={'current': processed_items, 'total': total_items}
                )
        
        # Process any remaining items
        if batch:
            self._process_batch(cur, batch)
        
        # Commit the transaction
        conn.commit()
        
        # Close database connection
        cur.close()
        conn.close()
        
        # Return success result
        return {
            'status': 'success',
            'processed_items': processed_items,
            'total_items': total_items
        }
    
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {str(e)}")
        # If an error occurs, close the database connection
        if 'conn' in locals() and conn:
            conn.rollback()
            cur.close()
            conn.close()
        
        # Re-raise the exception to mark the task as failed
        raise
    
    def _process_batch(self, cur, batch):
        """Process a batch of items."""
        for track_name, artist_name, album_name, ms_played, timestamp, user_id in batch:
            # Get or create artist
            cur.execute(
                "SELECT artist_id FROM artists WHERE artist_name = %s",
                (artist_name,)
            )
            result = cur.fetchone()
            if result:
                artist_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO artists (artist_name) VALUES (%s) RETURNING artist_id",
                    (artist_name,)
                )
                artist_id = cur.fetchone()[0]
            
            # Get or create album
            cur.execute(
                "SELECT album_id FROM albums WHERE album_name = %s AND artist_id = %s",
                (album_name, artist_id)
            )
            result = cur.fetchone()
            if result:
                album_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO albums (album_name, artist_id) VALUES (%s, %s) RETURNING album_id",
                    (album_name, artist_id)
                )
                album_id = cur.fetchone()[0]
            
            # Get or create track
            cur.execute(
                "SELECT track_id FROM tracks WHERE track_name = %s AND album_id = %s",
                (track_name, album_id)
            )
            result = cur.fetchone()
            if result:
                track_id = result[0]
            else:
                cur.execute(
                    "INSERT INTO tracks (track_name, album_id) VALUES (%s, %s) RETURNING track_id",
                    (track_name, album_id)
                )
                track_id = cur.fetchone()[0]
            
            # Insert into listening_history
            cur.execute(
                """
                INSERT INTO listening_history (
                    timestamp, ms_played, track_id, user_id, platform
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (timestamp, ms_played, track_id, user_id, "Spotify")
            )

@celery_app.task(name="tasks.data_import.cleanup_temp_files")
def cleanup_temp_files(file_paths):
    """Clean up temporary files after processing."""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temporary file: {file_path}")
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {str(e)}")