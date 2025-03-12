import psycopg2
import os
import logging
from dotenv import load_dotenv
from tabulate import tabulate
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("duplicate_identification.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("duplicate_identification")

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

def check_track_aliases_exists():
    """Check if the track_aliases table exists and create if it doesn't."""
    conn = None
    cursor = None
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Check if track_aliases table exists
        cursor.execute("""
            SELECT EXISTS (
               SELECT FROM information_schema.tables 
               WHERE table_name = 'track_aliases'
            );
        """)
        
        if not cursor.fetchone()[0]:
            logger.info("Track aliases table doesn't exist. Please run optimize_database.py first.")
            return False
            
        # Check if potential_track_duplicates view exists
        cursor.execute("""
            SELECT EXISTS (
               SELECT FROM information_schema.views 
               WHERE table_name = 'potential_track_duplicates'
            );
        """)
        
        if not cursor.fetchone()[0]:
            logger.info("Potential track duplicates view doesn't exist. Please run optimize_database.py first.")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def find_potential_duplicates(limit=100, min_similarity=0.8):
    """Find potential duplicate tracks based on name similarity."""
    conn = None
    cursor = None
    duplicates = []
    
    try:
        # Connect to the database
        logger.info("Connecting to database...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Get potential duplicates from view
        logger.info(f"Finding potential duplicates with similarity > {min_similarity}...")
        start_time = time.time()
        cursor.execute(f"""
            SELECT 
                track_id_1, track_id_2, 
                track_name_1, track_name_2,
                album_name_1, album_name_2,
                artist_name_1, artist_name_2,
                name_similarity
            FROM potential_track_duplicates
            WHERE name_similarity > %s
            ORDER BY name_similarity DESC
            LIMIT %s;
        """, (min_similarity, limit))
        
        duplicates = cursor.fetchall()
        duration = time.time() - start_time
        
        if duplicates:
            logger.info(f"Found {len(duplicates)} potential duplicates in {duration:.2f} seconds.")
        else:
            logger.info("No potential duplicates found.")
            
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            logger.info("Database connection closed.")
            
    return duplicates

def get_track_play_counts(track_ids):
    """Get play counts for a list of track IDs."""
    conn = None
    cursor = None
    play_counts = {}
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Get play counts for each track
        for track_id in track_ids:
            cursor.execute("""
                SELECT COUNT(*) FROM listening_history
                WHERE track_id = %s;
            """, (track_id,))
            
            play_counts[track_id] = cursor.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return play_counts

def merge_duplicate_tracks(canonical_id, duplicate_id):
    """Merge duplicate tracks by updating references to point to the canonical track."""
    conn = None
    cursor = None
    success = False
    
    try:
        # Connect to the database
        logger.info(f"Merging track {duplicate_id} into {canonical_id}...")
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # Call the merge_tracks function
        cursor.execute("""
            SELECT merge_tracks(%s, %s);
        """, (canonical_id, duplicate_id))
        
        success = cursor.fetchone()[0]
        
        if success:
            logger.info(f"Successfully merged track {duplicate_id} into {canonical_id}.")
            conn.commit()
        else:
            logger.error(f"Failed to merge track {duplicate_id} into {canonical_id}.")
            conn.rollback()
            
    except Exception as e:
        logger.error(f"Database error while merging tracks: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return success

def prompt_for_duplicates():
    """Interactive prompt to review and merge potential duplicates."""
    if not check_track_aliases_exists():
        logger.error("Required tables don't exist. Please run optimize_database.py first.")
        return
        
    while True:
        # Get user input for similarity threshold
        try:
            min_similarity = float(input("Enter minimum similarity threshold (0.8-1.0): ") or "0.8")
            if min_similarity < 0.8 or min_similarity > 1.0:
                print("Similarity threshold must be between 0.8 and 1.0.")
                continue
        except ValueError:
            print("Please enter a valid number.")
            continue
            
        # Get user input for limit
        try:
            limit = int(input("Enter maximum number of duplicates to review (default 20): ") or "20")
        except ValueError:
            print("Please enter a valid number.")
            continue
            
        # Find potential duplicates
        duplicates = find_potential_duplicates(limit=limit, min_similarity=min_similarity)
        
        if not duplicates:
            print("No potential duplicates found with the current criteria.")
            retry = input("Try again with different criteria? (y/n): ")
            if retry.lower() != 'y':
                break
            continue
            
        # Get play counts for track pairs
        all_track_ids = [pair[0] for pair in duplicates] + [pair[1] for pair in duplicates]
        play_counts = get_track_play_counts(all_track_ids)
        
        # Display duplicates and process merges
        for i, (track_id_1, track_id_2, name_1, name_2, album_1, album_2, artist_1, artist_2, similarity) in enumerate(duplicates):
            print("\n" + "="*80)
            print(f"Duplicate pair {i+1}/{len(duplicates)}:")
            print("="*80)
            
            table = [
                ["", "Track ID", "Track Name", "Album", "Artist", "Play Count"],
                ["Track 1", track_id_1, name_1, album_1, artist_1, play_counts.get(track_id_1, 0)],
                ["Track 2", track_id_2, name_2, album_2, artist_2, play_counts.get(track_id_2, 0)]
            ]
            
            print(tabulate(table, headers="firstrow", tablefmt="fancy_grid"))
            print(f"Similarity: {similarity:.2f}")
            
            action = input("\nActions:\n[1] Merge Track 2 into Track 1\n[2] Merge Track 1 into Track 2\n"
                           "[s] Skip this pair\n[q] Quit\nChoice: ")
                           
            if action.lower() == 'q':
                return
            elif action.lower() == 's':
                continue
            elif action == '1':
                merge_duplicate_tracks(track_id_1, track_id_2)
            elif action == '2':
                merge_duplicate_tracks(track_id_2, track_id_1)
            else:
                print("Invalid choice. Skipping this pair.")
        
        more = input("\nProcess more duplicates? (y/n): ")
        if more.lower() != 'y':
            break

def auto_merge_duplicates(min_similarity=0.95, limit=100):
    """Automatically merge highly similar tracks."""
    if not check_track_aliases_exists():
        logger.error("Required tables don't exist. Please run optimize_database.py first.")
        return
        
    # Find potential duplicates
    logger.info(f"Finding potential duplicates with high similarity (> {min_similarity})...")
    duplicates = find_potential_duplicates(limit=limit, min_similarity=min_similarity)
    
    if not duplicates:
        logger.info("No potential duplicates found with the current criteria.")
        return
        
    # Get play counts for track pairs
    all_track_ids = [pair[0] for pair in duplicates] + [pair[1] for pair in duplicates]
    play_counts = get_track_play_counts(all_track_ids)
    
    merged_count = 0
    for track_id_1, track_id_2, name_1, name_2, album_1, album_2, artist_1, artist_2, similarity in duplicates:
        # Choose the track with more plays as canonical
        if play_counts.get(track_id_1, 0) >= play_counts.get(track_id_2, 0):
            canonical_id, duplicate_id = track_id_1, track_id_2
        else:
            canonical_id, duplicate_id = track_id_2, track_id_1
            
        # Merge the duplicate into canonical
        logger.info(f"Auto-merging: '{name_1}' ({track_id_1}) and '{name_2}' ({track_id_2})")
        if merge_duplicate_tracks(canonical_id, duplicate_id):
            merged_count += 1
    
    logger.info(f"Auto-merged {merged_count} track pairs successfully.")

def main():
    """Main entry point for duplicate identification and merging."""
    print("=" * 80)
    print("Track Duplicate Identification and Resolution Tool")
    print("=" * 80)
    
    if not check_track_aliases_exists():
        print("Required tables don't exist. Please run optimize_database.py first.")
        return
    
    while True:
        print("\nAvailable actions:")
        print("[1] Interactive duplicate review and merging")
        print("[2] Auto-merge highly similar tracks (similarity > 0.95)")
        print("[q] Quit")
        
        choice = input("\nEnter your choice: ")
        
        if choice.lower() == 'q':
            break
        elif choice == '1':
            prompt_for_duplicates()
        elif choice == '2':
            min_similarity = float(input("Enter minimum similarity threshold (0.95-1.0): ") or "0.95")
            limit = int(input("Enter maximum number of duplicates to process: ") or "100")
            auto_merge_duplicates(min_similarity=min_similarity, limit=limit)
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main() 