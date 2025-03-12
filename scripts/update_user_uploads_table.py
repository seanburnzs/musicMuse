import os
import psycopg2
import sys
import logging
import traceback
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('update_user_uploads_table')

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

def update_user_uploads_table():
    """Update the user_uploads table to add processing status columns."""
    logger.info("=== STARTING USER_UPLOADS TABLE UPDATE ===")
    logger.info(f"Database connection parameters: {DB_PARAMS}")
    
    conn = None
    try:
        # Connect to the database
        logger.info("Attempting to connect to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        logger.info("Database connection established")
        cur = conn.cursor()
        
        # First check if the table exists
        logger.info("Checking if user_uploads table exists...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'user_uploads'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.error("user_uploads table does not exist! Please create the table first.")
            return
        
        logger.info("user_uploads table found, checking current columns...")
        
        # Check if the columns already exist
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'user_uploads'
        """)
        
        all_columns = cur.fetchall()
        logger.info(f"Current columns in user_uploads table: {all_columns}")
        
        # Check specific columns we need to modify
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_uploads' 
            AND column_name IN ('processed', 'processing', 'upload_id', 'id')
        """)
        
        existing_columns = [col[0] for col in cur.fetchall()]
        logger.info(f"Relevant columns found: {existing_columns}")
        
        # Determine primary key column name
        has_id = 'id' in existing_columns
        has_upload_id = 'upload_id' in existing_columns
        
        if has_id and not has_upload_id:
            # Add upload_id column if it doesn't exist
            logger.info("Found 'id' column but no 'upload_id' column. Renaming 'id' to 'upload_id'...")
            cur.execute("""
                ALTER TABLE user_uploads 
                RENAME COLUMN id TO upload_id
            """)
            logger.info("Renamed 'id' column to 'upload_id'")
            existing_columns.remove('id')
            existing_columns.append('upload_id')
        elif not has_id and not has_upload_id:
            logger.error("Neither 'id' nor 'upload_id' column found. Table appears to be missing a primary key.")
            return
        
        # Add processed column if it doesn't exist
        if 'processed' not in existing_columns:
            logger.info("Adding 'processed' column...")
            cur.execute("""
                ALTER TABLE user_uploads 
                ADD COLUMN processed BOOLEAN DEFAULT FALSE
            """)
            logger.info("Added 'processed' column to user_uploads table")
        else:
            logger.info("'processed' column already exists")
        
        # Add processing column if it doesn't exist
        if 'processing' not in existing_columns:
            logger.info("Adding 'processing' column...")
            cur.execute("""
                ALTER TABLE user_uploads 
                ADD COLUMN processing BOOLEAN DEFAULT FALSE
            """)
            logger.info("Added 'processing' column to user_uploads table")
        else:
            logger.info("'processing' column already exists")
        
        # Check final table structure
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns 
            WHERE table_name = 'user_uploads'
        """)
        final_columns = cur.fetchall()
        logger.info(f"Final user_uploads table structure: {final_columns}")
        
        # Insert a test row to validate the structure
        try:
            logger.info("Validating table structure with a test query...")
            cur.execute("""
                SELECT 
                    upload_id, user_id, file_name, file_path, 
                    created_at, processed, processing
                FROM user_uploads 
                LIMIT 1
            """)
            test_row = cur.fetchone()
            if test_row:
                logger.info(f"Test query successful. Sample row: {test_row}")
            else:
                logger.info("Test query successful but no rows found in the table.")
        except Exception as test_error:
            logger.error(f"Test query failed: {str(test_error)}")
            logger.error(traceback.format_exc())
        
        # Commit the transaction
        conn.commit()
        logger.info("User uploads table updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating user_uploads table: {str(e)}")
        logger.error(traceback.format_exc())
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed")
    
    logger.info("=== USER_UPLOADS TABLE UPDATE COMPLETE ===")

if __name__ == "__main__":
    update_user_uploads_table() 