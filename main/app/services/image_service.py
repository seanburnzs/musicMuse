import logging
from ..models.db import get_db
from ..services.spotify_service import SpotifyService
from flask import current_app

# Set up logger
logger = logging.getLogger(__name__)

class ImageService:
    """Service for managing media images (albums, artists, tracks)"""
    
    def __init__(self, spotify_service=None):
        """Initialize with optional SpotifyService instance"""
        self.spotify = spotify_service or SpotifyService()
        self.db = get_db()
    
    def update_artist_images(self, limit=None):
        """Update image URLs for artists that don't have images
        
        Args:
            limit (int, optional): Maximum number of artists to update at once
        
        Returns:
            int: Number of artists updated
        """
        cursor = self.db.cursor()
        
        # Get artists without images and not yet attempted
        query = """
            SELECT artist_id, artist_name
            FROM artists
            WHERE image_search_attempted = FALSE
            ORDER BY artist_id
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        artists = cursor.fetchall()
        
        if not artists:
            logger.info("No new artists to search for images")
            return 0
            
        count = 0
        for artist_id, artist_name in artists:
            try:
                # Get image URL from Spotify
                image_url = self.spotify.get_artist_image(artist_name)
                
                if image_url:
                    # Update the database with image URL
                    update_query = """
                        UPDATE artists 
                        SET image_url = %s, image_search_attempted = TRUE
                        WHERE artist_id = %s
                    """
                    cursor.execute(update_query, (image_url, artist_id))
                    count += 1
                    logger.info(f"Updated image for artist: {artist_name}")
                else:
                    # Mark as attempted even when no image is found
                    update_query = """
                        UPDATE artists 
                        SET image_search_attempted = TRUE
                        WHERE artist_id = %s
                    """
                    cursor.execute(update_query, (artist_id,))
                    logger.warning(f"No image found for artist: {artist_name}")
                
                self.db.commit()
            except Exception as e:
                logger.error(f"Error updating image for artist {artist_name}: {str(e)}")
                self.db.rollback()
                
        return count
        
    def update_album_images(self, limit=None):
        """Update image URLs for albums that don't have images
        
        Args:
            limit (int, optional): Maximum number of albums to update at once
        
        Returns:
            int: Number of albums updated
        """
        cursor = self.db.cursor()
        
        # Get albums without images and not yet attempted
        query = """
            SELECT albums.album_id, albums.album_name, artists.artist_name
            FROM albums
            JOIN artists ON albums.artist_id = artists.artist_id
            WHERE albums.image_search_attempted = FALSE
            ORDER BY albums.album_id
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        albums = cursor.fetchall()
        
        if not albums:
            logger.info("No new albums to search for images")
            return 0
            
        count = 0
        for album_id, album_name, artist_name in albums:
            try:
                # Get image URL from Spotify
                image_url = self.spotify.get_album_image(album_name, artist_name)
                
                if image_url:
                    # Update the database with image URL
                    update_query = """
                        UPDATE albums 
                        SET image_url = %s, image_search_attempted = TRUE
                        WHERE album_id = %s
                    """
                    cursor.execute(update_query, (image_url, album_id))
                    count += 1
                    logger.info(f"Updated image for album: {album_name} by {artist_name}")
                else:
                    # Mark as attempted even when no image is found
                    update_query = """
                        UPDATE albums 
                        SET image_search_attempted = TRUE
                        WHERE album_id = %s
                    """
                    cursor.execute(update_query, (album_id,))
                    logger.warning(f"No image found for album: {album_name} by {artist_name}")
                
                self.db.commit()
            except Exception as e:
                logger.error(f"Error updating image for album {album_name}: {str(e)}")
                self.db.rollback()
                
        return count
        
    def update_track_images(self, limit=None):
        """
        Updates track image URLs using the track's album image_url field.
        Since tracks typically use their album's image, this efficiently
        sets track images based on their associated album.
        
        Args:
            limit (int, optional): Maximum number of tracks to update at once
            
        Returns:
            int: Number of tracks updated
        """
        cursor = self.db.cursor()
        
        # First, get the track IDs that need updating
        select_query = """
            SELECT tracks.track_id
            FROM tracks
            JOIN albums ON tracks.album_id = albums.album_id
            WHERE albums.image_url IS NOT NULL
            AND albums.image_url != ''
            AND tracks.image_search_attempted = FALSE
            ORDER BY tracks.track_id
        """
        
        if limit and limit > 0:
            select_query += f" LIMIT {limit}"
            
        try:
            cursor.execute(select_query)
            track_ids = [row[0] for row in cursor.fetchall()]
            
            if not track_ids:
                logger.info("No new tracks to update with album images")
                return 0
                
            # Now update each track with its album's image
            count = 0
            for track_id in track_ids:
                update_query = """
                    UPDATE tracks 
                    SET image_url = (
                        SELECT albums.image_url 
                        FROM albums 
                        WHERE albums.album_id = tracks.album_id
                    ),
                    image_search_attempted = TRUE
                    WHERE track_id = %s
                """
                cursor.execute(update_query, (track_id,))
                count += cursor.rowcount
                
            self.db.commit()
            logger.info(f"Updated {count} track images from album images")
            return count
        except Exception as e:
            logger.error(f"Error updating track images from albums: {str(e)}")
            self.db.rollback()
            return 0
            
    def fetch_missing_track_images(self, limit=None):
        """Fetch images directly from Spotify for tracks that still don't have images
        
        Args:
            limit (int, optional): Maximum number of tracks to update at once
            
        Returns:
            int: Number of tracks updated
        """
        cursor = self.db.cursor()
        
        # Get tracks without images and not yet attempted
        query = """
            SELECT tracks.track_id, tracks.track_name, artists.artist_name
            FROM tracks
            JOIN albums ON tracks.album_id = albums.album_id
            JOIN artists ON albums.artist_id = artists.artist_id
            WHERE tracks.image_search_attempted = FALSE
            ORDER BY tracks.track_id
        """
        
        if limit:
            query += f" LIMIT {limit}"
            
        cursor.execute(query)
        tracks = cursor.fetchall()
        
        if not tracks:
            logger.info("No new tracks to search for images")
            return 0
            
        count = 0
        for track_id, track_name, artist_name in tracks:
            try:
                # Get image URL from Spotify
                image_url = self.spotify.get_track_image(track_name, artist_name)
                
                if image_url:
                    # Update the database with image URL
                    update_query = """
                        UPDATE tracks 
                        SET image_url = %s, image_search_attempted = TRUE
                        WHERE track_id = %s
                    """
                    cursor.execute(update_query, (image_url, track_id))
                    count += 1
                    logger.info(f"Updated image for track: {track_name} by {artist_name}")
                else:
                    # Mark as attempted even when no image is found
                    update_query = """
                        UPDATE tracks 
                        SET image_search_attempted = TRUE
                        WHERE track_id = %s
                    """
                    cursor.execute(update_query, (track_id,))
                    logger.warning(f"No image found for track: {track_name} by {artist_name}")
                
                self.db.commit()
            except Exception as e:
                logger.error(f"Error updating image for track {track_name}: {str(e)}")
                self.db.rollback()
                
        return count 