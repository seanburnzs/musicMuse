import redis
import json
import os
from functools import wraps
import hashlib
from dotenv import load_dotenv
import logging
from datetime import datetime, date

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Redis client
redis_client = redis.Redis.from_url(
    os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    decode_responses=True
)

def cache_key(namespace, *args, **kwargs):
    """
    Generate a cache key with namespace support.
    
    Args:
        namespace: The namespace for the cache key
        *args, **kwargs: Arguments to include in the key
    """
    # Start with the namespace
    key_parts = [namespace]
    
    # Add the args
    key_parts.extend([str(arg) for arg in args])
    
    # Add the kwargs in sorted order
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    
    # Join with colons
    key_str = ":".join(key_parts)
    
    # Hash the key if it's too long
    if len(key_str) > 200:
        return f"{namespace}:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    return key_str

def serialize_for_redis(obj):
    """Safely serialize an object for Redis storage."""
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        # Try using a custom JSON encoder
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                if hasattr(obj, "__dict__"):
                    return obj.__dict__
                return str(obj)
        
        try:
            return json.dumps(obj, cls=CustomEncoder)
        except:
            # If all else fails, return string representation
            return str(obj)

def redis_cache(prefix, expire=3600):
    """
    Decorator to cache function results in Redis.
    
    Args:
        prefix: Prefix for the cache key
        expire: Cache expiration time in seconds (default: 1 hour)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached = redis_client.get(key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    # If not JSON, return as is
                    return cached
            
            # Call the function
            result = func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                redis_client.set(key, serialize_for_redis(result), ex=expire)
            
            return result
        return wrapper
    return decorator

def invalidate_cache(prefix, pattern=None):
    """
    Invalidate cache entries with the given prefix.
    
    Args:
        prefix: Cache key prefix
        pattern: Optional pattern to match (e.g., "user:123:*")
    """
    if pattern:
        key_pattern = f"{prefix}:{pattern}"
    else:
        key_pattern = f"{prefix}:*"
    
    # Get all matching keys
    keys = redis_client.keys(key_pattern)
    
    # Delete keys if any found
    if keys:
        redis_client.delete(*keys)
        logger.info(f"Invalidated {len(keys)} cache entries with pattern {key_pattern}")