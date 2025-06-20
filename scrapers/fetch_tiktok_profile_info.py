# scrapers/fetch_tiktok_profile_info.py
import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps, even if not heavily used here
import re # For extracting username from URLs

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this TikTok API) ---
RAPIDAPI_HOST_TIKTOK = "tiktok-api6.p.rapidapi.com" # Updated API host for this specific endpoint

def fetch_tiktok_profile_info(profile_identifier): # Renamed 'username' to 'profile_identifier'
    """
    Fetches detailed information for a TikTok user profile using their username or URL,
    implementing API key rotation for resilience against rate limits or invalid keys.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    
    # Determine if the identifier is a URL or a username
    username_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from standard TikTok profile URLs
        match = re.search(r'(?:tiktok\.com\/@)([a-zA-Z0-9_\.]+)', profile_identifier)
        if match:
            username_for_api = match.group(1).replace('/', '') # Clean up potential trailing slash
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return {"error": f"Could not extract username from URL: {profile_identifier}"}

    # --- API Request with Key Rotation Loop ---
    # This loop attempts to fetch data, rotating API keys if a failure occurs due to
    # rate limits, invalid keys, or other transient errors.
    for _ in range(rapidapi_key_manager.max_key_rotations):
        conn = None # Initialize conn to None at the start of each loop iteration
        try:
            # Get headers with the current active API key and the specific host for TikTok
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_TIKTOK)
            
            # Properly encode the username for the GET request URL
            encoded_username = urllib.parse.quote(username_for_api)

            # Request user details using the new GET endpoint structure
            endpoint = f"/user/details?username={encoded_username}"
            
            # Establish an HTTPS connection to the RapidAPI host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST_TIKTOK)
            # Send the GET request
            conn.request("GET", endpoint, headers=current_headers)
            # Get the response
            res = conn.getresponse()
            data = res.read() # Read the response body

            # Decode the raw API response from bytes to a UTF-8 string
            raw_response_str = data.decode("utf-8")
            response_json = json.loads(raw_response_str)

            # Check HTTP status codes and API-specific error messages for key rotation triggers
            error_message_from_api = safe_get(response_json, 'message', safe_get(response_json, 'error', safe_get(response_json, 'reason', '')))
            
            # 429 status code indicates Too Many Requests (Rate Limit)
            if res.status == 429:
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}) for TikTok API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for TikTok rate limit."}
                continue # Retry the request with the new key in the next iteration

            # Check for messages indicating invalid key or subscription issues, or 401/403 status
            elif ("not subscribed" in str(error_message_from_api).lower() or 
                  "invalid api key" in str(error_message_from_api).lower() or 
                  res.status in [401, 403]):
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue for TikTok API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for TikTok subscription/authentication."}
                continue # Retry the request with the new key

            # If it's not a 200 OK and not a key/rate limit issue, it's a general API error
            elif res.status != 200:
                print(f"TikTok API Error {res.status}: {error_message_from_api}. Not a rate limit, returning error.")
                return {"error": f"TikTok API Error {res.status}: {error_message_from_api}"}
            
            # Check for a fundamental key to indicate valid data from the API response
            if not response_json.get('username'):
                final_api_error_message = error_message_from_api if error_message_from_api else 'Unknown error from TikTok API.'
                print(f"API returned an error for {profile_identifier}: {final_api_error_message}") # Use original identifier for error
                return {"error": f"TikTok API returned an error for {profile_identifier}: {final_api_error_message}"}

            break # Exit loop if the request was successful and data is valid

        except http.client.HTTPException as e:
            # Catch HTTP connection errors (e.g., host unreachable)
            print(f"HTTP connection error for {profile_identifier}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors for TikTok."}
            continue # Retry with next key
        except json.JSONDecodeError:
            # Catch errors if the response is not valid JSON
            print(f"Error for {profile_identifier}: Could not decode JSON response from TikTok API. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses from TikTok API."}
            continue # Retry with next key
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred for TikTok profile {profile_identifier}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors with TikTok API: {str(e)}"}
            continue # Retry with next key
        finally:
            # Ensure the HTTP connection is closed whether the request succeeded or failed
            if conn:
                conn.close()
    else: # This 'else' block is for the 'for' loop. It executes if the loop completes without a 'break'.
        return {"error": "Failed to fetch TikTok profile info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # If we reach this point, it means the API call was successful and `response_json` contains valid data.
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
