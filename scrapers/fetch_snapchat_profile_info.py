import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
from tabulate import tabulate # For pretty printing tables
import re # Essential for extracting username from URLs

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
# Snapchat API
RAPIDAPI_KEY_SNAPCHAT = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key for Snapchat
RAPIDAPI_HOST_SNAPCHAT = "snapchat-scraper2.p.rapidapi.com"

headers_snapchat = {
    'x-rapidapi-key': RAPIDAPI_KEY_SNAPCHAT,
    'x-rapidapi-host': RAPIDAPI_HOST_SNAPCHAT
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

def fetch_snapchat_profile_info(profile_identifier): # Changed parameter name
    """
    Fetches detailed information for a Snapchat profile using its username or URL.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST_SNAPCHAT)
    
    # Determine if the identifier is a URL or a username
    username_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from Snapchat profile URLs (e.g., snapchat.com/add/username)
        match = re.search(r'(?:snapchat\.com\/add\/)([a-zA-Z0-9_\-]+)', profile_identifier)
        if match:
            username_for_api = match.group(1)
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return None

    try:
        # Properly encode the username for the GET request URL
        encoded_username = urllib.parse.quote(username_for_api, safe='')

        # Request profile details using the GET endpoint structure
        endpoint = f"/api/v1/users/detail?username={encoded_username}"
        conn.request("GET", endpoint, headers=headers_snapchat)

        # Get response
        res = conn.getresponse()
        data = res.read()

        # Decode the raw API response
        raw_response_str = data.decode("utf-8")

        # Parse the JSON response
        response_json = json.loads(raw_response_str)

        # Navigate to the relevant profile information based on the new JSON structure
        page_props = safe_get(response_json, 'data.props.pageProps', {})
        user_profile_info = safe_get(page_props, 'userProfile.publicProfileInfo', {})
        page_links = safe_get(page_props, 'pageLinks', {})

        # Check if valid profile data is extracted
        if safe_get(user_profile_info, 'username'):
            profile_username = safe_get(user_profile_info, 'username', username_for_api)
            display_name = safe_get(user_profile_info, 'title') # 'title' field now holds the display name
            followers = safe_get(user_profile_info, 'subscriberCount') # 'subscriberCount' for followers
            profile_url = safe_get(page_links, 'snapchatCanonicalUrl', f"https://www.snapchat.com/add/{profile_username}")

            return {
                "Username": profile_username,
                "Display Name": display_name,
                "Followers": str(followers),
                "Profile URL": profile_url
            }
        else:
            # Report API specific error message if available
            error_message = safe_get(response_json, 'message', 'No specific error message from API')
            print(f"API returned no valid data or an error for {profile_identifier}: {error_message}")
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
    # Define multiple Snapchat usernames or URLs in a list
    snapchat_identifiers_to_process = [
        "https://www.snapchat.com/add/muskansharma.22", # New example URL
        "Mrwhosetheboss",
        "https://www.snapchat.com/add/therock", # Example URL
        "charlidamelio", # Example username
        "https://www.snapchat.com/add/nonexistentuser12345" # Example of a non-existent user URL
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Username",
        "Display Name",
        "Followers",
        "Profile URL"
    ]

    print("--- Processing Snapchat Profiles ---")

    for identifier in snapchat_identifiers_to_process:
        print(f"\nProcessing Profile: {identifier}")
        profile_details = fetch_snapchat_profile_info(identifier)
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
        print("\n--- Snapchat Profile Basic Information Table ---")
        print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("----------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified Snapchat usernames/URLs.")
