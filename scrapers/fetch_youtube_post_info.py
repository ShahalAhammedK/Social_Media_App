import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
from tabulate import tabulate # For pretty printing tables
import re # For extracting video ID from URLs
from langdetect import detect, DetectorFactory # Import language detection library

# Set seed for langdetect to ensure consistent results (optional but good for reproducibility)
DetectorFactory.seed = 0

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'"
# or "ModuleNotFoundError: No module named 'langdetect'",
# you need to install these libraries. Open your terminal or command prompt and run:
# pip install tabulate langdetect

# --- Configuration ---
# YouTube API
RAPIDAPI_KEY_YOUTUBE = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key for YouTube
RAPIDAPI_HOST_YOUTUBE = "youtube-v38.p.rapidapi.com"

headers_youtube = {
    'x-rapidapi-key': RAPIDAPI_KEY_YOUTUBE,
    'x-rapidapi-host': RAPIDAPI_HOST_YOUTUBE
}

def safe_get(data, path, default="N/A"):
    """
    Safely retrieves a nested value from a dictionary using a dot-separated path.
    Returns default if any key in the path is not found or if an intermediate value
    is not a dictionary.
    """
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, {})
        else:
            return default # Path segment not a dict, cannot go further
    return value if value else default # Return actual value or default if empty/None

def format_timestamp(ts, include_time=False):
    """
    Formats a Unix timestamp (or date string if already formatted) into a readable datetime string.
    Handles 'N/A' or invalid timestamps gracefully.
    If include_time is True, returns date and time.
    """
    if ts == "N/A" or not ts:
        return "N/A"
    try:
        # Check if it's a Unix timestamp (int) or already a string date
        if isinstance(ts, int) or (isinstance(ts, str) and ts.isdigit()):
            ts_int = int(ts)
            dt_object = datetime.utcfromtimestamp(ts_int)
        else:
            # Assume it's already a date string in 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' format
            # datetime.fromisoformat can handle various ISO 8601 formats
            dt_object = datetime.fromisoformat(ts.replace('Z', '+00:00')) # Handle 'Z' for UTC
            
        if include_time:
            return dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            return dt_object.strftime('%Y-%m-%d')
    except (ValueError, TypeError, Exception):
        return "Invalid timestamp"

def fetch_youtube_post_info(video_url): # Renamed function
    """
    Fetches basic details for a given YouTube video URL.
    Extracts the video ID from the URL and uses it to query the API.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST_YOUTUBE)
    
    video_id = None
    # Extract video ID from the URL using regular expressions
    match = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', video_url)
    if match:
        video_id = match.group(1)
    else:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return None # Return None if ID extraction fails

    try:
        # Properly encode the video ID for the GET request URL
        encoded_video_id = urllib.parse.quote(video_id, safe='')

        # Request video details using the GET endpoint structure
        endpoint = f"/video/details/?id={encoded_video_id}&hl=en&gl=US"
        conn.request("GET", endpoint, headers=headers_youtube)

        # Get response
        res = conn.getresponse()
        data = res.read()

        # Decode the raw API response and parse the JSON
        raw_response_str = data.decode("utf-8")
        response_json = json.loads(raw_response_str)

        # Check if the API call returned valid data (e.g., 'videoId' or 'title')
        if response_json.get('videoId') or response_json.get('title'):
            # Extract statistics and details from the provided JSON structure
            stats_info = safe_get(response_json, 'stats', {})
            views_count = safe_get(stats_info, 'views')
            likes_count = safe_get(stats_info, 'likes')
            comments_count = safe_get(stats_info, 'comments')

            author_info = safe_get(response_json, 'author', {})
            channel_name = safe_get(author_info, 'title')

            # Extract channel ID to construct Channel URL
            channel_id = safe_get(author_info, 'channelId')
            channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id != "N/A" else "N/A"

            # Duration is directly available in 'lengthSeconds'
            video_duration_seconds = safe_get(response_json, 'lengthSeconds')

            # Published date is directly available in 'publishedDate'
            published_date_raw = safe_get(response_json, 'publishedDate')
            published_date_formatted = format_timestamp(published_date_raw, include_time=True) # Full timestamp

            # Extract the video description
            video_description = safe_get(response_json, 'description')

            # Detect language of the description
            detected_description_language = "N/A" # Default if detection fails
            if video_description and len(video_description.strip()) > 0 and video_description != "N/A":
                try:
                    detected_description_language = detect(video_description)
                except Exception as e:
                    detected_description_language = "Undetectable"
                    print(f"  Warning: Could not detect language for video {video_id} description: {e}")

            return {
                "Views": str(views_count),
                "Likes": str(likes_count),
                "Comments": str(comments_count),
                "Video URL": video_url, # Use the original full URL for the output
                "Channel Name": channel_name,
                "Channel URL": channel_url,
                "Video Duration (seconds)": str(video_duration_seconds),
                "Published Date (UTC)": published_date_formatted,
                "Description Language": detected_description_language
            }
        else:
            # Report API specific error message if available
            error_message = safe_get(response_json, 'message', safe_get(response_json, 'error', 'No specific error message from API'))
            print(f"API returned no valid data or an error for Video ID {video_id}: {error_message}")
            return None

    except json.JSONDecodeError:
        print(f"Error for Video ID {video_id}: Could not decode JSON response. The API response might not be valid JSON.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for Video ID {video_id}: {e}")
        return None
    finally:
        # Ensure the connection is closed
        conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    # Define multiple YouTube Video URLs in a list
    youtube_video_urls_to_process = [
        "https://youtu.be/HvoBci_GC8A?si=BFNrECRroBd_nWB2",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Rick Astley - Never Gonna Give You Up
        "https://www.youtube.com/watch?v=kYtGl1JXzHg" # Example with comments
    ]

    # List to store all video data rows for tabulate display
    collected_video_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Views",
        "Likes",
        "Comments",
        "Video URL",
        "Channel Name",
        "Channel URL",
        "Video Duration (seconds)",
        "Published Date (UTC)",
        "Description Language"
    ]

    print("--- Processing YouTube Videos ---")

    for url in youtube_video_urls_to_process:
        print(f"\nProcessing URL: {url}")
        video_details = fetch_youtube_post_info(url) # Updated function call
        if video_details:
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [video_details.get(header, 'N/A') for header in output_headers]
            collected_video_rows_for_output.append(row_data_list)
            print("Successfully extracted basic video details and detected description language.")
        else:
            print(f"Failed to retrieve video details for {url}.")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_video_rows_for_output:
        print("\n--- YouTube Video Basic Information Table ---")
        print(tabulate(collected_video_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("-------------------------------------------")
    else:
        print("\nNo basic video details collected for the specified YouTube videos.")
