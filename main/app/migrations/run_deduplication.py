#!/usr/bin/env python3
"""
Script to deduplicate entities in the database before applying case-insensitive migration.
This script identifies and merges entities that differ only in case.
"""

import os
import sys
import argparse
import logging
import psycopg2
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

def run_deduplication(conn, dry_run=False):
    """Run the deduplication script on the database."""
    try:
        # Determine which SQL file to use
        if dry_run:
            # Try to use the single-result-set version first (more compatible)
            script_path = os.path.join(os.path.dirname(__file__), 'deduplicate_dry_run_single.sql')
            if not os.path.exists(script_path):
                # Fall back to the original dry run SQL
                script_path = os.path.join(os.path.dirname(__file__), 'deduplicate_dry_run.sql')
                
            if not os.path.exists(script_path):
                # Create a dry run SQL file on the fly if it doesn't exist
                logger.info("Creating dry run SQL script...")
                
                # Create the more compatible single-result-set version
                dry_run_sql = """
                -- Begin transaction
                BEGIN;
                
                -- Combined query to count duplicates for all entity types in a single result set
                SELECT 
                    'artists' as entity_type,
                    COUNT(*) as duplicate_sets,
                    SUM(num_duplicates) as total_duplicates
                FROM (
                    SELECT 
                        COUNT(*) - 1 as num_duplicates
                    FROM 
                        artists
                    GROUP BY 
                        LOWER(artist_name)
                    HAVING 
                        COUNT(*) > 1
                ) as artist_stats
                
                UNION ALL
                
                SELECT 
                    'albums' as entity_type,
                    COUNT(*) as duplicate_sets,
                    SUM(num_duplicates) as total_duplicates
                FROM (
                    SELECT 
                        COUNT(*) - 1 as num_duplicates
                    FROM 
                        albums
                    GROUP BY 
                        artist_id, LOWER(album_name)
                    HAVING 
                        COUNT(*) > 1
                ) as album_stats
                
                UNION ALL
                
                SELECT 
                    'tracks' as entity_type,
                    COUNT(*) as duplicate_sets,
                    SUM(num_duplicates) as total_duplicates
                FROM (
                    SELECT 
                        COUNT(*) - 1 as num_duplicates
                    FROM 
                        tracks
                    GROUP BY 
                        album_id, LOWER(track_name)
                    HAVING 
                        COUNT(*) > 1
                ) as track_stats;
                
                -- Artist duplicate details (top 20)
                SELECT 
                    'ARTIST' as entity_type,
                    LOWER(artist_name) as normalized_name,
                    string_agg(artist_name, ', ') as duplicate_names,
                    COUNT(*) as count
                FROM 
                    artists
                GROUP BY 
                    LOWER(artist_name)
                HAVING 
                    COUNT(*) > 1
                ORDER BY count DESC, normalized_name
                LIMIT 20;
                
                -- Album duplicate details (top 20)
                SELECT 
                    'ALBUM' as entity_type,
                    LOWER(album_name) as normalized_name,
                    string_agg(album_name, ', ') as duplicate_names,
                    COUNT(*) as count
                FROM 
                    albums
                GROUP BY 
                    artist_id, LOWER(album_name)
                HAVING 
                    COUNT(*) > 1
                ORDER BY count DESC, normalized_name
                LIMIT 20;
                
                -- Track duplicate details (top 20)
                SELECT 
                    'TRACK' as entity_type,
                    LOWER(track_name) as normalized_name,
                    string_agg(track_name, ', ') as duplicate_names,
                    COUNT(*) as count
                FROM 
                    tracks
                GROUP BY 
                    album_id, LOWER(track_name)
                HAVING 
                    COUNT(*) > 1
                ORDER BY count DESC, normalized_name
                LIMIT 20;
                
                -- Rollback to make no changes
                ROLLBACK;
                """
                
                # Write the dry run SQL to a file
                with open(os.path.join(os.path.dirname(__file__), 'deduplicate_dry_run_single.sql'), 'w') as f:
                    f.write(dry_run_sql)
                
                script_path = os.path.join(os.path.dirname(__file__), 'deduplicate_dry_run_single.sql')
                logger.info(f"Created dry run SQL script at {script_path}")
        else:
            # Path to the simplified SQL that uses SELECT for logging
            script_path = os.path.join(os.path.dirname(__file__), 'deduplicate_entities_simple.sql')
            
            # If the simplified file doesn't exist, fall back to the original
            if not os.path.exists(script_path):
                script_path = os.path.join(os.path.dirname(__file__), 'deduplicate_entities.sql')
        
        if not os.path.exists(script_path):
            logger.error(f"Deduplication script not found at: {script_path}")
            sys.exit(1)
            
        with open(script_path, 'r') as f:
            dedup_sql = f.read()
        
        # Execute the SQL
        with conn.cursor() as cur:
            logger.info("Starting deduplication...")
            
            if dry_run:
                logger.info("Running in DRY RUN mode - no changes will be made")
                
                # Execute the SQL in sequential statements to avoid multiple result sets
                statements = [stmt.strip() for stmt in dedup_sql.split(';') if stmt.strip()]
                
                # First statement is just BEGIN
                cur.execute(statements[0] + ';')
                
                # Second statement is the summary count
                cur.execute(statements[1] + ';')
                summary_results = cur.fetchall()
                
                # Process and display summary results
                has_duplicates = False
                for row in summary_results:
                    entity_type, duplicate_sets, total_duplicates = row
                    duplicate_sets = duplicate_sets or 0  # Handle NULL
                    total_duplicates = total_duplicates or 0  # Handle NULL
                    
                    if duplicate_sets > 0:
                        has_duplicates = True
                        logger.info(f"Found {duplicate_sets} sets of duplicate {entity_type} with {total_duplicates} total duplicates")
                    else:
                        logger.info(f"No duplicate {entity_type} found")
                
                # Process artist details if they exist
                if len(statements) > 2:
                    cur.execute(statements[2] + ';')
                    artist_duplicates = cur.fetchall()
                    if artist_duplicates:
                        logger.info(f"\nDuplicate artists (showing up to 20):")
                        for row in artist_duplicates:
                            entity_type, normalized_name, duplicate_names, count = row
                            logger.info(f"  - {duplicate_names} (normalized: {normalized_name}, count: {count})")
                
                # Process album details if they exist
                if len(statements) > 3:
                    cur.execute(statements[3] + ';')
                    album_duplicates = cur.fetchall()
                    if album_duplicates:
                        logger.info(f"\nDuplicate albums (showing up to 20):")
                        for row in album_duplicates:
                            entity_type, normalized_name, duplicate_names, count = row
                            logger.info(f"  - {duplicate_names} (normalized: {normalized_name}, count: {count})")
                
                # Process track details if they exist
                if len(statements) > 4:
                    cur.execute(statements[4] + ';')
                    track_duplicates = cur.fetchall()
                    if track_duplicates:
                        logger.info(f"\nDuplicate tracks (showing up to 20):")
                        for row in track_duplicates:
                            entity_type, normalized_name, duplicate_names, count = row
                            logger.info(f"  - {duplicate_names} (normalized: {normalized_name}, count: {count})")
                
                # Execute ROLLBACK
                cur.execute("ROLLBACK;")
                
                # Summarize
                if has_duplicates:
                    logger.info("\nFound case-insensitive duplicates that need to be merged")
                    logger.info("Run without --dry-run to apply the deduplication")
                else:
                    logger.info("\nNo case-insensitive duplicates found - your database is already clean!")
            else:
                # Execute each statement separately to capture informational SELECT output
                logger.info("Running deduplication...")
                
                # Start a transaction
                conn.autocommit = False
                
                # Execute the SQL and capture informational output from SELECT statements
                for statement in dedup_sql.split(';'):
                    if not statement.strip():
                        continue
                        
                    statement = statement.strip() + ';'
                    if statement.upper().startswith('SELECT'):
                        try:
                            cur.execute(statement)
                            result = cur.fetchone()
                            if result and result[0]:
                                logger.info(f"DB INFO: {result[0]}")
                        except Exception as e:
                            logger.error(f"Error executing SELECT: {str(e)}")
                            logger.error(f"Statement: {statement}")
                            conn.rollback()
                            raise
                    else:
                        try:
                            cur.execute(statement)
                        except Exception as e:
                            logger.error(f"Error executing statement: {str(e)}")
                            logger.error(f"Statement: {statement}")
                            conn.rollback()
                            raise
                
                # Commit the transaction
                conn.commit()
                logger.info("Deduplication completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during deduplication: {str(e)}")
        if not dry_run:
            try:
                conn.rollback()
            except:
                pass  # Ignore if rollback fails
        raise

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Deduplicate database entities that differ only by case')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Only identify duplicates without making any changes')
    parser.add_argument('--config', default='config.ini',
                        help='Path to configuration file (default: config.ini)')
    return parser.parse_args()

def main():
    """Main entry point for the script."""
    args = parse_args()
    
    try:
        logger.info("Starting database deduplication process")
        
        # Connect to the database using configuration
        conn = get_db_connection_from_config(config_file=args.config)
        
        # Run deduplication with the dry-run flag
        run_deduplication(conn, dry_run=args.dry_run)
        
        # Close the connection
        conn.close()
        
        logger.info("Deduplication process completed successfully")
        
    except Exception as e:
        logger.error(f"Deduplication failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 