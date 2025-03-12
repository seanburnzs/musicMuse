import os
from dotenv import load_dotenv
from app.services.spotify_service import SpotifyService

def test_spotify_api():
    """Test that we can authenticate with Spotify and retrieve data."""
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("ERROR: Missing Spotify API credentials!")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file")
        return False
    
    # Create a SpotifyService instance
    spotify = SpotifyService(client_id, client_secret)
    
    # Test authentication
    token = spotify._get_auth_token()
    if not token:
        print("ERROR: Failed to get authentication token from Spotify!")
        return False
    
    print("✅ Successfully authenticated with Spotify API!")
    
    # Test searching for an artist
    artist_name = "Taylor Swift"
    artist_image = spotify.get_artist_image(artist_name)
    
    if artist_image:
        print(f"✅ Successfully found image for artist '{artist_name}':")
        print(f"   {artist_image}")
    else:
        print(f"❌ Could not find image for artist '{artist_name}'")
    
    # Test searching for an album
    album_name = "1989"
    artist_name = "Taylor Swift"
    album_image = spotify.get_album_image(album_name, artist_name)
    
    if album_image:
        print(f"✅ Successfully found image for album '{album_name}' by '{artist_name}':")
        print(f"   {album_image}")
    else:
        print(f"❌ Could not find image for album '{album_name}' by '{artist_name}'")
    
    # Test searching for a track
    track_name = "Shake It Off"
    artist_name = "Taylor Swift"
    track_image = spotify.get_track_image(track_name, artist_name)
    
    if track_image:
        print(f"✅ Successfully found image for track '{track_name}' by '{artist_name}':")
        print(f"   {track_image}")
    else:
        print(f"❌ Could not find image for track '{track_name}' by '{artist_name}'")
    
    return True

if __name__ == "__main__":
    test_spotify_api() 