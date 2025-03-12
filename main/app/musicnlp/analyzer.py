"""
Analyzer component for the Music NLP library.
Responsible for semantic analysis and inference of user intent.
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class MusicQueryAnalyzer:
    """
    Analyzer for parsed music queries.
    """
    
    def __init__(self, db_connector=None):
        """
        Initialize the analyzer.
        
        Args:
            db_connector: Optional database connector for context-aware analysis
        """
        self.db_connector = db_connector
        
    def analyze(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a parsed query to infer additional context and intent.
        
        Args:
            parsed_query: The parsed query dictionary
            
        Returns:
            Enhanced query with additional context and intent information
        """
        enhanced_query = parsed_query.copy()
        
        # Determine the primary intent of the query
        enhanced_query["intent"] = self._determine_intent(parsed_query)
        
        # Enhance entity recognition
        if enhanced_query["entity_type"]:
            enhanced_query["entity_info"] = self._enhance_entity_info(parsed_query)
            
        # Resolve event context if present
        if enhanced_query["event"]:
            enhanced_query["event_context"] = self._resolve_event_context(parsed_query["event"])
            
        # Determine attributes to include in response
        enhanced_query["response_attributes"] = self._determine_response_attributes(parsed_query)
        
        return enhanced_query
    
    def _determine_intent(self, parsed_query: Dict[str, Any]) -> str:
        """Determine the primary intent of the query."""
        query_text = parsed_query["original_query"]
        
        # Check for comparison intent
        if any(term in query_text for term in ["compare", "versus", "vs", "difference"]):
            return "comparison"
            
        # Check for listing intent
        if any(term in query_text for term in ["list", "show", "display", "what are"]):
            return "listing"
            
        # Check for count intent
        if any(term in query_text for term in ["how many", "count", "total number"]):
            return "count"
            
        # Check for trend intent
        if any(term in query_text for term in ["trend", "over time", "pattern", "change"]):
            return "trend"
            
        # Default to listing
        return "listing"
    
    def _enhance_entity_info(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance entity recognition with additional context."""
        entity_type = parsed_query["entity_type"]
        query_text = parsed_query["original_query"]
        
        entity_info = {
            "type": entity_type,
            "attributes": []
        }
        
        # Determine relevant attributes based on entity type
        if entity_type == "track":
            entity_info["attributes"] = ["track_name", "artist_name", "album_name", "ms_played"]
            
            # Check for specific focus on particular track attributes
            if "longest" in query_text:
                entity_info["sort_attribute"] = "ms_played"
            elif "most played" in query_text:
                entity_info["sort_attribute"] = "play_count"
        
        elif entity_type == "album":
            entity_info["attributes"] = ["album_name", "artist_name", "total_tracks", "total_plays"]
            
        elif entity_type == "artist":
            entity_info["attributes"] = ["artist_name", "total_tracks", "total_plays"]
            
        return entity_info
    
    def _resolve_event_context(self, event_name: str) -> Dict[str, Any]:
        """
        Resolve event context from the database if available.
        
        Args:
            event_name: Name of the event to resolve
            
        Returns:
            Event context information if found
        """
        event_context = {
            "name": event_name,
            "resolved": False
        }
        
        # Skip if no database connector
        if not self.db_connector:
            return event_context
            
        try:
            # Try to query the database for event information
            event_data = self.db_connector.get_event_by_name(event_name)
            
            if event_data:
                event_context.update({
                    "resolved": True,
                    "start_date": event_data["start_date"],
                    "end_date": event_data["end_date"],
                    "description": event_data["description"]
                })
                
        except Exception as e:
            logger.error(f"Error resolving event context: {str(e)}")
            
        return event_context
    
    def _determine_response_attributes(self, parsed_query: Dict[str, Any]) -> List[str]:
        """Determine which attributes to include in the response based on the query."""
        intent = self._determine_intent(parsed_query)
        entity_type = parsed_query["entity_type"]
        query_text = parsed_query["original_query"]
        
        # Default attributes based on entity type
        if entity_type == "track":
            attributes = ["track_name", "artist_name", "play_count", "total_time"]
        elif entity_type == "album":
            attributes = ["album_name", "artist_name", "play_count", "total_time"]
        elif entity_type == "artist":
            attributes = ["artist_name", "play_count", "total_time"]
        else:
            attributes = ["name", "count"]
            
        # Add time-related attributes if query is time-focused
        if any(term in query_text for term in ["when", "time", "date", "period"]):
            attributes.extend(["first_played", "last_played"])
            
        return attributes