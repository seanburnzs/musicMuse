"""Date and time utility functions."""
from datetime import datetime, timedelta, date
from typing import Tuple, Optional
from .constants import (
    TIME_RANGE_ALL_TIME, TIME_RANGE_THIS_WEEK, TIME_RANGE_THIS_MONTH,
    TIME_RANGE_THIS_YEAR, TIME_RANGE_YEAR_2024, TIME_RANGE_YEAR_2023,
    TIME_RANGE_CUSTOM
)

def get_date_range(time_range, custom_start=None, custom_end=None):
    """
    Get date filter and parameters for SQL queries based on time range.
    
    Args:
        time_range (str): The time range to filter by (e.g., 'all_time', 'last_week', 'last_month', 'custom')
        custom_start (str): Custom start date in YYYY-MM-DD format (for 'custom' time_range)
        custom_end (str): Custom end date in YYYY-MM-DD format (for 'custom' time_range)
    
    Returns:
        tuple: (date_filter, date_params) where date_filter is a SQL WHERE clause and date_params is a list of parameters
    """
    today = date.today()
    
    if time_range == "all_time":
        return "", []
    
    elif time_range == "last_week" or time_range == "this_week":
        start_date = today - timedelta(days=7)
        return "AND timestamp >= %s", [start_date]
    
    elif time_range == "last_month" or time_range == "this_month":
        start_date = today - timedelta(days=30)
        return "AND timestamp >= %s", [start_date]
    
    elif time_range == "last_year":
        start_date = today - timedelta(days=365)
        return "AND timestamp >= %s", [start_date]
    
    elif time_range == "this_year":
        start_date = date(today.year, 1, 1)
        return "AND timestamp >= %s", [start_date]
        
    elif time_range == "year_2024":
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)
        return "AND timestamp BETWEEN %s AND %s", [start_date, end_date]
        
    elif time_range == "year_2023":
        start_date = date(2023, 1, 1)
        end_date = date(2023, 12, 31)
        return "AND timestamp BETWEEN %s AND %s", [start_date, end_date]
    
    elif time_range == "last_year_only":
        start_date = date(today.year - 1, 1, 1)
        end_date = date(today.year - 1, 12, 31)
        return "AND timestamp BETWEEN %s AND %s", [start_date, end_date]
    
    elif time_range == "custom" and custom_start:
        try:
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            
            if custom_end:
                end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
                return "AND timestamp BETWEEN %s AND %s", [start_date, end_date]
            else:
                return "AND timestamp >= %s", [start_date]
        except ValueError:
            # Invalid date format, return all time
            return "", []
    
    # Default to all time
    return "", []

def format_date(date_obj, format_str="%B %d, %Y"):
    """Format a date object as a string."""
    if not date_obj:
        return ""
    return date_obj.strftime(format_str)

def get_date_parts(date_str):
    """Split a date string into year, month, day parts."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        return date_obj.year, date_obj.month, date_obj.day
    except (ValueError, TypeError):
        return None, None, None

def date_to_str(date_obj: Optional[date]) -> Optional[str]:
    """Convert a date object to YYYY-MM-DD string format."""
    if date_obj is None:
        return None
    return date_obj.strftime("%Y-%m-%d")

def format_timestamp(timestamp: datetime) -> str:
    """Format a timestamp for display."""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def get_year_start_end(year: int) -> Tuple[date, date]:
    """Get the start and end dates for a specific year."""
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    return start_date, end_date