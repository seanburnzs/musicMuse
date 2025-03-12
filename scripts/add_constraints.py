import psycopg2
import os
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_migration")

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

def add_constraints():
    """Add constraints to ensure data integrity."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # List of constraints to add
        constraints = [
            # Value constraints
            ("listening_history_ms_played_check", "listening_history", "CHECK (ms_played >= 0)"),
            ("tracks_popularity_check", "tracks", "CHECK (popularity >= 0 AND popularity <= 100)"),
            
            # Privacy setting constraints
            ("user_settings_privacy_check", "user_settings", 
             "CHECK (impersonation_privacy IN ('everyone', 'friends', 'private'))"),
            ("user_settings_events_privacy_check", "user_settings", 
             "CHECK (events_privacy IN ('everyone', 'friends', 'private'))"),
            
            # Hall of fame position constraint
            ("user_hall_of_fame_position_check", "user_hall_of_fame", 
             "CHECK (position >= 1 AND position <= 3)"),
            
            # Item type constraint
            ("user_hall_of_fame_item_type_check", "user_hall_of_fame", 
             "CHECK (item_type IN ('track', 'album', 'artist'))")
        ]
        
        # Add each constraint
        for constraint_name, table, definition in constraints:
            try:
                logger.info(f"Adding constraint {constraint_name} to {table}...")
                
                # Check if constraint already exists
                cursor.execute(f"""
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = '{constraint_name}'
                """)
                
                if cursor.fetchone():
                    logger.info(f"Constraint {constraint_name} already exists.")
                    continue
                
                # Add the constraint
                cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} {definition};")
                logger.info(f"Constraint {constraint_name} added successfully.")
                
            except Exception as e:
                logger.error(f"Error adding constraint {constraint_name}: {str(e)}")
                conn.rollback()
                continue
        
        # Commit changes
        conn.commit()
        logger.info("All constraints added successfully.")
        
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
    add_constraints()