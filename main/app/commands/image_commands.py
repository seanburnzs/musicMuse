import click
from flask import current_app
from flask.cli import with_appcontext
import time
import logging
import os

from ..services.image_service import ImageService

# Set up logger
logger = logging.getLogger(__name__)

@click.group()
def images():
    """Commands to manage media images for artists, albums, and tracks"""
    pass

@images.command('update-all')
@click.option('--limit', default=100, help='Maximum number of items to update per type')
@click.option('--batch-size', default=10, help='Number of items to update in each batch')
@click.option('--delay', default=1.0, help='Delay between batches in seconds')
@with_appcontext
def update_all_images(limit, batch_size, delay):
    """Update images for artists, albums, and tracks that don't have images"""
    image_service = ImageService()
    start_time = time.time()
    
    total_updated = 0
    remaining = limit
    
    click.echo("Starting image update process...")
    
    # Update artists in batches
    artist_count = 0
    while remaining > 0:
        batch_limit = min(batch_size, remaining)
        updated = image_service.update_artist_images(batch_limit)
        artist_count += updated
        total_updated += updated
        
        if updated < batch_limit:
            # No more artists to update
            break
            
        remaining -= updated
        if remaining > 0 and delay > 0:
            time.sleep(delay)
    
    click.echo(f"Updated {artist_count} artist images")
    
    # Update albums in batches
    album_count = 0
    remaining = limit
    while remaining > 0:
        batch_limit = min(batch_size, remaining)
        updated = image_service.update_album_images(batch_limit)
        album_count += updated
        total_updated += updated
        
        if updated < batch_limit:
            # No more albums to update
            break
            
        remaining -= updated
        if remaining > 0 and delay > 0:
            time.sleep(delay)
    
    click.echo(f"Updated {album_count} album images")
    
    # Update tracks from album images
    track_count = image_service.update_track_images(limit)
    total_updated += track_count
    click.echo(f"Updated {track_count} track images from their albums")
    
    # Fetch missing track images directly
    missing_count = 0
    remaining = limit
    while remaining > 0:
        batch_limit = min(batch_size, remaining)
        updated = image_service.fetch_missing_track_images(batch_limit)
        missing_count += updated
        total_updated += updated
        
        if updated < batch_limit:
            # No more tracks to update
            break
            
        remaining -= updated
        if remaining > 0 and delay > 0:
            time.sleep(delay)
    
    click.echo(f"Fetched {missing_count} missing track images directly")
    
    elapsed_time = time.time() - start_time
    click.echo(f"Image update process completed in {elapsed_time:.2f} seconds")
    click.echo(f"Total images updated: {total_updated}")

@images.command('update-artists')
@click.option('--limit', default=50, help='Maximum number of artists to update')
@with_appcontext
def update_artist_images(limit):
    """Update images for artists that don't have images"""
    image_service = ImageService()
    count = image_service.update_artist_images(limit)
    click.echo(f"Updated {count} artist images")

@images.command('update-albums')
@click.option('--limit', default=50, help='Maximum number of albums to update')
@with_appcontext
def update_album_images(limit):
    """Update images for albums that don't have images"""
    image_service = ImageService()
    count = image_service.update_album_images(limit)
    click.echo(f"Updated {count} album images")

@images.command('update-tracks-from-albums')
@click.option('--limit', default=500, help='Maximum number of tracks to update')
@with_appcontext
def update_tracks_from_albums(limit):
    """Update track images from their album images"""
    image_service = ImageService()
    count = image_service.update_track_images(limit)
    click.echo(f"Updated {count} track images from their albums")

@images.command('fetch-missing-tracks')
@click.option('--limit', default=50, help='Maximum number of tracks to update')
@with_appcontext
def fetch_missing_track_images(limit):
    """Fetch images directly for tracks that still don't have images"""
    image_service = ImageService()
    count = image_service.fetch_missing_track_images(limit)
    click.echo(f"Fetched {count} missing track images directly") 