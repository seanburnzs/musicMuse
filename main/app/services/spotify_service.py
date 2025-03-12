import os
import base64
import requests
import time
from flask import current_app
import logging

# Set up logger
logger = logging.getLogger(__name__)

class SpotifyService:
    """Service for interacting with Spotify API to retrieve metadata such as images"""
    
    def __init__(self, client_id=None, client_secret=None):
        """Initialize with client credentials"""
        self.client_id = client_id or os.environ.get('SPOTIFY_CLIENT_ID')
        self.client_secret = client_secret or os.environ.get('SPOTIFY_CLIENT_SECRET')
        self.token = None
        self.token_expiry = 0
    
    def _get_auth_token(self):
        """Get a new auth token or use cached one if still valid"""
        current_time = time.time()
        
        # Return existing token if it's still valid (with 60s buffer)
        if self.token and current_time < self.token_expiry -.60:
            return self.token
            
        # Otherwise, get a new token
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Authorization": f"Basic {auth_base64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}
        
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            json_result = response.json()
            self.token = json_result["access_token"]
            # Save expiry time (subtract 60s as buffer)
            self.token_expiry = current_time + json_result["expires_in"] - 60
            
            return self.token
        except Exception as e:
            logger.error(f"Error getting Spotify auth token: {str(e)}")
            return None
    
    def _make_api_request(self, endpoint):
        """Make an authenticated request to the Spotify API"""
        token = self._get_auth_token()
        if not token:
            logger.error("Failed to get authentication token")
            return None
            
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://api.spotify.com/v1{endpoint}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            if status_code == 404:
                logger.warning(f"Resource not found at {endpoint}")
            else:
                logger.error(f"HTTP error {status_code} when accessing {endpoint}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error making Spotify API request to {endpoint}: {str(e)}")
            return None
    
    def search_item(self, query, item_type, limit=1):
        """Search for an item by name and get the first result
        
        Args:
            query (str): Search query
            item_type (str): One of 'artist', 'album', or 'track'
            limit (int): Maximum number of results to return
            
        Returns:
            dict: The first search result or None if not found
        """
        # URL encode the query
        encoded_query = requests.utils.quote(query)
        endpoint = f"/search?q={encoded_query}&type={item_type}&limit={limit}"
        
        results = self._make_api_request(endpoint)
        if not results:
            return None
            
        # The results are structured differently for each type
        items = results.get(f"{item_type}s", {}).get("items", [])
        return items[0] if items else None
    
    def get_artist_image(self, artist_name):
        """Get the image URL for an artist by name"""
        artist = self.search_item(artist_name, "artist")
        if not artist or not artist.get("images"):
            return None
            
        # Get the medium-sized image if available, otherwise the first one
        images = artist.get("images", [])
        if len(images) > 1:
            return images[1]["url"]  # Medium size
        elif images:
            return images[0]["url"]  # First available
        return None
    
    def get_album_image(self, album_name, artist_name=None):
        """Get the image URL for an album by name and optionally artist name"""
        query = album_name
        if artist_name:
            query += f" artist:{artist_name}"
            
        album = self.search_item(query, "album")
        if not album or not album.get("images"):
            return None
            
        images = album.get("images", [])
        if len(images) > 1:
            return images[1]["url"]  # Medium size
        elif images:
            return images[0]["url"]  # First available
        return None
    
    def get_track_image(self, track_name, artist_name=None):
        """Get the image URL for a track (from its album) by name and optionally artist name"""
        query = track_name
        if artist_name:
            query += f" artist:{artist_name}"
            
        track = self.search_item(query, "track")
        if not track or not track.get("album") or not track["album"].get("images"):
            return None
            
        images = track["album"].get("images", [])
        if len(images) > 1:
            return images[1]["url"]  # Medium size
        elif images:
            return images[0]["url"]  # First available
        return None 