"""
Executor component for the Music NLP library.
Responsible for converting analyzed queries into SQL and executing them.
"""
from typing import Dict, Any, List, Tuple, Optional
import logging
import psycopg2
from datetime import datetime, date

logger = logging.getLogger(__name__)

class MusicQueryExecutor:
    """
    Executor for analyzed music queries.
    """
    
    def __init__(self, db_config):
        """
        Initialize the executor.
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        
    def execute(self, analyzed_query: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """
        Execute an analyzed query and return results.
        
        Args:
            analyzed_query: The analyzed query dictionary
            user_id: The user ID to execute the query for
            
        Returns:
            Query results and metadata
        """
        try:
            # Build SQL query
            sql_query, params = self._build_sql_query(analyzed_query, user_id)
            
            # Execute the query
            results = self._execute_sql(sql_query, params)
            
            # Format the results
            formatted_results = self._format_results(results, analyzed_query)
            
            # Build the response
            response = {
                "query": analyzed_query["original_query"],
                "intent": analyzed_query["intent"],
                "results": formatted_results,
                "metadata": {
                    "entity_type": analyzed_query["entity_type"],
                    "time_range": analyzed_query["time_range"],
                    "count": len(formatted_results)
                }
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            return {
                "error": str(e),
                "query": analyzed_query["original_query"]
            }
            
    def _build_sql_query(self, 
                        analyzed_query: Dict[str, Any], 
                        user_id: int) -> Tuple[str, List[Any]]:
        """
        Build a SQL query from the analyzed query.
        
        Args:
            analyzed_query: The analyzed query dictionary
            user_id: The user ID to build the query for
            
        Returns:
            Tuple of (sql_query, params)
        """
        entity_type = analyzed_query["entity_type"]
        intent = analyzed_query["intent"]
        limit = analyzed_query.get("limit", 10)
        sort_order = analyzed_query.get("sort_order", "desc")
        
        # Start building the query
        select_clause = self._build_select_clause(entity_type, intent)
        from_clause = self._build_from_clause(entity_type)
        where_clause, where_params = self._build_where_clause(analyzed_query, user_id)
        group_by_clause = self._build_group_by_clause(entity_type)
        order_by_clause = self._build_order_by_clause(entity_type, sort_order)
        limit_clause = f"LIMIT {limit}"
        
        # Combine all clauses
        sql_query = f"""
            {select_clause}
            {from_clause}
            {where_clause}
            {group_by_clause}
            {order_by_clause}
            {limit_clause}
        """
        
        return sql_query, where_params
    
    def _build_select_clause(self, entity_type: str, intent: str) -> str:
        """Build the SELECT clause based on entity type and intent."""
        if entity_type == "track":
            return """
                SELECT 
                    tracks.track_name,
                    artists.artist_name,
                    COUNT(*) as play_count,
                    SUM(listening_history.ms_played)/60000.0 as total_minutes
            """
        elif entity_type == "album":
            return """
                SELECT 
                    albums.album_name,
                    artists.artist_name,
                    COUNT(*) as play_count,
                    SUM(listening_history.ms_played)/60000.0 as total_minutes
            """
        elif entity_type == "artist":
            return """
                SELECT 
                    artists.artist_name,
                    COUNT(*) as play_count,
                    SUM(listening_history.ms_played)/60000.0 as total_minutes
            """
        else:
            # Default
            return """
                SELECT 
                    tracks.track_name,
                    artists.artist_name,
                    COUNT(*) as play_count,
                    SUM(listening_history.ms_played)/60000.0 as total_minutes
            """
    
    def _build_from_clause(self, entity_type: str) -> str:
        """Build the FROM clause based on entity type."""
        return """
            FROM listening_history
            JOIN tracks ON listening_history.track_id = tracks.track_id
            JOIN albums ON tracks.album_id = albums.album_id
            JOIN artists ON albums.artist_id = artists.artist_id
        """
    
    def _build_where_clause(self, 
                           analyzed_query: Dict[str, Any], 
                           user_id: int) -> Tuple[str, List[Any]]:
        """Build the WHERE clause based on the analyzed query."""
        conditions = ["listening_history.user_id = %s"]
        params = [user_id]
        
        # Handle time range
        time_range = analyzed_query.get("time_range", {})
        if time_range and time_range.get("type") != "all_time":
            start_date, end_date = self._get_date_range(time_range)
            
            if start_date:
                conditions.append("listening_history.timestamp >= %s")
                params.append(start_date)
                
            if end_date:
                conditions.append("listening_history.timestamp <= %s")
                params.append(end_date)
                
        # Handle event context
        event_context = analyzed_query.get("event_context", {})
        if event_context and event_context.get("resolved"):
            start_date = event_context.get("start_date")
            end_date = event_context.get("end_date")
            
            if start_date:
                conditions.append("listening_history.timestamp >= %s")
                params.append(start_date)
                
            if end_date:
                conditions.append("listening_history.timestamp <= %s")
                params.append(end_date)
        
        # Construct final WHERE clause
        where_clause = "WHERE " + " AND ".join(conditions)
        
        return where_clause, params
    
    def _build_group_by_clause(self, entity_type: str) -> str:
        """Build the GROUP BY clause based on entity type."""
        if entity_type == "track":
            return "GROUP BY tracks.track_name, artists.artist_name"
        elif entity_type == "album":
            return "GROUP BY albums.album_name, artists.artist_name"
        elif entity_type == "artist":
            return "GROUP BY artists.artist_name"
        else:
            return "GROUP BY tracks.track_name, artists.artist_name"
    
    def _build_order_by_clause(self, entity_type: str, sort_order: str) -> str:
        """Build the ORDER BY clause based on entity type and sort order."""
        return f"ORDER BY play_count {sort_order}"
    
    def _get_date_range(self, time_range: Dict[str, Any]) -> Tuple[Optional[date], Optional[date]]:
        """Convert time range specification to actual dates."""
        time_type = time_range.get("type")
        today = datetime.now().date()
        
        if time_type == "this_year":
            start_date = date(today.year, 1, 1)
            return start_date, today
            
        elif time_type == "this_month":
            # 30 days back
            start_date = today.replace(day=1)
            return start_date, today
            
        elif time_type == "this_week":
            # 7 days back
            from datetime import timedelta
            start_date = today - timedelta(days=7)
            return start_date, today
            
        elif time_type == "year" and "year" in time_range:
            year = time_range["year"]
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            return start_date, end_date
            
        # Default - all time
        return None, None
    
    def _execute_sql(self, sql_query: str, params: List[Any]) -> List[Tuple]:
        """
        Execute a SQL query with parameters.
        
        Args:
            sql_query: The SQL query to execute
            params: The parameters for the query
            
        Returns:
            List of result tuples
        """
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute(sql_query, params)
            results = cursor.fetchall()
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing SQL: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _format_results(self, 
                       results: List[Tuple], 
                       analyzed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format raw SQL results into a structured response.
        
        Args:
            results: Raw SQL result tuples
            analyzed_query: The analyzed query
            
        Returns:
            Formatted results as a list of dictionaries
        """
        entity_type = analyzed_query["entity_type"]
        formatted_results = []
        
        for result in results:
            if entity_type == "track":
                formatted_result = {
                    "track_name": result[0],
                    "artist_name": result[1],
                    "play_count": result[2],
                    "total_minutes": round(result[3], 2)
                }
            elif entity_type == "album":
                formatted_result = {
                    "album_name": result[0],
                    "artist_name": result[1],
                    "play_count": result[2],
                    "total_minutes": round(result[3], 2)
                }
            elif entity_type == "artist":
                formatted_result = {
                    "artist_name": result[0],
                    "play_count": result[1],
                    "total_minutes": round(result[2], 2)
                }
            else:
                # Default
                formatted_result = {
                    "name": result[0],
                    "count": result[1]
                }
                
            formatted_results.append(formatted_result)
            
        return formatted_results