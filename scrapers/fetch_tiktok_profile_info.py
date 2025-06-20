# scrapers/fetch_tiktok_profile_info.py
import urllib.parse
import json
import re # For extracting username from URLs

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp, make_api_request
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this TikTok API) ---
RAPIDAPI_HOST_TIKTOK = "tiktok-scraper7.p.rapidapi.com" # Updated API host based on user's snippet

def extract_tiktok_identifier(profile_identifier):
    """
    Extracts the TikTok username from a URL or determines if the input is already a username.
    Returns the cleaned username or None if extraction fails.
    """
    cleaned_username = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from standard TikTok profile URLs
        match = re.search(r'(?:tiktok\.com\/@)([a-zA-Z0-9_\.]+)', profile_identifier)
        if match:
            cleaned_username = match.group(1).replace('/', '') # Clean up potential trailing slash
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}.")
            return None
    return cleaned_username


def fetch_tiktok_profile_info(profile_identifier):
    """
    Fetches detailed information for a TikTok user profile using their username or URL,
    implementing API key rotation for resilience against rate limits or invalid keys.
    This version uses the 'tiktok-scraper7.p.rapidapi.com' API.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    
    username_for_api = extract_tiktok_identifier(profile_identifier)

    if not username_for_api:
        return {"error": f"Could not extract a valid TikTok username from: {profile_identifier}"}

    # --- API Request with Key Rotation Loop (using make_api_request) ---
    response_json = None
    for _ in range(rapidapi_key_manager.max_key_rotations):
        # Get headers with the current active API key and the specific host for TikTok
        current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_TIKTOK)
        
        # Properly encode the username for the GET request URL
        encoded_username = urllib.parse.quote(username_for_api)

        # Request user details using the new GET endpoint and parameter name
        endpoint = f"/user/info?unique_id={encoded_username}" # Updated endpoint and parameter
        
        # Make the API request using the centralized helper function
        response_json = make_api_request(
            host=RAPIDAPI_HOST_TIKTOK,
            endpoint=endpoint,
            headers=current_headers
        )

        # Check if make_api_request returned an error (it returns a dict with 'error' key)
        if isinstance(response_json, dict) and "error" in response_json:
            error_msg = response_json["error"].lower()
            
            # Check for specific error messages that indicate key rotation is needed
            if "timed out" in error_msg:
                print(f"Request timed out for TikTok API. Retrying with next key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted due to timeouts for TikTok."}
                continue # Retry with next key
            elif ("not subscribed" in error_msg or 
                  "invalid api key" in error_msg or 
                  "401" in error_msg or # Status code embedded in error message
                  "403" in error_msg): # Status code embedded in error message
                print(f"Current key invalid or subscription issue for TikTok API. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for TikTok subscription/authentication."}
                continue # Retry with new key
            elif "429" in error_msg: # Rate limit error embedded in message
                 print(f"Rate limit hit with current key for TikTok API. Rotating key...")
                 if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for TikTok rate limit."}
                 continue # Retry with new key
            else:
                # Other general API errors (e.g., 404 not found for a valid key)
                print(f"TikTok API Error for {profile_identifier}: {response_json['error']}")
                return response_json # Return the error directly

        else:
            # If no error from make_api_request, check if the API response itself is valid data
            # The new API might return a 'data' key containing the actual user info
            user_data = safe_get(response_json, 'data') 
            if not user_data or not safe_get(user_data, 'user.uniqueId'): # Check for a fundamental key to indicate valid data
                final_api_error_message = safe_get(response_json, 'message', safe_get(response_json, 'error', safe_get(response_json, 'reason', 'No valid data or specific error message from API.')))
                print(f"API returned no valid data for {profile_identifier}. Full response: {response_json}")
                return {"error": f"TikTok API returned no valid data for {profile_identifier}: {final_api_error_message}"}
            break # Exit loop if the request was successful and data is valid
    else: # This 'else' block is for the 'for' loop. It executes if the loop completes without a 'break'.
        return {"error": "Failed to fetch TikTok profile info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # The new API structure appears to nest user info under a 'data' key
    profile_data_user = safe_get(response_json, 'data.user')
    profile_data_stats = safe_get(response_json, 'data.stats')

    profile_username = safe_get(profile_data_user, 'uniqueId') # Changed from 'username' to 'uniqueId' based on new API
    nickname = safe_get(profile_data_user, 'nickname')
    follower_count = safe_get(profile_data_stats, 'followerCount') # Extracted from data.stats
    following_count = safe_get(profile_data_stats, 'followingCount') # Extracted from data.stats
    total_likes_received = safe_get(profile_data_stats, 'heartCount') # Extracted from data.stats
    posts_count = safe_get(profile_data_stats, 'videoCount') # Extracted from data.stats

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

# --- Example Usage (only runs when this file is executed directly) ---
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

    # Print the collected data as a formatted table using tabulate
    if collected_profile_rows_for_output:
        print("\n--- TikTok Profile Basic Information Table ---")
        try:
            from tabulate import tabulate # Import tabulate here if not already at top for main guard
            print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        except ImportError:
            print("Please install 'tabulate' library (pip install tabulate) to view formatted table.")
            # Fallback to simple print if tabulate is not available
            for row in collected_profile_rows_for_output:
                print(row)
        print("--------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified TikTok usernames/URLs.")
