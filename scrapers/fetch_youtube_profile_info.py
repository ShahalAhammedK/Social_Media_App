# scrapers/fetch_youtube_profile_info.py
import urllib.parse
import json
import re # Essential for extracting channel ID/handle from URLs

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp, make_api_request
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this YouTube Channel API) ---
RAPIDAPI_HOST_YOUTUBE_CHANNEL = "youtube-shorts-sounds-songs-api.p.rapidapi.com"

def extract_youtube_identifier(identifier):
    """
    Extracts the channel handle (e.g., @handle) or channel ID (e.g., UC...) from a full URL,
    or determines if the input is already a handle or ID.
    If the input is a plain string that doesn't start with 'UC' (channel ID format) or '@' (handle format),
    it is automatically assumed to be a YouTube handle, and '@' is prepended for consistency.
    Returns a tuple: (identifier_type, cleaned_identifier_value)
    identifier_type will be 'handle', 'id', or None if extraction fails.
    """
    if identifier.startswith("http"):
        # Regex to capture @handle, /channel/UCid, /c/legacyname, or /user/legacyusername
        match = re.search(r'(?:youtube\.com/(?:@|channel/|c/|user/)|youtu\.be/)([a-zA-Z0-9@_-]+)(?:[/]|$|\?|&)', identifier)
        if match:
            extracted = match.group(1)
            # If it looks like a channel ID (starts with UC and is roughly 24 chars long)
            if extracted.startswith("UC") and len(extracted) >= 22 and len(extracted) <= 24: # YouTube IDs are typically 24 characters
                return ('id', extracted)
            # If it explicitly starts with '@', it's a handle
            elif extracted.startswith("@"):
                return ('handle', extracted)
            # Otherwise, assume it's a handle from a custom URL or legacy username (e.g., /c/LinusTechTips, /user/PewDiePie)
            else:
                return ('handle', "@" + extracted) # Prepend '@' for consistency with handle format
        else:
            print(f"Warning: Could not extract a clear identifier from URL: {identifier}")
            return (None, None) # Could not extract a valid identifier from the URL
    else:
        # If not a URL, check if it's a channel ID or a handle
        if identifier.startswith("UC") and len(identifier) >= 22 and len(identifier) <= 24: # Check for typical ID format
            return ('id', identifier)
        elif identifier.startswith("@"):
            return ('handle', identifier)
        else:
            # If it's a plain string (e.g., "ishowspeed", "mrbeast"), assume it's a handle
            # and prepend '@' to conform to the API's expected handle format.
            print(f"Assuming '{identifier}' is a YouTube handle. Prepending '@'.")
            return ('handle', "@" + identifier)


def fetch_youtube_profile_info(channel_identifier):
    """
    Fetches detailed information for a YouTube channel using its handle (e.g., "@TeamFalconsGG"),
    channel ID (e.g., "UC..."), or URL, implementing API key rotation for resilience.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    
    identifier_type, cleaned_identifier = extract_youtube_identifier(channel_identifier)

    if not identifier_type or not cleaned_identifier:
        print(f"Error: Could not determine identifier type or extract valid identifier from: {channel_identifier}")
        return {"error": f"Could not determine identifier type or extract valid identifier from: {channel_identifier}"}

    # Properly encode the identifier for the GET request URL
    encoded_identifier = urllib.parse.quote(cleaned_identifier, safe='')
    
    # Choose endpoint based on identifier type
    if identifier_type == 'handle':
        endpoint = f"/channel/handle/{encoded_identifier}"
    elif identifier_type == 'id':
        endpoint = f"/channel/id/{encoded_identifier}"
    else: # Should not happen if extract_youtube_identifier works as expected
        print(f"Internal Error: Unknown identifier type '{identifier_type}' for {channel_identifier}")
        return {"error": f"Internal Error: Unknown identifier type for {channel_identifier}"}

    # --- API Request with Key Rotation Loop (using make_api_request) ---
    response_json = None
    for _ in range(rapidapi_key_manager.max_key_rotations):
        current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_YOUTUBE_CHANNEL)
        
        response_json = make_api_request(
            host=RAPIDAPI_HOST_YOUTUBE_CHANNEL,
            endpoint=endpoint,
            headers=current_headers
        )

        # Check if make_api_request returned an error
        if isinstance(response_json, dict) and "error" in response_json:
            error_msg = response_json["error"].lower()
            
            # Check for RapidAPI specific errors that indicate key rotation
            if "timed out" in error_msg:
                print(f"Request timed out for YouTube Channel API. Retrying with next key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted due to timeouts for YouTube Channel."}
                continue # Retry with next key
            elif ("not subscribed" in error_msg or 
                  "invalid api key" in error_msg or 
                  "401" in error_msg or # Status code in error message
                  "403" in error_msg): # Status code in error message
                print(f"Current key invalid or subscription issue for YouTube Channel API. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube Channel subscription/authentication."}
                continue # Retry with new key
            elif "429" in error_msg: # Rate limit error in message
                 print(f"Rate limit hit with current key for YouTube Channel API. Rotating key...")
                 if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube Channel rate limit."}
                 continue # Retry with new key
            else:
                # Other general API errors (e.g., 404 not found for a valid key)
                print(f"YouTube Channel API Error for {channel_identifier}: {response_json['error']}")
                return response_json # Return the error directly
        else:
            # If no error from make_api_request, check if the API response itself is valid
            if not (safe_get(response_json, 'id') or safe_get(response_json, 'name')):
                final_api_error_message = safe_get(response_json, 'message', safe_get(response_json, 'error', 'No valid data or specific error message from API.'))
                print(f"API returned no valid data for {channel_identifier}. Full response: {response_json}")
                return {"error": f"YouTube Channel API returned no valid data for {channel_identifier}: {final_api_error_message}"}
            break # Exit loop if the request was successful and data is valid
    else: 
        return {"error": "Failed to fetch YouTube channel info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # Extract specific channel details from the parsed JSON response
    # Prioritize values from API, fallback to original if not present
    channel_id_val = safe_get(response_json, 'id')
    # If API provides a handle, use it. Otherwise, use the cleaned_identifier if it was a handle.
    channel_handle_val = safe_get(response_json, 'handle', cleaned_identifier if identifier_type == 'handle' else 'N/A')
    channel_name = safe_get(response_json, 'name')
    subscribers = safe_get(response_json, 'subscribers')
    total_videos = safe_get(response_json, 'videoCount')
    total_views = safe_get(response_json, 'viewCount')

    # Construct YouTube channel URL based on standard YouTube format
    if channel_handle_val and channel_handle_val != 'N/A':
        # Handles always have a URL like https://www.youtube.com/@handle
        display_url = f"https://www.youtube.com/{channel_handle_val}"
    elif channel_id_val and channel_id_val != 'N/A':
        # Channel IDs have a URL like https://www.youtube.com/channel/UC...
        display_url = f"https://www.youtube.com/channel/{channel_id_val}"
    else:
        display_url = "N/A"


    return {
        "Channel ID": channel_id_val,
        "Channel Handle": channel_handle_val,
        "Channel Name": channel_name,
        "Subscribers": str(subscribers),
        "Total Videos": str(total_videos),
        "Total Channel Views": str(total_views),
        "Channel URL": display_url
    }

# --- Example Usage (only runs when this file is executed directly) ---
if __name__ == "__main__":
    # Define multiple YouTube channel handles, IDs or URLs in a list for testing
    youtube_channels_to_process = [
        "ishowspeed", # Plain string - should be detected as handle
        "mrbeast",    # Plain string - should be detected as handle
        "@TeamFalconsGG", # Handle with @
        "https://www.youtube.com/@DrakeOfficial", # URL with handle
        "UCByOQJjav0CUDwxCk-jVNRQ", # Channel ID
        "https://www.youtube.com/channel/UCByOQJjav0CUDwxCk-jVNRQ", # URL with channel ID
        "https://www.youtube.com/c/LinusTechTips", # Legacy custom URL (should resolve to handle or ID)
        "UC-lHJZR3Gqxm24_Vd_AJ5Yw", # Another Channel ID (e.g., PewDiePie)
        "https://www.youtube.com/user/PewDiePie", # Legacy username URL (should resolve)
        "@nonexistentchannel123456", # Example of a non-existent channel handle
        "UC_NonExistentID1234567890ABCDEF" # Example of a non-existent channel ID
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Channel ID",
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
            row_data_list = [profile_details.get(header, 'N/A') for header in output_headers]
            collected_profile_rows_for_output.append(row_data_list)
            print("Successfully extracted basic profile details.")
        else:
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
