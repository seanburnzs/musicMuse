import os
import psycopg2
import logging
import traceback
from dotenv import load_dotenv

# Set up logger
logger = logging.getLogger('app.utils.db')

# Load environment variables
load_dotenv()

def get_db_connection():
    """
    Get a connection to the database.
    
    Returns:
        connection: A connection to the PostgreSQL database
    """
    logger.info("Establishing database connection")
    try:
        # Configure connection from environment variables
        db_params = {
            'dbname': os.getenv('DB_NAME', 'musicmuse_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASS', ''),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432')
        }
        
        logger.info(f"Connecting to database: {db_params['dbname']} on {db_params['host']}:{db_params['port']} as {db_params['user']}")
        
        # Create connection
        conn = psycopg2.connect(**db_params)
        logger.info("Database connection established successfully")
        
        # Test connection by checking for user_uploads table
        cur = conn.cursor()
        try:
            logger.info("Checking if user_uploads table exists")
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = 'user_uploads'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                logger.info("user_uploads table exists")
                
                # Check table structure
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'user_uploads';
                """)
                columns = cur.fetchall()
                logger.info(f"user_uploads table structure: {columns}")
                
                # Check if processed and processing columns exist
                has_processed = any(col[0] == 'processed' for col in columns)
                has_processing = any(col[0] == 'processing' for col in columns)
                logger.info(f"Has processed column: {has_processed}, Has processing column: {has_processing}")
            else:
                logger.warning("user_uploads table does not exist")
        except Exception as e:
            logger.error(f"Error checking database schema: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            cur.close()
        
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        logger.error(traceback.format_exc())
        raise 