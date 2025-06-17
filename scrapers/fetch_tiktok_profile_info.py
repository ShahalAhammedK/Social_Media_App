import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps, even if not heavily used here
from tabulate import tabulate # For pretty printing tables
import re # For extracting username from URLs

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
# TikTok API
RAPIDAPI_KEY_TIKTOK = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key for TikTok
RAPIDAPI_HOST_TIKTOK = "tiktok-api6.p.rapidapi.com" # Updated API host for this specific endpoint

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

def fetch_tiktok_profile_info(profile_identifier): # Renamed 'username' to 'profile_identifier'
    """
    Fetches detailed information for a TikTok user profile using their username or URL.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST_TIKTOK)
    
    # Determine if the identifier is a URL or a username
    username_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from standard TikTok profile URLs
        match = re.search(r'(?:tiktok\.com\/@)([a-zA-Z0-9_\.]+)', profile_identifier)
        if match:
            username_for_api = match.group(1).replace('/', '') # Clean up potential trailing slash
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return None

    try:
        # Properly encode the username for the GET request URL
        encoded_username = urllib.parse.quote(username_for_api)

        # Request user details using the new GET endpoint structure
        endpoint = f"/user/details?username={encoded_username}"
        conn.request("GET", endpoint, headers=headers_tiktok)

        # Get response
        res = conn.getresponse()
        data = res.read()

        # Decode the raw API response and parse the JSON
        raw_response_str = data.decode("utf-8")
        response_json = json.loads(raw_response_str)

        # Check for a fundamental key to indicate valid data from the API response
        if response_json.get('username'):
            # Extract profile information using safe_get for robustness
            profile_username = safe_get(response_json, 'username')
            nickname = safe_get(response_json, 'nickname')
            follower_count = safe_get(response_json, 'followers')
            following_count = safe_get(response_json, 'following')
            total_likes_received = safe_get(response_json, 'total_heart')
            posts_count = safe_get(response_json, 'total_videos')

            # Construct a basic profile URL
            profile_url = f"https://www.tiktok.com/@{profile_username}" if profile_username != "N/A" else "N/A"

            return {
                "Username": profile_username,
                "Nickname": nickname,
                "Profile Followers": str(follower_count),
                "Following Count": str(following_count),
                "Total Likes Received": str(total_likes_received),
                "Posts Count": str(posts_count),
                "Profile URL": profile_url
            }
        else:
            # If 'username' key is not found at the root, assume it's an error response
            error_message = safe_get(response_json, 'message', safe_get(response_json, 'error', safe_get(response_json, 'reason', 'Unknown error')))
            print(f"API returned an error for {profile_identifier}: {error_message}") # Use original identifier for error
            return None

    except json.JSONDecodeError:
        print(f"Error for {profile_identifier}: Could not decode JSON response. The API response might not be valid JSON.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for {profile_identifier}: {e}")
        return None
    finally:
        # Ensure the connection is closed
        conn.close()

# --- Example Usage ---
if __name__ == "__main__":
    # Define multiple TikTok usernames or profile URLs in a list
    tiktok_identifiers_to_process = [
        "Mrwhosetheboss",
        "https://www.tiktok.com/@therock", # Added a URL example
        "charlidamelio",
        "nonexistentuser12345", # Example of a non-existent user
        "https://www.tiktok.com/@arianagrande" # Another URL example
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Username",
        "Nickname",
        "Profile Followers",
        "Following Count",
        "Total Likes Received",
        "Posts Count",
        "Profile URL"
    ]

    print("--- Processing TikTok Profiles ---")

    for identifier in tiktok_identifiers_to_process:
        print(f"\nProcessing Profile: {identifier}")
        profile_details = fetch_tiktok_profile_info(identifier) # Use 'identifier' here
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
        print("\n--- TikTok Profile Basic Information Table ---")
        print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("--------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified TikTok usernames/URLs.")
