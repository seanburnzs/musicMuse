"""
Client interface for the Music NLP library.
"""
from typing import Dict, Any, Optional
import logging
from .parser import MusicQueryParser
from .analyzer import MusicQueryAnalyzer
from .executor import MusicQueryExecutor
from .db_connector import MusicDBConnector

logger = logging.getLogger(__name__)

class MusicNLPClient:
    """
    Client interface for the Music NLP library.
    """
    
    def __init__(self, db_config):
        """
        Initialize the client.
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.db_connector = MusicDBConnector(db_config)
        self.parser = MusicQueryParser()
        self.analyzer = MusicQueryAnalyzer(self.db_connector)
        self.executor = MusicQueryExecutor(db_config)
        
    def process_query(self, query_text: str, user_id: int) -> Dict[str, Any]:
        """
        Process a natural language query.
        
        Args:
            query_text: The natural language query text
            user_id: The user ID to process the query for
            
        Returns:
            Query results and metadata
        """
        try:
            # Parse the query
            parsed_query = self.parser.parse(query_text)
            
            # Analyze the query
            analyzed_query = self.analyzer.analyze(parsed_query)
            
            # Execute the query
            results = self.executor.execute(analyzed_query, user_id)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                "error": str(e),
                "query": query_text
            }