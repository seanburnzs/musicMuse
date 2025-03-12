"""
MusicNLP - A custom natural language processing library for music-related queries.
"""

from .parser import MusicQueryParser
from .analyzer import MusicQueryAnalyzer
from .executor import MusicQueryExecutor
from .client import MusicNLPClient

__version__ = '0.1.0'

def process_query(query_text, user_id):
    """
    Process a natural language query about music.
    
    Args:
        query_text: The query text
        user_id: The user ID
        
    Returns:
        Query results
    """
    from ..utils.db import get_db_connection
    import logging
    import psycopg2
    import os
    
    try:
        # Create a proper database configuration dictionary with actual connection parameters
        # Instead of passing the get_connection function directly
        db_config = {
            "dbname": os.getenv("DB_NAME", "musicmuse_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432"))
        }
        
        # Create a client instance
        client = MusicNLPClient(db_config)
        
        # Process the query
        results = client.process_query(query_text, user_id)
        return results
    except Exception as e:
        logging.error(f"Error processing query: {str(e)}")
        return {
            "error": str(e),
            "query": query_text
        }