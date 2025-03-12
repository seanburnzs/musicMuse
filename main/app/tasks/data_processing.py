import json
import os
import logging
import traceback
import gc  # Garbage collector for managing memory
from datetime import datetime
from celery import shared_task
from ..utils.db import get_db_connection

# Set up detailed logger for this module
logger = logging.getLogger('app.tasks.data_processing')

# Configuration values
MIN_PLAY_DURATION_MS = 30000  # Minimum play duration to consider (30 seconds)
SCHEMA_CASE_INSENSITIVE = True  # Set to True if database uses citext (case-insensitive) columns

@shared_task
def process_streaming_data(file_paths, user_id):
    """
    Process streaming data files and import them into the database.
    
    Args:
        file_paths (list): List of paths to the uploaded streaming data files
        user_id (int): ID of the user who uploaded the files
    
    Returns:
        dict: Summary of the import process
    """
    logger.info(f"=== STARTING DATA PROCESSING ===")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Number of files to process: {len(file_paths)}")
    
    # Log file details
    total_size = 0
    for idx, path in enumerate(file_paths):
        logger.info(f"File {idx+1}: {path}")
        if os.path.exists(path):
            file_size = os.path.getsize(path)
            total_size += file_size
            logger.info(f"  - File exists, size: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")
        else:
            logger.warning(f"  - File does not exist at path!")
    
    logger.info(f"Total size of all files: {total_size} bytes ({total_size/(1024*1024):.2f} MB)")
    
    stats = {
        "processed_files": 0,
        "total_entries": 0,
        "successful_entries": 0,
        "failed_entries": 0,
        "new_artists": 0,
        "new_albums": 0,
        "new_tracks": 0
    }
    
    logger.info("Establishing database connection")
    # Open a single database connection for all files to improve efficiency
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Mark all files as processing
        logger.info("Marking all files as processing in database")
        for file_path in file_paths:
            try:
                # Get the filename from the path
                filename = os.path.basename(file_path)
                logger.info(f"Updating processing status for file: {filename}")
                
                # Update the processing status
                cur.execute(
                    """
                    UPDATE user_uploads 
                    SET processing = TRUE 
                    WHERE user_id = %s AND file_path = %s
                    """,
                    (user_id, file_path)
                )
                logger.info(f"Database updated, committing...")
                conn.commit()
                logger.info(f"File {filename} marked as processing")
            except Exception as e:
                logger.error(f"Error updating processing status for {file_path}: {str(e)}")
                logger.error(traceback.format_exc())
                conn.rollback()
                logger.info("Database rollback performed")
        
        # Process each file one at a time
        for file_idx, file_path in enumerate(file_paths):
            logger.info(f"=== Processing file {file_idx+1}/{len(file_paths)}: {os.path.basename(file_path)} ===")
            try:
                # Read the JSON file with better memory management
                logger.info(f"Reading JSON file: {file_path}")
                try:
                    # Check file size before processing
                    file_size = os.path.getsize(file_path)
                    logger.info(f"File size before processing: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")
                    
                    # For very large files, consider reading in chunks
                    if file_size > 50 * 1024 * 1024:  # 50MB
                        logger.info("Large file detected. Using memory-efficient processing.")
                        process_large_file(file_path, user_id, conn, cur, stats)
                        logger.info("Large file processing complete")
                    else:
                        # Standard processing for regular-sized files
                        with open(file_path, 'r', encoding='utf-8') as f:
                            try:
                                streaming_data = json.load(f)
                                logger.info(f"JSON file read successfully. Data type: {type(streaming_data)}")
                                
                                # Force garbage collection after reading large file
                                gc.collect()
                                
                                if isinstance(streaming_data, list):
                                    logger.info(f"Valid list data found. Number of entries: {len(streaming_data)}")
                                    
                                    # Process the streaming data
                                    process_streaming_list(streaming_data, user_id, conn, cur, stats, file_idx)
                                else:
                                    logger.warning(f"Unexpected data format. Expected list, got: {type(streaming_data)}")
                                    stats["failed_entries"] += 1
                            except json.JSONDecodeError as je:
                                logger.error(f"JSON decode error in file {file_path}: {str(je)}")
                                logger.error(f"Error position: line {je.lineno}, column {je.colno}")
                                stats["failed_entries"] += 1
                                # Mark as not processed due to JSON error
                                logger.info("Marking file as not processed due to JSON error")
                                cur.execute(
                                    """
                                    UPDATE user_uploads 
                                    SET processing = FALSE, processed = FALSE 
                                    WHERE user_id = %s AND file_path = %s
                                    """,
                                    (user_id, file_path)
                                )
                                conn.commit()
                                continue
                except FileNotFoundError:
                    logger.error(f"File not found: {file_path}")
                    stats["failed_entries"] += 1
                    continue
                except PermissionError:
                    logger.error(f"Permission denied when trying to read: {file_path}")
                    stats["failed_entries"] += 1
                    continue
                except MemoryError:
                    logger.error(f"Memory error when processing file: {file_path}")
                    logger.error("Consider using a different approach for very large files")
                    stats["failed_entries"] += 1
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error reading file {file_path}: {str(e)}")
                    logger.error(traceback.format_exc())
                    stats["failed_entries"] += 1
                    continue
                
                stats["processed_files"] += 1
                
                # Mark as processed successfully
                logger.info(f"Marking file {file_idx+1} as processed successfully")
                cur.execute(
                    """
                    UPDATE user_uploads 
                    SET processing = FALSE, processed = TRUE 
                    WHERE user_id = %s AND file_path = %s
                    """,
                    (user_id, file_path)
                )
                logger.info("Database update successful, committing...")
                conn.commit()
                logger.info(f"File {file_idx+1}/{len(file_paths)} processed successfully")
                
                # Don't delete the file anymore so it can be referenced later
                logger.info(f"File {file_path} preserved for reference")
                
                # Force garbage collection after processing each file
                gc.collect()
                logger.info("Memory cleanup performed")
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                logger.error(traceback.format_exc())
                stats["failed_entries"] += 1
                
                # Mark as not processed due to error
                logger.info(f"Marking file as not processed due to error: {str(e)}")
                cur.execute(
                    """
                    UPDATE user_uploads 
                    SET processing = FALSE, processed = FALSE 
                    WHERE user_id = %s AND file_path = %s
                    """,
                    (user_id, file_path)
                )
                conn.commit()
                logger.info("Database updated to reflect processing failure")
                
                # Force garbage collection after error
                gc.collect()
        
    except Exception as e:
        logger.error(f"Critical error in process_streaming_data: {str(e)}")
        logger.error(traceback.format_exc())
        conn.rollback()
        
        # Mark all as not processing if there was a global error
        logger.info("Marking all files as not processing due to critical error")
        for file_path in file_paths:
            try:
                cur.execute(
                    """
                    UPDATE user_uploads 
                    SET processing = FALSE 
                    WHERE user_id = %s AND file_path = %s
                    """,
                    (user_id, file_path)
                )
                conn.commit()
                logger.info(f"Reset processing flag for file: {file_path}")
            except Exception as update_error:
                logger.error(f"Error updating processing status: {str(update_error)}")
                logger.error(traceback.format_exc())
                conn.rollback()
        
        raise
    
    finally:
        logger.info("Closing database connection")
        conn.close()
    
    # Calculate percentages for better insights
    if stats["total_entries"] > 0:
        success_rate = (stats["successful_entries"] / stats["total_entries"]) * 100
        failure_rate = (stats["failed_entries"] / stats["total_entries"]) * 100
        logger.info(f"Processing stats summary:")
        logger.info(f" - Total entries found: {stats['total_entries']}")
        logger.info(f" - Successfully processed: {stats['successful_entries']} ({success_rate:.1f}%)")
        logger.info(f" - Failed/skipped: {stats['failed_entries']} ({failure_rate:.1f}%)")
        logger.info(f" - New artists added: {stats['new_artists']}")
        logger.info(f" - New albums added: {stats['new_albums']}")
        logger.info(f" - New tracks added: {stats['new_tracks']}")
    
    logger.info(f"=== DATA PROCESSING COMPLETE ===")
    logger.info(f"Final stats: {stats}")
    return stats

def process_streaming_list(streaming_data, user_id, conn, cur, stats, file_idx):
    """Process a list of streaming history entries."""
    # Use batch operations for better performance
    batch_size = 100
    entries_batch = []
    
    # Log some sample entries for debugging
    if len(streaming_data) > 0:
        logger.info(f"SAMPLE DATA - First entry in file {file_idx+1}: {streaming_data[0]}")
        # Check for lowercase issue only if database is not case-insensitive
        if not SCHEMA_CASE_INSENSITIVE and streaming_data[0].get("master_metadata_track_name") and streaming_data[0].get("master_metadata_track_name").islower():
            logger.warning("WARNING: Detected all lowercase track names in the data file!")
    
    # Process each entry in the streaming data
    for entry_idx, entry in enumerate(streaming_data):
        if entry_idx % 100 == 0:
            logger.info(f"Processing entry {entry_idx+1}/{len(streaming_data)} in file {file_idx+1}")
        
        stats["total_entries"] += 1
        
        try:
            # Extract data from the entry - handle case normally as database is case-insensitive
            if SCHEMA_CASE_INSENSITIVE:
                # No need to alter case when database handles it
                track_name = entry.get("trackName", entry.get("master_metadata_track_name", "Unknown Track"))
                artist_name = entry.get("artistName", entry.get("master_metadata_album_artist_name", "Unknown Artist"))
                album_name = entry.get("albumName", entry.get("master_metadata_album_album_name", "Unknown Album"))
            else:
                # Use the previous case-fixing approach if needed
                raw_track_name = entry.get("trackName", entry.get("master_metadata_track_name", "Unknown Track"))
                raw_artist_name = entry.get("artistName", entry.get("master_metadata_album_artist_name", "Unknown Artist"))
                raw_album_name = entry.get("albumName", entry.get("master_metadata_album_album_name", "Unknown Album"))
                
                # Apply capitalization fix - proper title case for each
                track_name = raw_track_name.title() if raw_track_name != "Unknown Track" else raw_track_name
                artist_name = raw_artist_name if raw_artist_name != "Unknown Artist" else raw_artist_name
                album_name = raw_album_name if raw_album_name != "Unknown Album" else raw_album_name
                
                # Log the transformation for debugging
                if entry_idx % 100 == 0 or entry_idx < 5:
                    if raw_track_name != track_name:
                        logger.info(f"Capitalization fixed: '{raw_track_name}' -> '{track_name}'")
            
            # Skip entries without critical info
            if track_name == "Unknown Track" and artist_name == "Unknown Artist":
                if entry_idx % 100 == 0:
                    logger.warning(f"Entry {entry_idx+1} skipped - missing track and artist info. Raw data: {entry}")
                stats["failed_entries"] += 1
                continue
            
            # Extract timestamp and ms_played
            timestamp_str = entry.get("endTime", entry.get("ts", None))
            ms_played = entry.get("msPlayed", entry.get("ms_played", 0))
            
            # Filter out plays less than minimum duration
            if ms_played < MIN_PLAY_DURATION_MS:
                logger.info(f"Entry {entry_idx+1} skipped - play time too short: {ms_played}ms for track '{track_name}' by '{artist_name}'")
                stats["failed_entries"] += 1
                continue
            
            # Parse timestamp
            timestamp = datetime.now()
            if timestamp_str:
                try:
                    # Try different timestamp formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M"]:
                        try:
                            timestamp = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass  # Keep default timestamp
            
            # Add to batch with corrected naming
            entries_batch.append({
                "track_name": track_name,
                "artist_name": artist_name,
                "album_name": album_name,
                "timestamp": timestamp,
                "ms_played": ms_played,
                "reason_start": entry.get("reason_start"),
                "reason_end": entry.get("reason_end"),
                "shuffle": entry.get("shuffle", False),
                "skipped": entry.get("skipped", False)
            })
            
            # Process batch if it reaches batch size
            if len(entries_batch) >= batch_size:
                logger.info(f"Processing batch of {len(entries_batch)} entries")
                process_entries_batch(conn, cur, entries_batch, user_id, stats)
                logger.info(f"Batch processed successfully. Running totals: {stats}")
                entries_batch = []
        
        except Exception as e:
            logger.error(f"Error processing entry {entry_idx+1}: {str(e)}")
            logger.error(traceback.format_exc())
            stats["failed_entries"] += 1
    
    # Process any remaining entries
    if entries_batch:
        logger.info(f"Processing final batch of {len(entries_batch)} entries for file {file_idx+1}")
        process_entries_batch(conn, cur, entries_batch, user_id, stats)
        logger.info(f"Final batch processed. Running totals: {stats}")

def process_large_file(file_path, user_id, conn, cur, stats):
    """Process a large JSON file in a memory-efficient way using streaming."""
    import ijson  # Import here to avoid dependency issues if not needed
    
    logger.info("Using ijson for memory-efficient JSON streaming")
    entries_batch = []
    batch_size = 100
    entry_count = 0
    sample_logged = False
    
    try:
        with open(file_path, 'rb') as f:
            # Stream the JSON array items one by one
            parser = ijson.items(f, 'item')
            
            for entry_idx, entry in enumerate(parser):
                # Log the first entry as a sample
                if not sample_logged:
                    logger.info(f"SAMPLE DATA - First streamed entry: {entry}")
                    # Check for lowercase issue only if database is not case-insensitive
                    if not SCHEMA_CASE_INSENSITIVE and entry.get("master_metadata_track_name") and entry.get("master_metadata_track_name").islower():
                        logger.warning("WARNING: Detected all lowercase track names in the data file!")
                    sample_logged = True
                
                if entry_idx % 100 == 0:
                    logger.info(f"Processing streamed entry {entry_idx+1}")
                
                entry_count += 1
                stats["total_entries"] += 1
                
                try:
                    # Extract data from the entry - handle case normally as database is case-insensitive
                    if SCHEMA_CASE_INSENSITIVE:
                        # No need to alter case when database handles it
                        track_name = entry.get("trackName", entry.get("master_metadata_track_name", "Unknown Track"))
                        artist_name = entry.get("artistName", entry.get("master_metadata_album_artist_name", "Unknown Artist"))
                        album_name = entry.get("albumName", entry.get("master_metadata_album_album_name", "Unknown Album"))
                    else:
                        # Use the previous case-fixing approach if needed
                        raw_track_name = entry.get("trackName", entry.get("master_metadata_track_name", "Unknown Track"))
                        raw_artist_name = entry.get("artistName", entry.get("master_metadata_album_artist_name", "Unknown Artist"))
                        raw_album_name = entry.get("albumName", entry.get("master_metadata_album_album_name", "Unknown Album"))
                        
                        # Apply capitalization fix - proper title case for each
                        track_name = raw_track_name.title() if raw_track_name != "Unknown Track" else raw_track_name
                        artist_name = raw_artist_name if raw_artist_name != "Unknown Artist" else raw_artist_name
                        album_name = raw_album_name if raw_album_name != "Unknown Album" else raw_album_name
                        
                        # Log the transformation for debugging
                        if entry_idx % 100 == 0 or entry_idx < 5:
                            if raw_track_name != track_name:
                                logger.info(f"Capitalization fixed: '{raw_track_name}' -> '{track_name}'")
                    
                    # Skip entries without critical info
                    if track_name == "Unknown Track" and artist_name == "Unknown Artist":
                        if entry_idx % 100 == 0:
                            logger.warning(f"Entry {entry_idx+1} skipped - missing track and artist info. Raw data: {entry}")
                        stats["failed_entries"] += 1
                        continue
                    
                    # Extract timestamp and ms_played
                    timestamp_str = entry.get("endTime", entry.get("ts", None))
                    ms_played = entry.get("msPlayed", entry.get("ms_played", 0))
                    
                    # Filter out plays less than minimum duration
                    if ms_played < MIN_PLAY_DURATION_MS:
                        logger.info(f"Entry {entry_idx+1} skipped - play time too short: {ms_played}ms for track '{track_name}' by '{artist_name}'")
                        stats["failed_entries"] += 1
                        continue
                    
                    # Parse timestamp
                    timestamp = datetime.now()
                    if timestamp_str:
                        try:
                            # Try different timestamp formats
                            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M"]:
                                try:
                                    timestamp = datetime.strptime(timestamp_str, fmt)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass  # Keep default timestamp
                    
                    # Add to batch with corrected naming and extra fields
                    entries_batch.append({
                        "track_name": track_name,
                        "artist_name": artist_name,
                        "album_name": album_name,
                        "timestamp": timestamp,
                        "ms_played": ms_played,
                        "reason_start": entry.get("reason_start"),
                        "reason_end": entry.get("reason_end"),
                        "shuffle": entry.get("shuffle", False),
                        "skipped": entry.get("skipped", False)
                    })
                    
                    # Process batch if it reaches batch size
                    if len(entries_batch) >= batch_size:
                        logger.info(f"Processing batch of {len(entries_batch)} streamed entries")
                        process_entries_batch(conn, cur, entries_batch, user_id, stats)
                        logger.info(f"Batch processed successfully. Running totals: {stats}")
                        entries_batch = []
                
                except Exception as e:
                    logger.error(f"Error processing streamed entry {entry_idx+1}: {str(e)}")
                    logger.error(traceback.format_exc())
                    stats["failed_entries"] += 1
            
            # Process any remaining entries
            if entries_batch:
                logger.info(f"Processing final batch of {len(entries_batch)} streamed entries")
                process_entries_batch(conn, cur, entries_batch, user_id, stats)
                logger.info(f"Final batch processed successfully")
            
            logger.info(f"Completed streaming process. Total entries processed: {entry_count}")
    
    except Exception as e:
        logger.error(f"Error during large file streaming: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def process_entries_batch(conn, cur, entries_batch, user_id, stats):
    """Process a batch of streaming history entries."""
    try:
        if SCHEMA_CASE_INSENSITIVE and len(entries_batch) > 0:
            logger.info("Using case-insensitive database schema for entity matching")
            
        for entry_idx, entry in enumerate(entries_batch):
            # Get or create artist
            cur.execute(
                """
                INSERT INTO artists (artist_name)
                VALUES (%s)
                ON CONFLICT (artist_name) DO UPDATE SET artist_name = EXCLUDED.artist_name
                RETURNING artist_id, (xmax = 0) AS is_new
                """,
                (entry["artist_name"],)
            )
            artist_result = cur.fetchone()
            artist_id = artist_result[0]
            if artist_result[1]:  # is_new
                stats["new_artists"] += 1
            
            # Get or create album
            cur.execute(
                """
                INSERT INTO albums (album_name, artist_id)
                VALUES (%s, %s)
                ON CONFLICT (album_name, artist_id) DO UPDATE SET album_name = EXCLUDED.album_name
                RETURNING album_id, (xmax = 0) AS is_new
                """,
                (entry["album_name"], artist_id)
            )
            album_result = cur.fetchone()
            album_id = album_result[0]
            if album_result[1]:  # is_new
                stats["new_albums"] += 1
            
            # Get or create track
            cur.execute(
                """
                INSERT INTO tracks (track_name, album_id)
                VALUES (%s, %s)
                ON CONFLICT (track_name, album_id) DO UPDATE SET track_name = EXCLUDED.track_name
                RETURNING track_id, (xmax = 0) AS is_new
                """,
                (entry["track_name"], album_id)
            )
            track_result = cur.fetchone()
            track_id = track_result[0]
            if track_result[1]:  # is_new
                stats["new_tracks"] += 1
            
            # Always check if the entry already exists first
            cur.execute(
                """
                SELECT COUNT(*) FROM listening_history
                WHERE user_id = %s AND track_id = %s AND timestamp = %s
                """,
                (user_id, track_id, entry["timestamp"])
            )
            
            if cur.fetchone()[0] == 0:
                # No existing entry, insert a new one
                try:
                    cur.execute(
                        """
                        INSERT INTO listening_history (user_id, track_id, timestamp, ms_played, 
                                                      reason_start, reason_end, shuffle, skipped)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, track_id, entry["timestamp"], entry["ms_played"],
                         entry.get("reason_start"), entry.get("reason_end"), 
                         entry.get("shuffle", False), entry.get("skipped", False))
                    )
                    logger.info(f"Successfully added: '{entry['track_name']}' by '{entry['artist_name']}' - {entry['ms_played']}ms at {entry['timestamp']}")
                    stats["successful_entries"] += 1
                except Exception as e:
                    logger.error(f"Error inserting listening history: {str(e)}")
                    logger.error(f"Entry data: {entry}")
                    stats["failed_entries"] += 1
            else:
                # Entry already exists
                logger.info(f"Skipped duplicate: '{entry['track_name']}' by '{entry['artist_name']}' at {entry['timestamp']}")
                # Count as successful since it's already in the database
                stats["successful_entries"] += 1
    
    except Exception as e:
        logger.error(f"Error processing batch: {str(e)}")
        logger.error(traceback.format_exc())
        conn.rollback()
        for entry in entries_batch:
            stats["failed_entries"] += 1
        raise 