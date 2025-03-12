"""
Tests for the Spotify client module.
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.spotify_client import SpotifyClient

class TestSpotifyClient(unittest.TestCase):
    """Test cases for the SpotifyClient class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = SpotifyClient()
    
    @patch('spotipy.Spotify')
    def test_get_recently_played(self, mock_spotify):
        """Test getting recently played tracks."""
        # Mock the Spotify API response
        mock_response = {
            "items": [
                {
                    "track": {
                        "name": "Test Track",
                        "album": {"name": "Test Album"},
                        "artists": [{"name": "Test Artist"}],
                        "duration_ms": 300000
                    },
                    "played_at": "2023-01-01T12:00:00.000Z"
                }
            ]
        }
        mock_spotify.return_value.current_user_recently_played.return_value = mock_response
        
        # Call the method
        result = self.client.get_recently_played(limit=1)
        
        # Assert the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["track"]["name"], "Test Track")
        
        # Assert the API was called with the correct parameters
        mock_spotify.return_value.current_user_recently_played.assert_called_once_with(limit=1)
    
    def test_parse_timestamp(self):
        """Test parsing timestamps from Spotify API."""
        # Test with milliseconds
        timestamp_with_ms = "2023-01-01T12:00:00.123Z"
        result_with_ms = SpotifyClient.parse_timestamp(timestamp_with_ms)
        self.assertIsInstance(result_with_ms, datetime)
        self.assertEqual(result_with_ms.year, 2023)
        self.assertEqual(result_with_ms.month, 1)
        self.assertEqual(result_with_ms.day, 1)
        self.assertEqual(result_with_ms.hour, 12)
        self.assertEqual(result_with_ms.minute, 0)
        self.assertEqual(result_with_ms.second, 0)
        self.assertEqual(result_with_ms.microsecond, 123000)
        
        # Test without milliseconds
        timestamp_without_ms = "2023-01-01T12:00:00Z"
        result_without_ms = SpotifyClient.parse_timestamp(timestamp_without_ms)
        self.assertIsInstance(result_without_ms, datetime)
        self.assertEqual(result_without_ms.year, 2023)
        self.assertEqual(result_without_ms.month, 1)
        self.assertEqual(result_without_ms.day, 1)
        self.assertEqual(result_without_ms.hour, 12)
        self.assertEqual(result_without_ms.minute, 0)
        self.assertEqual(result_without_ms.second, 0)
        self.assertEqual(result_without_ms.microsecond, 0)
    
    def test_format_track_info(self):
        """Test formatting track information."""
        # Test with valid track item
        valid_track_item = {
            "track": {
                "name": "Test Track",
                "album": {"name": "Test Album"},
                "artists": [{"name": "Test Artist"}],
                "duration_ms": 300000
            },
            "played_at": "2023-01-01T12:00:00.000Z"
        }
        result = SpotifyClient.format_track_info(valid_track_item)
        self.assertIsNotNone(result)
        self.assertEqual(result["track_name"], "Test Track")
        self.assertEqual(result["album_name"], "Test Album")
        self.assertEqual(result["artist_name"], "Test Artist")
        self.assertEqual(result["ms_played"], 300000)
        self.assertIsInstance(result["played_at"], datetime)
        
        # Test with invalid track item (missing track)
        invalid_track_item = {
            "played_at": "2023-01-01T12:00:00.000Z"
        }
        result = SpotifyClient.format_track_info(invalid_track_item)
        self.assertIsNone(result)
        
        # Test with invalid track item (missing played_at)
        invalid_track_item = {
            "track": {
                "name": "Test Track",
                "album": {"name": "Test Album"},
                "artists": [{"name": "Test Artist"}],
                "duration_ms": 300000
            }
        }
        result = SpotifyClient.format_track_info(invalid_track_item)
        self.assertIsNone(result)
        
        # Test with invalid track item (missing essential info)
        invalid_track_item = {
            "track": {
                "name": "Unknown Track",
                "album": {"name": "Test Album"},
                "artists": [{"name": "Test Artist"}],
                "duration_ms": 300000
            },
            "played_at": "2023-01-01T12:00:00.000Z"
        }
        result = SpotifyClient.format_track_info(invalid_track_item)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main() 