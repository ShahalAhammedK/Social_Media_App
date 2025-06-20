# scrapers/fetch_youtube_profile_info.py
import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
import re # Essential for extracting channel ID/handle from URLs

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this YouTube Channel API) ---
RAPIDAPI_HOST_YOUTUBE_CHANNEL = "youtube-shorts-sounds-songs-api.p.rapidapi.com"

def extract_youtube_identifier(identifier):
    """
    Extracts the channel handle (e.g., @handle) or channel ID (e.g., UC...) from a full URL.
    If already a handle or ID, returns as is.
    """
    if identifier.startswith("http"):
        # This regex tries to capture either @handle, /channel/UCid, or /c/legacyname
        match = re.search(r'youtube\.com/(?:@|channel/|c/)?([a-zA-Z0-9@_.\-]+)', identifier)
        if match:
            extracted = match.group(1)
            # If it looks like a channel ID (starts with UC) or already has '@', return as is
            if extracted.startswith("UC") or extracted.startswith("@"):
                return extracted
            # Otherwise, assume it's a handle that might be missing the '@'
            return "@" + extracted
        else:
            return None # Could not extract a valid identifier from the URL
    return identifier # If not a URL, assume it's already an identifier

def fetch_youtube_profile_info(channel_identifier):
    """
    Fetches detailed information for a YouTube channel using its handle (e.g., "@TeamFalconsGG") or URL,
    implementing API key rotation for resilience against rate limits or invalid keys.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    conn = None # Initialize conn to None to ensure it's defined for the finally block
    
    handle_for_api = extract_youtube_identifier(channel_identifier)
    if not handle_for_api:
        print(f"Error: Could not extract valid handle or ID from: {channel_identifier}")
        return {"error": f"Could not extract valid handle or ID from URL: {channel_identifier}"}

    # Properly encode the channel handle/ID for the GET request URL
    encoded_handle = urllib.parse.quote(handle_for_api, safe='')
    endpoint = f"/channel/handle/{encoded_handle}"

    # --- API Request with Key Rotation Loop ---
    # This loop attempts to fetch data, rotating API keys if a failure occurs due to
    # rate limits, invalid keys, or other transient errors.
    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            # Get headers with the current active API key and the specific host for YouTube Channel API
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_YOUTUBE_CHANNEL)
            
            # Establish an HTTPS connection to the RapidAPI host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST_YOUTUBE_CHANNEL)
            # Send the GET request
            conn.request("GET", endpoint, headers=current_headers)
            # Get the response
            res = conn.getresponse()
            data = res.read() # Read the response body

            # Decode the raw API response from bytes to a UTF-8 string
            raw_response_str = data.decode("utf-8")
            response_json = json.loads(raw_response_str)

            # Check HTTP status codes and API-specific error messages for key rotation triggers
            error_message_from_api = safe_get(response_json, 'message', safe_get(response_json, 'error', ''))
            
            # 429 status code indicates Too Many Requests (Rate Limit)
            if res.status == 429:
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}) for YouTube Channel API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube Channel rate limit."}
                continue # Retry the request with the new key in the next iteration

            # Check for messages indicating invalid key or subscription issues, or 401/403 status
            elif ("not subscribed" in str(error_message_from_api).lower() or 
                  "invalid api key" in str(error_message_from_api).lower() or 
                  res.status in [401, 403]):
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue for YouTube Channel API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube Channel subscription/authentication."}
                continue # Retry the request with the new key

            # If it's not a 200 OK and not a key/rate limit issue, it's a general API error
            elif res.status != 200:
                print(f"YouTube Channel API Error {res.status}: {error_message_from_api}. Not a rate limit, returning error.")
                return {"error": f"YouTube Channel API Error {res.status}: {error_message_from_api}"}
            
            # Check if the JSON response contains expected valid data (e.g., 'id' or 'name')
            if not (safe_get(response_json, 'id') or safe_get(response_json, 'name')):
                final_api_error_message = error_message_from_api if error_message_from_api else 'No valid data or specific error message from API.'
                print(f"API returned no valid data for {channel_identifier}. Full response: {raw_response_str}")
                return {"error": f"YouTube Channel API returned no valid data for {channel_identifier}: {final_api_error_message}"}

            break # Exit loop if the request was successful and data is valid

        except http.client.HTTPException as e:
            # Catch HTTP connection errors (e.g., host unreachable)
            print(f"HTTP connection error for {channel_identifier}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors for YouTube Channel."}
            continue # Retry with next key
        except json.JSONDecodeError:
            # Catch errors if the response is not valid JSON
            print(f"Error for {channel_identifier}: Could not decode JSON response from YouTube Channel API. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses from YouTube Channel API."}
            continue # Retry with next key
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred for {channel_identifier} with YouTube Channel API: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors with YouTube Channel API: {str(e)}"}
            continue # Retry with next key
        finally:
            # Ensure the HTTP connection is closed whether the request succeeded or failed
            if conn:
                conn.close()
    else: # This 'else' block executes if the loop completes without a 'break' statement,
        # meaning all available API keys were tried and failed to get a successful response.
        return {"error": "Failed to fetch YouTube channel info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # Extract specific channel details from the parsed JSON response
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

# --- Example Usage (only runs when this file is executed directly) ---
if __name__ == "__main__":
    # Define multiple YouTube channel handles or URLs in a list for testing
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
        if profile_details and not profile_details.get("error"): # Check for successful fetch and no error
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [profile_details.get(header, 'N/A') for header in output_headers]
            collected_profile_rows_for_output.append(row_data_list)
            print("Successfully extracted basic profile details.")
        else:
            # Print the error message if the fetch failed
            error_msg = profile_details.get("error", "Unknown error") if profile_details else "No details retrieved."
            print(f"Failed to retrieve profile details for {identifier}. Error: {error_msg}")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_profile_rows_for_output:
        print("\n--- YouTube Channel Basic Information Table ---")
        try:
            from tabulate import tabulate # Import tabulate here if not already at top for main guard
            print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        except ImportError:
            print("Please install 'tabulate' library (pip install tabulate) to view formatted table.")
            # Fallback to simple print if tabulate is not available
            for row in collected_profile_rows_for_output:
                print(row)
        print("---------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified YouTube channels.")
