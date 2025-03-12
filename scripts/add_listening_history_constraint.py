import os
import logging
import psycopg2
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('add_listening_history_constraint')

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

def check_table_structure():
    """Check the structure of the listening_history table."""
    conn = None
    try:
        # Connect to the database
        logger.info("Establishing database connection")
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Get table columns
        logger.info("Checking listening_history table structure")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'listening_history'
        """)
        columns = cur.fetchall()
        
        logger.info(f"Table columns: {columns}")
        
        # Check for any constraints
        logger.info("Checking existing constraints")
        cur.execute("""
            SELECT con.conname, pg_get_constraintdef(con.oid)
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE rel.relname = 'listening_history'
        """)
        constraints = cur.fetchall()
        
        logger.info(f"Existing constraints: {constraints}")
        
    except Exception as e:
        logger.error(f"Error checking table structure: {str(e)}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed for structure check")

def clean_duplicates():
    """Remove duplicate entries from the listening_history table."""
    conn = None
    try:
        # Connect to the database
        logger.info("Establishing database connection")
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Find duplicate entries
        logger.info("Finding duplicate entries")
        cur.execute("""
            SELECT user_id, track_id, timestamp, COUNT(*)
            FROM listening_history
            GROUP BY user_id, track_id, timestamp
            HAVING COUNT(*) > 1
        """)
        duplicates = cur.fetchall()
        
        logger.info(f"Found {len(duplicates)} sets of duplicate entries")
        
        if duplicates:
            # Handle each set of duplicates
            for dup in duplicates[:10]:  # Log first 10 for debugging
                logger.info(f"Duplicate set: user_id={dup[0]}, track_id={dup[1]}, timestamp={dup[2]}, count={dup[3]}")
            
            # Approach: For each set of duplicates, keep one record and delete the rest
            for user_id, track_id, timestamp, _ in duplicates:
                # Find all IDs for this duplicate set
                cur.execute("""
                    SELECT id 
                    FROM listening_history 
                    WHERE user_id = %s AND track_id = %s AND timestamp = %s 
                    ORDER BY ms_played DESC
                """, (user_id, track_id, timestamp))
                ids = [row[0] for row in cur.fetchall()]
                
                if len(ids) > 1:
                    # Keep the first one (with highest ms_played) and delete the rest
                    ids_to_delete = ids[1:]
                    placeholder = ','.join(['%s'] * len(ids_to_delete))
                    cur.execute(f"""
                        DELETE FROM listening_history 
                        WHERE id IN ({placeholder})
                    """, ids_to_delete)
                    
            # Commit the changes
            conn.commit()
            logger.info("Duplicates removed successfully")
        else:
            logger.info("No duplicates found with this query")
            
    except Exception as e:
        logger.error(f"Error cleaning duplicates: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed for cleanup")

def add_unique_constraint():
    """Add a unique constraint to the listening_history table."""
    conn = None
    try:
        # Connect to the database
        logger.info("Establishing database connection")
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        
        # Check if listening_history table exists
        logger.info("Checking if listening_history table exists")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'listening_history'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.error("listening_history table does not exist!")
            return
        
        # Check if constraint already exists
        logger.info("Checking if constraint already exists")
        cur.execute("""
            SELECT COUNT(*) FROM pg_constraint
            WHERE conname = 'listening_history_user_track_time_key'
        """)
        constraint_exists = cur.fetchone()[0] > 0
        
        if constraint_exists:
            logger.info("Constraint already exists, no need to add it again")
            return
        
        # Add the unique constraint
        logger.info("Adding unique constraint to listening_history table")
        cur.execute("""
            ALTER TABLE listening_history
            ADD CONSTRAINT listening_history_user_track_time_key
            UNIQUE (user_id, track_id, timestamp)
        """)
        
        # Commit the transaction
        conn.commit()
        logger.info("Unique constraint added successfully")
        
    except Exception as e:
        logger.error(f"Error adding unique constraint: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    logger.info("=== ADDING LISTENING HISTORY UNIQUE CONSTRAINT ===")
    # First check the table structure
    check_table_structure()
    # Then clean up duplicates
    clean_duplicates()
    # Finally add the constraint
    add_unique_constraint()
    logger.info("=== PROCESS COMPLETE ===") 