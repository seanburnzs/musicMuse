"""
Tests for the database module.
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.database import (
    get_or_create_artist,
    get_or_create_album,
    get_or_create_track,
    record_exists,
    insert_listening_history,
    get_or_create_user,
    get_user_credentials,
    update_user_credentials,
    get_active_users
)

class TestDatabase(unittest.TestCase):
    """Test cases for the database module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock connection and cursor
        self.mock_conn = MagicMock()
        self.mock_cur = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cur
    
    def test_get_or_create_artist(self):
        """Test getting or creating an artist."""
        # Test when artist exists
        self.mock_cur.fetchone.return_value = (1,)
        artist_id = get_or_create_artist(self.mock_conn, "Test Artist")
        self.assertEqual(artist_id, 1)
        self.mock_cur.execute.assert_called_with(
            "SELECT artist_id FROM artists WHERE artist_name = %s;",
            ("Test Artist",)
        )
        
        # Test when artist doesn't exist
        self.mock_cur.fetchone.side_effect = [None, (2,)]
        artist_id = get_or_create_artist(self.mock_conn, "New Artist")
        self.assertEqual(artist_id, 2)
        self.mock_cur.execute.assert_called_with(
            "INSERT INTO artists (artist_name) VALUES (%s) RETURNING artist_id;",
            ("New Artist",)
        )
    
    def test_get_or_create_album(self):
        """Test getting or creating an album."""
        # Test when album exists
        self.mock_cur.fetchone.return_value = (1,)
        album_id = get_or_create_album(self.mock_conn, "Test Album", 1)
        self.assertEqual(album_id, 1)
        self.mock_cur.execute.assert_called_with(
            "SELECT album_id FROM albums WHERE album_name = %s AND artist_id = %s;",
            ("Test Album", 1)
        )
        
        # Test when album doesn't exist
        self.mock_cur.fetchone.side_effect = [None, (2,)]
        album_id = get_or_create_album(self.mock_conn, "New Album", 1)
        self.assertEqual(album_id, 2)
        self.mock_cur.execute.assert_called_with(
            "INSERT INTO albums (album_name, artist_id) VALUES (%s, %s) RETURNING album_id;",
            ("New Album", 1)
        )
    
    def test_get_or_create_track(self):
        """Test getting or creating a track."""
        # Test when track exists
        self.mock_cur.fetchone.return_value = (1,)
        track_id = get_or_create_track(self.mock_conn, "Test Track", 1)
        self.assertEqual(track_id, 1)
        self.mock_cur.execute.assert_called_with(
            "SELECT track_id FROM tracks WHERE track_name = %s AND album_id = %s;",
            ("Test Track", 1)
        )
        
        # Test when track doesn't exist
        self.mock_cur.fetchone.side_effect = [None, (2,)]
        track_id = get_or_create_track(self.mock_conn, "New Track", 1)
        self.assertEqual(track_id, 2)
        self.mock_cur.execute.assert_called_with(
            "INSERT INTO tracks (track_name, album_id) VALUES (%s, %s) RETURNING track_id;",
            ("New Track", 1)
        )
    
    def test_record_exists(self):
        """Test checking if a record exists."""
        # Test when record exists
        self.mock_cur.fetchone.return_value = (1,)
        exists = record_exists(self.mock_conn, 1, datetime.now(), 1)
        self.assertTrue(exists)
        
        # Test when record doesn't exist
        self.mock_cur.fetchone.return_value = None
        exists = record_exists(self.mock_conn, 1, datetime.now(), 1)
        self.assertFalse(exists)
    
    def test_insert_listening_history(self):
        """Test inserting a listening history record."""
        # Mock record_exists to return False (record doesn't exist)
        with patch('src.database.record_exists', return_value=False):
            timestamp = datetime.now()
            inserted = insert_listening_history(
                self.mock_conn, 1, timestamp, 1, 300000,
                platform="Spotify", country="US", reason_start="scrobble",
                reason_end="scrobble", shuffle=False, skipped=False, moods=None
            )
            self.assertTrue(inserted)
            self.mock_cur.execute.assert_called_once()
            self.mock_conn.commit.assert_called_once()
        
        # Mock record_exists to return True (record exists)
        with patch('src.database.record_exists', return_value=True):
            timestamp = datetime.now()
            inserted = insert_listening_history(
                self.mock_conn, 1, timestamp, 1, 300000
            )
            self.assertFalse(inserted)
            # No new calls to execute or commit
            self.mock_cur.execute.assert_not_called()
            self.mock_conn.commit.assert_not_called()
    
    def test_get_or_create_user(self):
        """Test getting or creating a user."""
        # Test when user exists
        self.mock_cur.fetchone.return_value = (1,)
        user_id = get_or_create_user(self.mock_conn, "spotify_user_1")
        self.assertEqual(user_id, 1)
        
        # Test when user doesn't exist
        self.mock_cur.fetchone.side_effect = [None, (2,)]
        user_id = get_or_create_user(
            self.mock_conn, "spotify_user_2", "Test User", "test@example.com"
        )
        self.assertEqual(user_id, 2)
        self.mock_cur.execute.assert_called_with(
            """
                INSERT INTO users (spotify_id, display_name, email, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING user_id;
                """,
            ("spotify_user_2", "Test User", "test@example.com")
        )
    
    def test_get_user_credentials(self):
        """Test getting user credentials."""
        # Test when credentials exist
        self.mock_cur.fetchone.return_value = ("access_token", "refresh_token", datetime.now())
        credentials = get_user_credentials(self.mock_conn, 1)
        self.assertIsNotNone(credentials)
        self.assertEqual(credentials["access_token"], "access_token")
        self.assertEqual(credentials["refresh_token"], "refresh_token")
        
        # Test when credentials don't exist
        self.mock_cur.fetchone.return_value = None
        credentials = get_user_credentials(self.mock_conn, 1)
        self.assertIsNone(credentials)
    
    def test_update_user_credentials(self):
        """Test updating user credentials."""
        token_expiry = datetime.now()
        update_user_credentials(
            self.mock_conn, 1, "new_access_token", "new_refresh_token", token_expiry
        )
        self.mock_cur.execute.assert_called_once()
        self.mock_conn.commit.assert_called_once()
    
    def test_get_active_users(self):
        """Test getting active users."""
        self.mock_cur.fetchall.return_value = [(1, "spotify_user_1"), (2, "spotify_user_2")]
        active_users = get_active_users(self.mock_conn)
        self.assertEqual(len(active_users), 2)
        self.assertEqual(active_users[0][0], 1)
        self.assertEqual(active_users[0][1], "spotify_user_1")

if __name__ == '__main__':
    unittest.main() 