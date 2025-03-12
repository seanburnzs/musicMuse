#!/usr/bin/env python3
"""
Script to apply the case-insensitive migration to the database.
This script should be run with appropriate database credentials.
"""

import os
import sys
import argparse
import logging
import psycopg2
from psycopg2 import sql
from configparser import ConfigParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_db_connection_from_config(config_file='config.ini', section='postgresql'):
    """Read database configuration from config file and return a connection."""
    parser = ConfigParser()
    
    if not os.path.exists(config_file):
        logger.error(f"Config file {config_file} not found!")
        sys.exit(1)
        
    parser.read(config_file)
    
    # Get section
    db_config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db_config[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {config_file} file')
    
    # Connect to the database
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise

def apply_migration(conn, force_recreate_views=False):
    """Apply the case insensitivity migration to the database."""
    try:
        # Get the migration SQL
        migration_path = os.path.join(os.path.dirname(__file__), 'case_insensitive_migration.sql')
        
        if not os.path.exists(migration_path):
            logger.error(f"Migration file not found at: {migration_path}")
            sys.exit(1)
            
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Execute the migration
        with conn.cursor() as cur:
            logger.info("Starting migration...")
            
            # If force_recreate_views is True, we'll drop the views with CASCADE first
            if force_recreate_views:
                logger.info("Forcing drop of dependent views with CASCADE...")
                try:
                    # Drop views that might cause dependency issues
                    cur.execute("DROP VIEW IF EXISTS potential_track_duplicates CASCADE;")
                    cur.execute("DROP MATERIALIZED VIEW IF EXISTS user_top_tracks CASCADE;")
                    cur.execute("DROP MATERIALIZED VIEW IF EXISTS user_top_artists CASCADE;")
                    conn.commit()
                    logger.info("Dependent views dropped successfully")
                except Exception as e:
                    logger.error(f"Error dropping views: {str(e)}")
                    conn.rollback()
                    # Continue with the migration anyway
            
            try:
                # Execute the main migration script
                cur.execute(migration_sql)
                logger.info("Migration completed successfully!")
                conn.commit()
            except Exception as e:
                conn.rollback()
                if "depend on it" in str(e):
                    logger.error(f"Dependency error: {str(e)}")
                    logger.error("Please run with --force-recreate-views to automatically drop dependent views")
                else:
                    logger.error(f"Error during migration: {str(e)}")
                raise
        
    except Exception as e:
        logger.error(f"Error applying migration: {str(e)}")
        conn.rollback()
        raise

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Apply case-insensitive migration to the database')
    parser.add_argument('--force-recreate-views', action='store_true', 
                        help='Force recreation of dependent views (will drop them with CASCADE)')
    parser.add_argument('--config', default='config.ini',
                        help='Path to configuration file (default: config.ini)')
    return parser.parse_args()

def main():
    """Main entry point for the script."""
    args = parse_args()
    
    try:
        logger.info("Starting case-insensitive database migration")
        
        # Connect to the database using configuration
        conn = get_db_connection_from_config(config_file=args.config)
        
        # Apply the migration with the force flag
        apply_migration(conn, force_recreate_views=args.force_recreate_views)
        
        # Close the connection
        conn.close()
        
        logger.info("Migration process completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 