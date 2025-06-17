import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
from tabulate import tabulate # For pretty printing tables

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
# TikTok API
RAPIDAPI_KEY_TIKTOK = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key for TikTok
RAPIDAPI_HOST_TIKTOK = "tiktok89.p.rapidapi.com"

headers_tiktok = {
    'x-rapidapi-key': RAPIDAPI_KEY_TIKTOK,
    'x-rapidapi-host': RAPIDAPI_HOST_TIKTOK
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
    Formats a Unix timestamp into a readable datetime string (date only by default).
    Handles 'N/A' or invalid timestamps gracefully.
    If include_time is True, returns date and time.
    """
    if ts == "N/A" or not ts:
        return "N/A"
    try:
        ts_int = int(ts)
        # Convert Unix timestamp (seconds) to UTC datetime string
        if include_time:
            return datetime.utcfromtimestamp(ts_int).strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            return datetime.utcfromtimestamp(ts_int).strftime('%Y-%m-%d')
    except Exception:
        return "Invalid timestamp"

def fetch_tiktok_post_info(video_url): # Renamed function
    """
    Fetches basic details for a given TikTok video URL using the TikTok API.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST_TIKTOK)
    
    try:
        encoded_url = urllib.parse.quote(video_url, safe='')
        endpoint = f"/tiktok?link={encoded_url}"
        conn.request("GET", endpoint, headers=headers_tiktok)
        res = conn.getresponse()
        data = res.read()
        raw_response_str = data.decode("utf-8")
        response_json = json.loads(raw_response_str)

        if response_json.get('ok'):
            author_info = response_json.get('author', {})
            author_username = safe_get(author_info, 'unique_id')

            statistics_info = response_json.get('statistics', {})
            play_count = safe_get(statistics_info, 'play_count')
            like_count = safe_get(statistics_info, 'digg_count')
            comment_count = safe_get(statistics_info, 'comment_count')
            share_count = safe_get(statistics_info, 'share_count')

            video_details = response_json.get('video', {})
            raw_video_duration = safe_get(video_details, 'duration')
            
            video_duration_seconds = 'N/A'
            if isinstance(raw_video_duration, (int, float)):
                # Heuristic: If the raw duration is a large number (e.g., > 1000), it's likely in milliseconds
                # and needs conversion to seconds. Otherwise, assume it's already in seconds.
                if raw_video_duration > 1000 and raw_video_duration % 1000 == 0:
                    video_duration_seconds = raw_video_duration / 1000
                else:
                    video_duration_seconds = raw_video_duration
            
            caption_language = safe_get(response_json, 'desc_language')
            video_share_url = safe_get(response_json, 'share_url')

            create_time_unix = safe_get(response_json, 'create_time')
            create_time_utc = format_timestamp(create_time_unix, include_time=True)

            return {
                "Views": str(play_count),
                "Likes": str(like_count),
                "Comments": str(comment_count),
                "Shares": str(share_count),
                "Video URL": video_share_url,
                "Author Username": author_username,
                "Video Duration (Milli seconds)": str(video_duration_seconds),
                "Video Language": caption_language,
                "Caption Language": caption_language, # Often the same field for TikTok
                "Created Date (UTC)": create_time_utc
            }
        else:
            error_message = response_json.get('message', response_json.get('reason', 'Unknown error'))
            print(f"TikTok API returned an error for {video_url}: {error_message}")
            return None

    except json.JSONDecodeError:
        print(f"Error for {video_url}: Could not decode JSON response from TikTok API.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for TikTok video {video_url}: {e}")
        return None
    finally:
        conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    # Define multiple TikTok video URLs in a list
    tiktok_video_urls = [
        "https://www.tiktok.com/@malik.usama.76/video/7481587188128337159",
        # Add more TikTok video URLs here if needed
        # "https://www.tiktok.com/@exampleuser/video/1234567890123456789" 
    ]

    # List to store all video data rows for tabulate display
    collected_video_rows = []

    # Define the headers for the TikTok video details
    output_headers = [
        "Views",
        "Likes",
        "Comments",
        "Shares",
        "Video URL",
        "Author Username",
        "Video Duration (seconds)",
        "Video Language",
        "Caption Language",
        "Created Date (UTC)"
    ]

    print("--- Processing TikTok Videos ---")

    for video_url in tiktok_video_urls:
        print(f"\nProcessing URL: {video_url}")
        video_details = fetch_tiktok_post_info(video_url) # Updated function call
        if video_details:
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [video_details.get(header, 'N/A') for header in output_headers]
            collected_video_rows.append(row_data_list)
            print("Successfully extracted basic video details.")
        else:
            print(f"Failed to retrieve video details for {video_url}.")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_video_rows:
        print("\n--- TikTok Video Basic Information Table ---")
        print(tabulate(collected_video_rows, headers=output_headers, tablefmt="fancy_grid"))
        print("------------------------------------------")
    else:
        print("\nNo basic video details collected for the specified TikTok videos.")
