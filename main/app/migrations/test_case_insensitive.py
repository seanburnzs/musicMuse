#!/usr/bin/env python3
"""
Script to test that the case-insensitive functionality is working correctly.
This script runs some test queries with different capitalizations to verify
that the case-insensitive migration was successful.
"""

import os
import sys
import logging
import psycopg2
from configparser import ConfigParser
from tabulate import tabulate

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

def run_test_query(cursor, table, column, value, case_variations=None):
    """Run a test query with different case variations of the value."""
    if case_variations is None:
        # Create variations: original, uppercase, lowercase, title case
        case_variations = [
            value,
            value.upper(),
            value.lower(),
            value.title()
        ]
    
    results = []
    for variation in case_variations:
        # Run query and get count
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = %s", (variation,))
        count = cursor.fetchone()[0]
        
        # Get some sample results if available
        cursor.execute(f"SELECT {column} FROM {table} WHERE {column} = %s LIMIT 3", (variation,))
        samples = [row[0] for row in cursor.fetchall()]
        sample_str = ", ".join(samples) if samples else "No matches"
        
        results.append([variation, count, sample_str])
    
    return results

def test_case_insensitive_search(conn):
    """Run test queries to verify case-insensitive search is working."""
    try:
        with conn.cursor() as cur:
            # Get a sample artist, album and track
            cur.execute("SELECT artist_name FROM artists LIMIT 1")
            artist_result = cur.fetchone()
            if not artist_result:
                logger.warning("No artists found in database")
                artist_name = "No Artist"
            else:
                artist_name = artist_result[0]
                
            cur.execute("SELECT album_name FROM albums LIMIT 1")
            album_result = cur.fetchone()
            if not album_result:
                logger.warning("No albums found in database")
                album_name = "No Album"
            else:
                album_name = album_result[0]
                
            cur.execute("SELECT track_name FROM tracks LIMIT 1")
            track_result = cur.fetchone()
            if not track_result:
                logger.warning("No tracks found in database")
                track_name = "No Track"
            else:
                track_name = track_result[0]
            
            # Test artist name case-insensitivity
            logger.info(f"Testing case-insensitive search for artist: {artist_name}")
            artist_results = run_test_query(cur, "artists", "artist_name", artist_name)
            
            print("\nARTIST SEARCH RESULTS:")
            print(tabulate(artist_results, headers=["Search Variation", "Count", "Sample Matches"]))
            
            # Test album name case-insensitivity
            logger.info(f"Testing case-insensitive search for album: {album_name}")
            album_results = run_test_query(cur, "albums", "album_name", album_name)
            
            print("\nALBUM SEARCH RESULTS:")
            print(tabulate(album_results, headers=["Search Variation", "Count", "Sample Matches"]))
            
            # Test track name case-insensitivity
            logger.info(f"Testing case-insensitive search for track: {track_name}")
            track_results = run_test_query(cur, "tracks", "track_name", track_name)
            
            print("\nTRACK SEARCH RESULTS:")
            print(tabulate(track_results, headers=["Search Variation", "Count", "Sample Matches"]))
            
            # Test a LIKE query with case variations
            if track_name and len(track_name) > 3:
                pattern = track_name[:3] + '%'  # First 3 characters + wildcard
                logger.info(f"Testing case-insensitive LIKE search with pattern: {pattern}")
                
                like_variations = [
                    pattern,
                    pattern.upper(),
                    pattern.lower(),
                    pattern.title() + '%'
                ]
                
                like_results = []
                for variation in like_variations:
                    cur.execute(f"SELECT COUNT(*) FROM tracks WHERE track_name LIKE %s", (variation,))
                    count = cur.fetchone()[0]
                    
                    cur.execute(f"SELECT track_name FROM tracks WHERE track_name LIKE %s LIMIT 3", (variation,))
                    samples = [row[0] for row in cur.fetchall()]
                    sample_str = ", ".join(samples) if samples else "No matches"
                    
                    like_results.append([variation, count, sample_str])
                
                print("\nTRACK LIKE SEARCH RESULTS:")
                print(tabulate(like_results, headers=["LIKE Pattern", "Count", "Sample Matches"]))
            
            # Test if validation passes
            all_counts_match = (
                len(set(row[1] for row in artist_results)) == 1 and
                len(set(row[1] for row in album_results)) == 1 and
                len(set(row[1] for row in track_results)) == 1
            )
            
            if all_counts_match:
                logger.info("✅ SUCCESS: All case variations return the same number of results!")
                print("\n✅ CASE-INSENSITIVE MIGRATION SUCCESSFUL!")
                print("All search variations return the same number of results regardless of case.")
            else:
                logger.error("❌ FAILURE: Different case variations return different numbers of results.")
                print("\n❌ CASE-INSENSITIVE MIGRATION INCOMPLETE OR UNSUCCESSFUL!")
                print("Some search variations return different numbers of results based on case.")
                print("You may need to rerun the migration or check if all tables were properly converted.")
        
    except Exception as e:
        logger.error(f"Error during case-insensitive testing: {str(e)}")
        raise

def main():
    """Main entry point for the script."""
    try:
        logger.info("Starting case-insensitive test")
        
        # Connect to the database using configuration
        conn = get_db_connection_from_config()
        
        # Run tests
        test_case_insensitive_search(conn)
        
        # Close the connection
        conn.close()
        
    except Exception as e:
        logger.error(f"Case-insensitive test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 