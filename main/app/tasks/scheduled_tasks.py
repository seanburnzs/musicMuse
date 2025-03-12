from celery_config import celery_app
import os
import psycopg2
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

@celery_app.task(name="tasks.scheduled_tasks.refresh_analytics_views")
def refresh_analytics_views():
    """Refresh all analytics materialized views."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database to refresh analytics views...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Call the refresh function
        cursor.execute("SELECT refresh_analytics_views();")
        
        # Commit the transaction
        conn.commit()
        logger.info("Analytics views refreshed successfully.")
        
    except Exception as e:
        logger.error(f"Error refreshing analytics views: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logger.info("Database connection closed.")

@celery_app.task(name="tasks.scheduled_tasks.clean_old_sessions")
def clean_old_sessions():
    """Clean old session data."""
    from app import redis_client
    
    try:
        # Delete session keys older than 30 days
        session_keys = redis_client.keys("session:*")
        expired_count = 0
        
        for key in session_keys:
            # Check if the key has an expiration time set
            ttl = redis_client.ttl(key)
            
            # If TTL is less than 0, it means no expiration is set
            # or the key doesn't exist (which shouldn't happen in this loop)
            if ttl < 0:
                redis_client.expire(key, 30 * 24 * 60 * 60)  # 30 days
                expired_count += 1
                
        logger.info(f"Set expiration on {expired_count} session keys.")
        
    except Exception as e:
        logger.error(f"Error cleaning old sessions: {str(e)}")