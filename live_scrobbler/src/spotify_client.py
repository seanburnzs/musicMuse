"""
Spotify client module for the live scrobbler service.
"""
import logging
import time
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE
)

# Configure logging
logger = logging.getLogger(__name__)

class SpotifyClient:
    """
    A client for interacting with the Spotify API.
    This class handles authentication and API calls.
    """
    
    def __init__(self, access_token=None, refresh_token=None):
        """
        Initialize the Spotify client.
        
        Args:
            access_token: Optional access token for an authenticated user
            refresh_token: Optional refresh token for an authenticated user
        """
        self.auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SPOTIFY_SCOPE
        )
        
        if access_token and refresh_token:
            self.client = spotipy.Spotify(auth=access_token, auth_manager=self.auth_manager)
            self.client.auth_manager.refresh_token = refresh_token
        else:
            self.client = spotipy.Spotify(auth_manager=self.auth_manager)
    
    def get_auth_url(self):
        """Get the authorization URL for the Spotify OAuth flow."""
        return self.auth_manager.get_authorize_url()
    
    def get_tokens(self, code):
        """
        Exchange an authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from the OAuth callback
            
        Returns:
            dict: Token information including access_token, refresh_token, and expires_at
        """
        token_info = self.auth_manager.get_access_token(code)
        return token_info
    
    def refresh_access_token(self, refresh_token):
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            dict: New token information
        """
        self.auth_manager.refresh_token = refresh_token
        token_info = self.auth_manager.refresh_access_token(refresh_token)
        return token_info
    
    def get_user_profile(self):
        """
        Get the current user's Spotify profile.
        
        Returns:
            dict: User profile information
        """
        try:
            return self.client.current_user()
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            raise
    
    def get_recently_played(self, limit=50, after=None, before=None):
        """
        Get the user's recently played tracks.
        
        Args:
            limit: Maximum number of tracks to return (max 50)
            after: Return tracks after this timestamp (in milliseconds)
            before: Return tracks before this timestamp (in milliseconds)
            
        Returns:
            list: Recently played tracks
        """
        try:
            kwargs = {"limit": limit}
            if after:
                kwargs["after"] = after
            if before:
                kwargs["before"] = before
                
            results = self.client.current_user_recently_played(**kwargs)
            return results.get("items", [])
        except Exception as e:
            logger.error(f"Error getting recently played tracks: {e}")
            # If we get a 429 (rate limit), back off and retry
            if hasattr(e, "http_status") and e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 1))
                logger.warning(f"Rate limited. Retrying after {retry_after} seconds")
                time.sleep(retry_after)
                return self.get_recently_played(limit, after, before)
            raise
    
    @staticmethod
    def parse_timestamp(timestamp_str):
        """
        Parse a timestamp string from Spotify API.
        
        Args:
            timestamp_str: ISO8601 timestamp string
            
        Returns:
            datetime: Parsed timestamp
        """
        try:
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
    
    @staticmethod
    def get_image_url(images, preferred_size='medium'):
        """
        Get the best image URL from a list of images.
        
        Args:
            images: List of image objects from Spotify API
            preferred_size: Preferred image size ('small', 'medium', 'large')
            
        Returns:
            str: Image URL or None if no images available
        """
        if not images:
            return None
            
        # Sort images by size (width)
        sorted_images = sorted(images, key=lambda img: img.get('width', 0) if img.get('width') else 0)
        
        if preferred_size == 'small' and len(sorted_images) > 0:
            return sorted_images[0].get('url')
        elif preferred_size == 'large' and len(sorted_images) > 0:
            return sorted_images[-1].get('url')
        elif len(sorted_images) > 1:  # medium or default
            middle_index = len(sorted_images) // 2
            return sorted_images[middle_index].get('url')
        elif len(sorted_images) > 0:
            return sorted_images[0].get('url')
        
        return None
    
    @staticmethod
    def format_track_info(track_item):
        """
        Format a track item from the Spotify API.
        
        Args:
            track_item: Track item from the Spotify API
            
        Returns:
            dict: Formatted track information
        """
        if not track_item:
            return None
            
        played_at_str = track_item.get("played_at")
        if not played_at_str:
            return None
            
        played_at = SpotifyClient.parse_timestamp(played_at_str)
        
        track = track_item.get("track")
        if not track:
            return None
            
        # Extract track details
        track_name = track.get("name", "Unknown Track")
        album = track.get("album", {})
        album_name = album.get("name", "Unknown Album")
        artists = track.get("artists", [])
        artist_name = ", ".join([artist.get("name", "Unknown Artist") for artist in artists])
        
        # Get image URLs
        album_images = album.get("images", [])
        album_image_url = SpotifyClient.get_image_url(album_images)
        
        # Get track popularity
        popularity = track.get("popularity", 0)
        
        # Use track duration as a proxy for ms_played
        ms_played = track.get("duration_ms", 0)
        
        # Skip if essential info is unknown
        if track_name == "Unknown Track" or album_name == "Unknown Album" or artist_name == "Unknown Artist":
            return None
            
        return {
            "played_at": played_at,
            "track_name": track_name,
            "album_name": album_name,
            "artist_name": artist_name,
            "ms_played": ms_played,
            "platform": "Spotify",
            "country": None,
            "reason_start": "scrobble",
            "reason_end": "scrobble",
            "shuffle": False,
            "skipped": False,
            "moods": None,
            "album_image_url": album_image_url,
            "popularity": popularity
        }
        
    def get_artist_image_url(self, artist_name):
        """
        Get an image URL for an artist by searching for them.
        
        Args:
            artist_name: Artist name to search for
            
        Returns:
            str: Artist image URL or None if not found
        """
        try:
            results = self.client.search(q=f"artist:{artist_name}", type="artist", limit=1)
            artists = results.get("artists", {}).get("items", [])
            
            if artists:
                artist = artists[0]
                images = artist.get("images", [])
                return self.get_image_url(images)
            
            return None
        except Exception as e:
            logger.error(f"Error getting artist image URL: {e}")
            return None 