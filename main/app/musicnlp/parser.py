"""
Parser component for the Music NLP library.
"""
import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MusicQueryParser:
    """
    Parser for natural language music queries.
    """
    
    def __init__(self):
        # Compile regex patterns for performance
        self.time_pattern = re.compile(
            r"(in|during|from|between)\s+(?:the\s+)?(?:(year|month|week|day)s?\s+of\s+)?([0-9]{4})"
        )
        self.entity_pattern = re.compile(
            r"(track|song|album|artist)s?"
        )
        self.count_pattern = re.compile(
            r"(top|bottom|most|least|favorite|favourite)\s+([0-9]+)?"
        )
        self.event_pattern = re.compile(
            r"(during|in|when|while)\s+(?:my|the)?\s*([a-zA-Z0-9\s]+?)\s*(event|period|time)"
        )
        
    def parse(self, query_text: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured data.
        
        Args:
            query_text: The natural language query text
            
        Returns:
            Dict with parsed query information
        """
        query_text = query_text.lower().strip()
        logger.info(f"Parsing query: {query_text}")
        
        parsed = {
            "original_query": query_text,
            "entity_type": self._extract_entity_type(query_text),
            "time_range": self._extract_time_range(query_text),
            "limit": self._extract_limit(query_text),
            "sort_order": self._extract_sort_order(query_text),
            "event": self._extract_event(query_text),
            "comparison": self._extract_comparison(query_text),
            "explicit_attributes": self._extract_attributes(query_text)
        }
        
        logger.info(f"Parsed query: {parsed}")
        return parsed
    
    def _extract_entity_type(self, query_text: str) -> str:
        """Extract the entity type (track, album, artist) from the query."""
        match = self.entity_pattern.search(query_text)
        if match:
            entity = match.group(1)
            if entity in ["song", "track"]:
                return "track"
            return entity
        
        # Default to track if not specified
        return "track"
    
    def _extract_time_range(self, query_text: str) -> Dict[str, Any]:
        """Extract time range information from the query."""
        time_range = {"type": "all_time", "start": None, "end": None}
        
        if "all time" in query_text:
            return time_range
        
        if "this year" in query_text or "current year" in query_text:
            time_range["type"] = "this_year"
            return time_range
        
        if "last month" in query_text or "past month" in query_text:
            time_range["type"] = "this_month"
            return time_range
        
        if "last week" in query_text or "past week" in query_text:
            time_range["type"] = "this_week"
            return time_range
        
        # Extract year if present
        match = self.time_pattern.search(query_text)
        if match:
            time_unit = match.group(2)
            year = match.group(3)
            
            time_range["type"] = "year"
            time_range["year"] = int(year)
            
        return time_range
    
    def _extract_limit(self, query_text: str) -> int:
        """Extract the limit (number of results) from the query."""
        match = self.count_pattern.search(query_text)
        if match and match.group(2):
            return int(match.group(2))
        
        # Look for number words
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50
        }
        
        for word, number in number_words.items():
            if word in query_text:
                return number
        
        # Default to top 10
        return 10
    
    def _extract_sort_order(self, query_text: str) -> str:
        """Extract the sort order from the query."""
        if any(term in query_text for term in ["top", "most", "favorite", "favourite"]):
            return "desc"
        elif any(term in query_text for term in ["bottom", "least"]):
            return "asc"
        
        # Default to descending
        return "desc"
    
    def _extract_event(self, query_text: str) -> Optional[str]:
        """Extract event information from the query."""
        match = self.event_pattern.search(query_text)
        if match:
            return match.group(2).strip()
        return None
    
    def _extract_comparison(self, query_text: str) -> Dict[str, Any]:
        """Extract comparison information from the query."""
        comparison = {
            "is_comparison": False,
            "entities": []
        }
        
        # Check for comparison keywords
        comparison_terms = ["compare", "vs", "versus", "difference", "between"]
        if not any(term in query_text for term in comparison_terms):
            return comparison
        
        # Mark as a comparison query
        comparison["is_comparison"] = True
        
        # Try to extract entities being compared
        # This is a simplified implementation - could be enhanced with more sophisticated NLP
        if "between" in query_text:
            parts = query_text.split("between")[1].split("and")
            if len(parts) >= 2:
                entity1 = parts[0].strip()
                entity2 = parts[1].strip().split()[0]  # Take first word after "and"
                comparison["entities"] = [entity1, entity2]
        
        return comparison
    
    def _extract_attributes(self, query_text: str) -> Dict[str, Any]:
        """Extract explicit attributes mentioned in the query."""
        attributes = {}
        
        # Check for duration/length mentions
        if any(term in query_text for term in ["longest", "shortest", "duration", "length"]):
            attributes["duration"] = True
        
        # Check for play count mentions
        if any(term in query_text for term in ["most played", "least played", "play count", "times played"]):
            attributes["play_count"] = True
        
        # Check for recency mentions
        if any(term in query_text for term in ["recent", "latest", "newest", "last played"]):
            attributes["recency"] = True
        
        # Check for genre mentions
        genre_match = re.search(r"(genre|style)s?\s+(?:of\s+)?([a-zA-Z0-9\s]+)", query_text)
        if genre_match:
            attributes["genre"] = genre_match.group(2).strip()
        
        return attributes