import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
from tabulate import tabulate # For pretty printing tables
import re # Essential for extracting channel ID/handle from URLs

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
# YouTube API for Channel Details (using the specified host)
RAPIDAPI_KEY_YOUTUBE_CHANNEL = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key
RAPIDAPI_HOST_YOUTUBE_CHANNEL = "youtube-shorts-sounds-songs-api.p.rapidapi.com"

headers_youtube_channel = {
    'x-rapidapi-key': RAPIDAPI_KEY_YOUTUBE_CHANNEL,
    'x-rapidapi-host': RAPIDAPI_HOST_YOUTUBE_CHANNEL
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
        # This API's timestamps might be in various formats, or not needed for channel details
        # Keeping for consistency with other utils, but it might not be directly applicable
        # to channel published dates/times from this specific API.
        if isinstance(ts, int) or (isinstance(ts, str) and ts.isdigit()):
            ts_int = int(ts)
            dt_object = datetime.utcfromtimestamp(ts_int)
        else:
            dt_object = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            
        if include_time:
            return dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            return dt_object.strftime('%Y-%m-%d')
    except (ValueError, TypeError, Exception):
        return "Invalid timestamp"

def fetch_youtube_profile_info(channel_identifier):
    """
    Fetches detailed information for a YouTube channel using its handle (e.g., "@TeamFalconsGG") or URL.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST_YOUTUBE_CHANNEL)
    
    # Determine if the identifier is a URL or a handle
    # If it's a URL, extract the channel handle/ID
    handle_for_api = channel_identifier
    if channel_identifier.startswith("http"):
        # Regex to extract handle (starts with @) or channel ID (UC...) from various YouTube URL formats
        # Matches @handle, /channel/UCid, or /c/legacyname
        match_handle = re.search(r'(?:youtube\.com\/(?:@|channel\/|c\/))([a-zA-Z0-9_-]+)', channel_identifier)
        if match_handle:
            handle_for_api = match_handle.group(1)
            # Prepend '@' if it looks like a handle but doesn't have it (e.g., extracted "marquesbrownlee")
            if not handle_for_api.startswith('@') and not handle_for_api.startswith('UC'):
                 handle_for_api = '@' + handle_for_api
        else:
            print(f"Error: Could not extract channel handle/ID from URL: {channel_identifier}. Skipping.")
            return None

    try:
        # Properly encode the channel handle for the GET request URL
        encoded_handle = urllib.parse.quote(handle_for_api, safe='')

        # Request channel details using the GET endpoint structure
        # The API supports fetching by handle or channel ID directly in the path
        endpoint = f"/channel/handle/{encoded_handle}"
        conn.request("GET", endpoint, headers=headers_youtube_channel)

        # Get response
        res = conn.getresponse()
        data = res.read()

        # Decode the raw API response and parse the JSON
        raw_response_str = data.decode("utf-8")
        response_json = json.loads(raw_response_str)

        # Check if the JSON response contains expected data (e.g., 'id' or 'name')
        if safe_get(response_json, 'id') or safe_get(response_json, 'name'):
            channel_handle_val = safe_get(response_json, 'handle', handle_for_api) # Use original or extracted if not in response
            channel_name = safe_get(response_json, 'name')
            subscribers = safe_get(response_json, 'subscribers')
            total_videos = safe_get(response_json, 'videoCount')
            total_views = safe_get(response_json, 'viewCount')

            # Construct YouTube channel URL from the handle
            channel_url = f"https://www.youtube.com/{channel_handle_val}" if channel_handle_val != "N/A" else "N/A"

            return {
                "Channel Handle": channel_handle_val,
                "Channel Name": channel_name,
                "Subscribers": str(subscribers),
                "Total Videos": str(total_videos),
                "Total Channel Views": str(total_views),
                "Channel URL": channel_url
            }
        else:
            # If expected keys are not found, assume it's an error response
            print(f"API returned no valid data for {channel_identifier}. Full response: {raw_response_str}")
            return None

    except json.JSONDecodeError:
        print(f"Error for {channel_identifier}: Could not decode JSON response. The API response might not be valid JSON.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for {channel_identifier}: {e}")
        return None
    finally:
        # Ensure the connection is closed
        conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    # Define multiple YouTube channel handles or URLs in a list
    youtube_channels_to_process = [
        "@TeamFalconsGG",
        "https://www.youtube.com/@marquesbrownlee", # URL with @handle
        "https://www.youtube.com/channel/UC-xV7_0S4s8Lw_uI_y4XfJQ", # URL with channel ID
        "https://www.youtube.com/c/LinusTechTips", # URL with /c/ legacy name
        "@nonexistentchannel123456" # Example of a non-existent channel handle
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Channel Handle",
        "Channel Name",
        "Subscribers",
        "Total Videos",
        "Total Channel Views",
        "Channel URL"
    ]

    print("--- Processing YouTube Channels ---")

    for identifier in youtube_channels_to_process:
        print(f"\nProcessing Channel: {identifier}")
        profile_details = fetch_youtube_profile_info(identifier)
        if profile_details:
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [profile_details.get(header, 'N/A') for header in output_headers]
            collected_profile_rows_for_output.append(row_data_list)
            print("Successfully extracted basic profile details.")
        else:
            print(f"Failed to retrieve profile details for {identifier}.")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_profile_rows_for_output:
        print("\n--- YouTube Channel Basic Information Table ---")
        print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("---------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified YouTube channels.")
