"""
Database connector for the Music NLP library.
"""
import psycopg2
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class MusicDBConnector:
    """
    Database connector for music data.
    """
    
    def __init__(self, db_config):
        """
        Initialize the database connector.
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        
    def get_connection(self):
        """Get a database connection."""
        return psycopg2.connect(**self.db_config)
    
    def get_event_by_name(self, event_name: str, user_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Get event information by name.
        
        Args:
            event_name: The event name to search for
            user_id: Optional user ID to restrict search
            
        Returns:
            Event information or None if not found
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build query based on whether user_id is provided
            if user_id:
                query = """
                    SELECT event_id, name, start_date, end_date, description, category
                    FROM user_events
                    WHERE user_id = %s AND LOWER(name) LIKE %s
                    LIMIT 1
                """
                cursor.execute(query, (user_id, f"%{event_name.lower()}%"))
            else:
                query = """
                    SELECT event_id, name, start_date, end_date, description, category
                    FROM user_events
                    WHERE LOWER(name) LIKE %s
                    LIMIT 1
                """
                cursor.execute(query, (f"%{event_name.lower()}%",))
                
            result = cursor.fetchone()
            
            if result:
                return {
                    "event_id": result[0],
                    "name": result[1],
                    "start_date": result[2],
                    "end_date": result[3],
                    "description": result[4],
                    "category": result[5]
                }
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting event by name: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
    def get_user_top_items(self, 
                          user_id: int, 
                          item_type: str, 
                          limit: int = 10,
                          time_range: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Get top items for a user.
        
        Args:
            user_id: The user ID
            item_type: The type of item (track, album, artist)
            limit: Maximum number of items to return
            time_range: Optional time range filter
            
        Returns:
            List of top items
        """
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Build query based on item type
            if item_type == "track":
                query = """
                    SELECT 
                        tracks.track_name,
                        artists.artist_name,
                        COUNT(*) as play_count,
                        SUM(listening_history.ms_played)/60000.0 as total_minutes
                    FROM listening_history
                    JOIN tracks ON listening_history.track_id = tracks.track_id
                    JOIN albums ON tracks.album_id = albums.album_id
                    JOIN artists ON albums.artist_id = artists.artist_id
                    WHERE listening_history.user_id = %s
                    {time_filter}
                    GROUP BY tracks.track_name, artists.artist_name
                    ORDER BY play_count DESC
                    LIMIT %s
                """
            elif item_type == "album":
                query = """
                    SELECT 
                        albums.album_name,
                        artists.artist_name,
                        COUNT(*) as play_count,
                        SUM(listening_history.ms_played)/60000.0 as total_minutes
                    FROM listening_history
                    JOIN tracks ON listening_history.track_id = tracks.track_id
                    JOIN albums ON tracks.album_id = albums.album_id
                    JOIN artists ON albums.artist_id = artists.artist_id
                    WHERE listening_history.user_id = %s
                    {time_filter}
                    GROUP BY albums.album_name, artists.artist_name
                    ORDER BY play_count DESC
                    LIMIT %s
                """
            elif item_type == "artist":
                query = """
                    SELECT 
                        artists.artist_name,
                        COUNT(*) as play_count,
                        SUM(listening_history.ms_played)/60000.0 as total_minutes
                    FROM listening_history
                    JOIN tracks ON listening_history.track_id = tracks.track_id
                    JOIN albums ON tracks.album_id = albums.album_id
                    JOIN artists ON albums.artist_id = artists.artist_id
                    WHERE listening_history.user_id = %s
                    {time_filter}
                    GROUP BY artists.artist_name
                    ORDER BY play_count DESC
                    LIMIT %s
                """
            else:
                return []
                
            # Add time filter if provided
            params = [user_id]
            time_filter = ""
            
            if time_range:
                time_type = time_range.get("type")
                
                if time_type != "all_time":
                    time_filter = "AND listening_history.timestamp >= %s"
                    params.append(time_range.get("start"))
                    
                    if time_range.get("end"):
                        time_filter += " AND listening_history.timestamp <= %s"
                        params.append(time_range.get("end"))
            
            # Add limit parameter
            params.append(limit)
            
            # Format the query with the time filter
            query = query.format(time_filter=time_filter)
            
            # Execute the query
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Format the results
            formatted_results = []
            for result in results:
                if item_type == "track":
                    formatted_result = {
                        "track_name": result[0],
                        "artist_name": result[1],
                        "play_count": result[2],
                        "total_minutes": round(result[3], 2)
                    }
                elif item_type == "album":
                    formatted_result = {
                        "album_name": result[0],
                        "artist_name": result[1],
                        "play_count": result[2],
                        "total_minutes": round(result[3], 2)
                    }
                elif item_type == "artist":
                    formatted_result = {
                        "artist_name": result[0],
                        "play_count": result[1],
                        "total_minutes": round(result[2], 2)
                    }
                    
                formatted_results.append(formatted_result)
                
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error getting top items: {str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()