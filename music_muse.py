#!/usr/bin/env python3
import os
import re
import psycopg2
from datetime import datetime
import logging
import dotenv

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)

class MusicMuse:
    def __init__(self, db_params):
        self.db_params = db_params

    def parse_natural_language(self, query_text):
        """
        Extracts query parameters such as year, day of week, time constraints,
        season, month, action, entity type, plus additional filters like artist,
        platform, country, mood, reason_start, exact play counts, and ordinal (nth)
        queries.
        """
        lower_query = query_text.lower()
        # Remove unsupported terms.
        for word in ["discover", "rediscover", "stop listening"]:
            lower_query = lower_query.replace(word, "")
        
        parsed = {
            "year": None,
            "day_of_week": None,
            "time_after": None,
            "time_before": None,
            "season": None,
            "month": None,
            "action": None,
            "entity_type": None,
            "limit": 5,  # default limit
            "filter_value": None,
            "platform": None,
            "country": None,
            "mood": None,
            "reason_start": None,
            "play_count": None,
            "nth": None,
            "use_count": False
        }

        # Detect a "between" time expression first.
        between_match = re.search(
            r"between\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s+and\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
            lower_query)
        if between_match:
            hour1 = int(between_match.group(1))
            period1 = between_match.group(3)
            hour2 = int(between_match.group(4))
            period2 = between_match.group(6)
            if period1 == "pm" and hour1 < 12:
                hour1 += 12
            if period2 == "pm" and hour2 < 12:
                hour2 += 12
            parsed["time_after"] = hour1
            parsed["time_before"] = hour2

        # Extract year (first occurrence)
        year_match = re.search(r"\b(20\d{2})\b", lower_query)
        if year_match:
            parsed["year"] = int(year_match.group(1))
        # If no explicit year is given but query contains "this year", use current year.
        if not parsed["year"] and "this year" in lower_query:
            parsed["year"] = datetime.now().year

        # Detect month (if a full month name is provided)
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        for m, num in month_map.items():
            if m in lower_query:
                parsed["month"] = num
                break

        # Day-of-week mapping: Sunday=0, Monday=1, etc.
        dow_map = {
            "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
            "thursday": 4, "friday": 5, "saturday": 6
        }
        for day, num in dow_map.items():
            if day in lower_query:
                parsed["day_of_week"] = num
                break

        # Time references (if not already set by "between")
        if parsed["time_after"] is None:
            after_match = re.search(r"after\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower_query)
            if after_match:
                hour = int(after_match.group(1))
                period = after_match.group(3)
                if period == "pm" and hour < 12:
                    hour += 12
                parsed["time_after"] = hour

        if parsed["time_before"] is None:
            before_match = re.search(r"before\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", lower_query)
            if before_match:
                hour = int(before_match.group(1))
                period = before_match.group(3)
                if period == "pm" and hour < 12:
                    hour += 12
                parsed["time_before"] = hour

        # Season detection.
        if "summer" in lower_query:
            parsed["season"] = "summer"
        elif "winter" in lower_query:
            parsed["season"] = "winter"
        elif "fall" in lower_query or "autumn" in lower_query:
            parsed["season"] = "fall"
        elif "spring" in lower_query:
            parsed["season"] = "spring"

        # Look for ordinal expressions for nth queries.
        ordinal_match = re.search(r"\b(\d+)(?:st|nd|rd|th)\b", lower_query)
        if ordinal_match:
            parsed["nth"] = int(ordinal_match.group(1))
            parsed["action"] = "nth"
            # Attempt to extract filter value from phrases like "50th frank ocean song"
            nth_filter = re.search(r"\d+(?:st|nd|rd|th)\s+([a-z\s]+?)\s+(song|track|album)", lower_query)
            if nth_filter:
                parsed["filter_value"] = nth_filter.group(1).strip()

        # Check for percentage query (generalized for any artist).
        if "percentage" in lower_query:
            parsed["action"] = "percentage"
            # If no explicit artist is given, try to extract one from the query.
            if not parsed.get("filter_value"):
                artist_match = re.search(r"(?:percentage.*of my)\s+([a-z\s]+?)\s+plays", lower_query)
                if artist_match:
                    parsed["filter_value"] = artist_match.group(1).strip().title()

        # For "first" queries.
        if "first listen" in lower_query or ("first" in lower_query and "listen" in lower_query):
            parsed["action"] = "first"
            filter_match = re.search(r"first listen(?:ed)? to\s+(.+?)(?:\s+from|$)", lower_query)
            if filter_match:
                filter_value = re.sub(r'[^\w\s]', '', filter_match.group(1)).strip()
                parsed["filter_value"] = filter_value
            else:
                from_match = re.search(r"from\s+(.+)", lower_query)
                if from_match:
                    parsed["filter_value"] = from_match.group(1).strip()
            if not parsed.get("filter_value"):
                first_entity_match = re.search(r"first\s+(.+?)\s+(song|track)", lower_query)
                if first_entity_match:
                    parsed["filter_value"] = first_entity_match.group(1).strip()

        # If action not yet set, determine based on keywords.
        if parsed["action"] is None:
            if "skip" in lower_query or "skipped" in lower_query:
                parsed["action"] = "skipped"
            else:
                parsed["action"] = "top"

        # Identify entity type.
        if "artist" in lower_query:
            parsed["entity_type"] = "artist"
        elif "track" in lower_query or "song" in lower_query:
            parsed["entity_type"] = "track"
        elif "album" in lower_query:
            parsed["entity_type"] = "album"
        else:
            parsed["entity_type"] = "artist"

        # Extract additional filter for non-first queries if not already set.
        if not parsed.get("filter_value"):
            artist_filter = re.search(r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", query_text)
            if artist_filter:
                parsed["filter_value"] = artist_filter.group(1).strip()
            else:
                from_filter = re.search(r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", query_text)
                if from_filter:
                    parsed["filter_value"] = from_filter.group(1).strip()
        # Additional extraction for queries like "what frank ocean song..." or "which {artist} album..."
        if not parsed.get("filter_value") and parsed["entity_type"] in ("track", "album"):
            extra_filter = re.search(r"(?:what|which)\s+([a-z]+(?:\s+[a-z]+){0,3})\s+(song|track|album)", lower_query)
            if extra_filter:
                candidate = extra_filter.group(1).strip()
                if candidate not in ["are my top", "my favorite", "my top"]:
                    parsed["filter_value"] = candidate.title()
        # If query starts with "my favorite" and no filter set, try to extract artist name.
        if "my favorite" in lower_query and not parsed.get("filter_value"):
            fav_match = re.search(r"my favorite\s+([a-z\s]+?)\s+(song|track|album)", lower_query)
            if fav_match:
                parsed["filter_value"] = fav_match.group(1).strip().title()

        # Extract platform filter.
        platforms = ["ios", "android", "spotify", "apple music", "youtube", "soundcloud", "pandora"]
        for plat in platforms:
            if plat in lower_query:
                parsed["platform"] = plat
                break

        # Extract country filter.
        countries = ["mexico", "uk", "canada", "japan", "usa"]
        for country in countries:
            if f"in {country}" in lower_query:
                parsed["country"] = country
                break

        # Extract shuffle filter.
        if "shuffle" in lower_query:
            if "not shuffle" in lower_query or "without shuffle" in lower_query:
                parsed["shuffle"] = False
            else:
                parsed["shuffle"] = True

        # Extract mood filter.
        moods = ["chill", "sad", "happy", "focus", "high-energy", "workout", "rain", "snow", "holiday", "christmas"]
        for mood in moods:
            if mood in lower_query:
                parsed["mood"] = mood
                break

        # Extract reason_start filter.
        if "playlist" in lower_query:
            parsed["reason_start"] = "playlist"
        elif "voice command" in lower_query:
            parsed["reason_start"] = "voice command"

        # Extract play count condition (e.g., "exactly 3 times").
        play_count_match = re.search(r"exactly\s+(\d+)\s+times", lower_query)
        if play_count_match:
            parsed["play_count"] = int(play_count_match.group(1))

        # Determine limit if specified.
        limit_match = re.search(r"(?:top|skipped|most listened|most played|streamed|replay|replayed|favorite|binge-listen)\s+(\d+)", lower_query)
        if limit_match:
            limit_val = int(limit_match.group(1))
            parsed["limit"] = min(limit_val, 20)
        else:
            alt_limit_match = re.search(r"what\s+(\d+)\s+(tracks|albums|artists|songs)", lower_query)
            if alt_limit_match:
                limit_val = int(alt_limit_match.group(1))
                parsed["limit"] = min(limit_val, 20)

        # If no explicit numeric limit is provided, check if query implies a singular result.
        if not re.search(r"(?:top|skipped|most listened|most played|streamed|replay|replayed|favorite|binge-listen)\s+\d+", lower_query):
            if parsed["entity_type"] == "track" and re.search(r"\bsong\b", query_text, re.IGNORECASE) and not re.search(r"\bsongs\b", query_text, re.IGNORECASE):
                parsed["limit"] = 1
            elif parsed["entity_type"] == "album" and re.search(r"\balbum\b", query_text, re.IGNORECASE) and not re.search(r"\balbums\b", query_text, re.IGNORECASE):
                parsed["limit"] = 1
            elif parsed["entity_type"] == "artist" and re.search(r"\bartist\b", query_text, re.IGNORECASE) and not re.search(r"\bartists\b", query_text, re.IGNORECASE):
                parsed["limit"] = 1

        # If 'favorite' is in the query without a number, default to limit 1.
        if "favorite" in lower_query and not re.search(r"(?:top|skipped|most listened|most played|streamed|replay|replayed)\s+\d+", lower_query):
            parsed["limit"] = 5

        # Detect if query wants a count-based top ranking instead of total ms.
        if "most times" in lower_query or "most frequently" in lower_query:
            parsed["use_count"] = True

        return parsed

    def build_sql_query(self, parsed):
        """
        Constructs a parameterized SQL query using the parsed parameters.
        Builds dynamic WHERE clauses (including new filters) and switches the query
        structure based on the action (first, percentage, nth, last, top, skipped).
        """
        base_join = (
            "FROM listening_history lh "
            "JOIN tracks t ON lh.track_id = t.track_id "
            "JOIN albums a ON t.album_id = a.album_id "
            "JOIN artists ar ON a.artist_id = ar.artist_id "
        )
        where_clauses = []
        params = []

        # Common filters.
        if parsed["year"]:
            where_clauses.append("EXTRACT(YEAR FROM lh.timestamp) = %s")
            params.append(parsed["year"])
        if parsed["day_of_week"] is not None:
            where_clauses.append("EXTRACT(DOW FROM lh.timestamp) = %s")
            params.append(parsed["day_of_week"])
        if parsed["time_after"] is not None:
            where_clauses.append("EXTRACT(HOUR FROM lh.timestamp) >= %s")
            params.append(parsed["time_after"])
        if parsed["time_before"] is not None:
            where_clauses.append("EXTRACT(HOUR FROM lh.timestamp) < %s")
            params.append(parsed["time_before"])
        if parsed["month"] is not None:
            where_clauses.append("EXTRACT(MONTH FROM lh.timestamp) = %s")
            params.append(parsed["month"])
        elif parsed["season"]:
            if parsed["season"] == "summer":
                where_clauses.append("EXTRACT(MONTH FROM lh.timestamp) IN (6, 7, 8)")
            elif parsed["season"] == "winter":
                where_clauses.append("EXTRACT(MONTH FROM lh.timestamp) IN (12, 1, 2)")
            elif parsed["season"] == "fall":
                where_clauses.append("EXTRACT(MONTH FROM lh.timestamp) IN (9, 10, 11)")
            elif parsed["season"] == "spring":
                where_clauses.append("EXTRACT(MONTH FROM lh.timestamp) IN (3, 4, 5)")
        if parsed.get("filter_value"):
            where_clauses.append("ar.artist_name ILIKE %s")
            params.append(f"%{parsed['filter_value']}%")
        if parsed.get("platform"):
            where_clauses.append("lh.platform ILIKE %s")
            params.append(f"%{parsed['platform']}%")
        if parsed.get("country"):
            where_clauses.append("lh.country ILIKE %s")
            params.append(f"%{parsed['country']}%")
        if parsed.get("shuffle") is not None:
            where_clauses.append("lh.shuffle = %s")
            params.append(parsed["shuffle"])
        if parsed.get("mood"):
            where_clauses.append("lh.moods ILIKE %s")
            params.append(f"%{parsed['mood']}%")
        if parsed.get("reason_start"):
            where_clauses.append("lh.reason_start ILIKE %s")
            params.append(f"%{parsed['reason_start']}%")
        
        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # Build query based on action.
        if parsed["action"] == "first":
            if parsed["entity_type"] == "artist":
                select_fields = "ar.artist_name AS entity, lh.timestamp AS first_listen"
            elif parsed["entity_type"] == "track":
                select_fields = "t.track_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS first_listen"
            elif parsed["entity_type"] == "album":
                select_fields = "a.album_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS first_listen"
            else:
                select_fields = "ar.artist_name AS entity, lh.timestamp AS first_listen"
            sql = (
                f"SELECT {select_fields} "
                f"{base_join} "
                f"{where_clause} "
                f"ORDER BY lh.timestamp ASC "
                f"LIMIT 1;"
            )
            return (sql, params)
        elif parsed["action"] == "percentage":
            # Calculate percentage of skipped plays.
            sql = (
                f"SELECT COUNT(*) FILTER (WHERE lh.skipped = TRUE) AS skipped_count, "
                f"COUNT(*) AS total_count "
                f"{base_join} "
                f"{where_clause};"
            )
            return (sql, params)
        elif parsed["action"] == "nth" and parsed.get("nth"):
            if parsed["entity_type"] == "artist":
                select_fields = "ar.artist_name AS entity, lh.timestamp AS listen_time"
            elif parsed["entity_type"] == "track":
                select_fields = "t.track_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS listen_time"
            elif parsed["entity_type"] == "album":
                select_fields = "a.album_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS listen_time"
            else:
                select_fields = "ar.artist_name AS entity, lh.timestamp AS listen_time"
            offset_val = max(parsed["nth"] - 1, 0)
            sql = (
                f"SELECT {select_fields} "
                f"{base_join} "
                f"{where_clause} "
                f"ORDER BY lh.timestamp ASC "
                f"OFFSET %s LIMIT 1;"
            )
            params.append(offset_val)
            return (sql, params)
        elif parsed["action"] == "last":
            # Query for the last played record.
            if parsed["entity_type"] == "artist":
                select_fields = "ar.artist_name AS entity, lh.timestamp AS listen_time"
            elif parsed["entity_type"] == "track":
                select_fields = "t.track_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS listen_time"
            elif parsed["entity_type"] == "album":
                select_fields = "a.album_name AS entity, ar.artist_name AS sub_entity, lh.timestamp AS listen_time"
            else:
                select_fields = "ar.artist_name AS entity, lh.timestamp AS listen_time"
            sql = (
                f"SELECT {select_fields} "
                f"{base_join} "
                f"{where_clause} "
                f"ORDER BY lh.timestamp DESC "
                f"LIMIT 1;"
            )
            return (sql, params)
        else:
            # For "skipped" and "top" actions.
            if parsed["entity_type"] == "artist":
                group_clause = "ar.artist_name"
                select_fields = "ar.artist_name AS entity"
            elif parsed["entity_type"] == "track":
                group_clause = "t.track_name, ar.artist_name"
                select_fields = "t.track_name AS entity, ar.artist_name AS sub_entity"
            elif parsed["entity_type"] == "album":
                group_clause = "a.album_name, ar.artist_name"
                select_fields = "a.album_name AS entity, ar.artist_name AS sub_entity"
            else:
                group_clause = "ar.artist_name"
                select_fields = "ar.artist_name AS entity"
            effective_limit = parsed["limit"] * 2
            having_clause = ""
            if parsed.get("play_count") is not None:
                having_clause = "HAVING COUNT(*) = %s"
            if parsed["action"] == "skipped":
                sql = (
                    f"SELECT {select_fields}, COUNT(*) AS skip_count "
                    f"{base_join} "
                    f"{where_clause} "
                    f"GROUP BY {group_clause} "
                )
                if having_clause:
                    sql += having_clause
                    params.append(parsed["play_count"])
                sql += f" ORDER BY skip_count DESC LIMIT %s;"
            elif parsed["action"] == "top":
                if parsed.get("use_count"):
                    sql = (
                        f"SELECT {select_fields}, COUNT(*) AS play_count "
                        f"{base_join} "
                        f"{where_clause} "
                        f"GROUP BY {group_clause} "
                        f"ORDER BY play_count DESC LIMIT %s;"
                    )
                else:
                    sql = (
                        f"SELECT {select_fields}, SUM(lh.ms_played) AS total_ms "
                        f"{base_join} "
                        f"{where_clause} "
                        f"GROUP BY {group_clause} "
                        f"ORDER BY total_ms DESC LIMIT %s;"
                    )
            else:
                sql = "SELECT %s AS error_msg;"
                params = ["No recognized action in your query."]
                return (sql, params)
            params.append(effective_limit)
            return (sql, params)

    def ordinal(self, n):
        """Converts an integer n into its ordinal string (e.g., 1 -> '1st')."""
        n = int(n)
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return str(n) + suffix

    def format_response(self, parsed, results):
        """
        Converts raw SQL result data into an HTML response.
        Handles special responses for 'first', 'percentage', 'nth', 'last' queries,
        and for top/skipped actions builds a header plus an unordered list.
        """
        if parsed["action"] == "first":
            if not results:
                return "<h2>No matching record found for your first listen query.</h2>"
            row = results[0]
            ts = row[-1]
            try:
                ts_formatted = ts.strftime("%Y-%m-%d %I:%M %p")
            except Exception:
                ts_formatted = str(ts)
            if parsed["entity_type"] == "artist":
                entity = row[0]
                html_response = f"<h2>You first listened to {entity} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "track":
                track = row[0]
                artist = row[1]
                html_response = f"<h2>You first listened to {track} by {artist} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "album":
                album = row[0]
                artist = row[1]
                html_response = f"<h2>You first listened to {album} by {artist} on {ts_formatted}.</h2>"
            else:
                html_response = f"<h2>Your first listen was on {ts_formatted}.</h2>"
            return html_response
        elif parsed["action"] == "percentage":
            if not results or results[0][1] == 0:
                return "<h2>No data available to calculate percentage.</h2>"
            skipped_count, total_count = results[0]
            percentage = (skipped_count / total_count) * 100 if total_count else 0
            html_response = f"<h2>{percentage:.2f}% of my {parsed.get('filter_value', '')} plays were skipped.</h2>"
            return html_response
        elif parsed["action"] == "nth" and parsed.get("nth"):
            if not results:
                ordinal_val = f"{parsed['nth']}"
                html_response = f"<h2>No matching record found for your {ordinal_val} streamed track query.</h2>"
                return html_response
            row = results[0]
            ts = row[-1]
            try:
                ts_formatted = ts.strftime("%Y-%m-%d %I:%M %p")
            except Exception:
                ts_formatted = str(ts)
            ordinal_str = self.ordinal(parsed["nth"])
            if parsed["entity_type"] == "artist":
                entity = row[0]
                html_response = f"<h2>Your {ordinal_str} streamed artist was {entity} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "track":
                track = row[0]
                artist = row[1]
                html_response = f"<h2>Your {ordinal_str} streamed track was {track} by {artist} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "album":
                album = row[0]
                artist = row[1]
                html_response = f"<h2>Your {ordinal_str} streamed album was {album} by {artist} on {ts_formatted}.</h2>"
            else:
                html_response = f"<h2>Your {ordinal_str} streamed record was on {ts_formatted}.</h2>"
            return html_response
        elif parsed["action"] == "last":
            if not results:
                return "<h2>No matching record found for your last played query.</h2>"
            row = results[0]
            ts = row[-1]
            try:
                ts_formatted = ts.strftime("%Y-%m-%d %I:%M %p")
            except Exception:
                ts_formatted = str(ts)
            if parsed["entity_type"] == "artist":
                entity = row[0]
                html_response = f"<h2>Your last played artist was {entity} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "track":
                track = row[0]
                artist = row[1]
                html_response = f"<h2>Your last played track was {track} by {artist} on {ts_formatted}.</h2>"
            elif parsed["entity_type"] == "album":
                album = row[0]
                artist = row[1]
                html_response = f"<h2>Your last played album was {album} by {artist} on {ts_formatted}.</h2>"
            else:
                html_response = f"<h2>Your last played record was on {ts_formatted}.</h2>"
            return html_response
        else:
            # For "top" and "skipped" actions.
            conditions = []
            if parsed["day_of_week"] is not None:
                day_names = {0: "Sundays", 1: "Mondays", 2: "Tuesdays", 3: "Wednesdays",
                             4: "Thursdays", 5: "Fridays", 6: "Saturdays"}
                conditions.append(f"on {day_names.get(parsed['day_of_week'], '')}")
            if parsed["year"]:
                conditions.append(f"in {parsed['year']}")
            if parsed["time_after"] is not None and parsed["time_before"] is None:
                conditions.append(f"after {self.format_hour(parsed['time_after'])}")
            if parsed["time_before"] is not None and parsed["time_after"] is None:
                conditions.append(f"before {self.format_hour(parsed['time_before'])}")
            if parsed["time_after"] is not None and parsed["time_before"] is not None:
                conditions.append(f"between {self.format_hour(parsed['time_after'])} and {self.format_hour(parsed['time_before'])}")
            if parsed["month"] is not None:
                month_names = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
                conditions.append(f"in {month_names.get(parsed['month'], '')}")
            elif parsed["season"]:
                conditions.append(f"during {parsed['season']}")
            if parsed.get("platform"):
                conditions.append(f"on {parsed['platform'].capitalize()}")
            if parsed.get("country"):
                conditions.append(f"in {parsed['country'].capitalize()}")
            if parsed.get("mood"):
                conditions.append(f"with a {parsed['mood']} mood")
            if parsed.get("reason_start"):
                conditions.append(f"started via {parsed['reason_start']}")
            condition_str = " " + " ".join(conditions) if conditions else ""
            entity_map = {"artist": "artists", "track": "songs", "album": "albums"}
            action_text = "most skipped" if parsed["action"] == "skipped" else "top"
            entity_text = entity_map.get(parsed["entity_type"], "artists")
            header_text = f"Your {action_text} {entity_text}{condition_str}:"

            def is_valid_row(row, entity_type):
                if entity_type == "artist":
                    return row[0].strip().lower() != "unknown artist"
                elif entity_type == "track":
                    return (row[0].strip().lower() != "unknown track") and (row[1].strip().lower() != "unknown artist")
                elif entity_type == "album":
                    return (row[0].strip().lower() != "unknown album") and (row[1].strip().lower() != "unknown artist")
                return True

            filtered_results = [row for row in results if is_valid_row(row, parsed["entity_type"])]
            valid_results = filtered_results[:parsed["limit"]]

            html_response = f"<h2>{header_text}</h2><ul class='result-list'>"
            if parsed["entity_type"] == "track":
                for row in valid_results:
                    html_response += f"<li><span class='track-name'>{row[0]}</span> by <span class='artist-name'>{row[1]}</span></li>"
            elif parsed["entity_type"] == "album":
                for row in valid_results:
                    html_response += f"<li><span class='album-name'>{row[0]}</span> by <span class='artist-name'>{row[1]}</span></li>"
            else:  # artist
                for row in valid_results:
                    html_response += f"<li><span class='artist-name'>{row[0]}</span></li>"
            html_response += "</ul>"
            return html_response

    def join_items(self, items):
        """Joins list items using commas and 'and' before the last item."""
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + ", and " + items[-1]

    def format_hour(self, hour):
        """Converts a 24-hour integer into a 12-hour format with AM/PM."""
        suffix = "AM"
        if hour >= 12:
            suffix = "PM"
            if hour > 12:
                hour -= 12
        if hour == 0:
            hour = 12
        return f"{hour}{suffix}"

    def execute_query(self, query_text):
        """
        Parses the user query, builds and executes the SQL,
        and returns both the parsed parameters and raw results.
        """
        parsed = self.parse_natural_language(query_text)
        sql_query, params = self.build_sql_query(parsed)
        logging.info("Executing SQL: %s with params %s", sql_query, params)
        try:
            with psycopg2.connect(**self.db_params) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_query, params)
                    results = cur.fetchall()
        except Exception as e:
            logging.error("Query execution error: %s", e)
            results = [("Error executing query", str(e))]
        return parsed, results

if __name__ == "__main__":
    db_params = {
        "dbname": os.getenv("DB_NAME", "musicmuse_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASS"),
        "host": "localhost",
        "port": 5432
    }
    music_muse = MusicMuse(db_params)
    # Example queries
    queries = [
        "When did I first listen to Frank Ocean?",
        "Which artists did I skip the most on Thursdays in 2022?",
        "What are my top songs to listen to after 8PM?",
        "What were my top 10 tracks during the summer of 2023?",
    ]
    for q in queries:
        parsed, result = music_muse.execute_query(q)
        response = music_muse.format_response(parsed, result)
        print("Query:", q)
        print("Response:", response)