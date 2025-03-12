"""
Database initialization script for the live scrobbler service.
"""
import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config import DB_CONFIG

# Configure logging
logger = logging.getLogger(__name__)

def create_database():
    """Create the database if it doesn't exist."""
    db_name = DB_CONFIG["dbname"]
    
    # Connect to PostgreSQL server
    conn_params = DB_CONFIG.copy()
    conn_params["dbname"] = "postgres"  # Connect to default database
    
    conn = None
    try:
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
        exists = cur.fetchone()
        
        if not exists:
            logger.info(f"Creating database {db_name}")
            cur.execute(f"CREATE DATABASE {db_name};")
            logger.info(f"Database {db_name} created successfully")
        else:
            logger.info(f"Database {db_name} already exists")
        
        cur.close()
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_schema():
    """Initialize the database schema."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Read schema file
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config",
            "schema.sql"
        )
        
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        
        logger.info("Initializing database schema")
        cur.execute(schema_sql)
        conn.commit()
        logger.info("Database schema initialized successfully")
        
        cur.close()
    except Exception as e:
        logger.error(f"Error initializing schema: {e}")
        raise
    finally:
        if conn:
            conn.close()

def main():
    """Main entry point for database initialization."""
    try:
        create_database()
        init_schema()
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

if __name__ == "__main__":
    main() 