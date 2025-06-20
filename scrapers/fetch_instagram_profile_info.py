# scrapers/fetch_instagram_profile_info.py
import http.client
import urllib.parse
import json
import re
from datetime import datetime # Although not explicitly used, kept for consistency

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get # Import safe_get from utils.py
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this Instagram Profile API) ---
RAPIDAPI_HOST = "simple-instagram-api.p.rapidapi.com"

def fetch_instagram_profile_info(profile_identifier):
    """
    Fetches detailed information for an Instagram profile using its username or URL
    from the 'simple-instagram-api', with API key rotation.
    Returns a dictionary of extracted details or an error dictionary.
    """
    conn = None # Initialize conn to None for finally block
    
    # Determine if the identifier is a URL or a username
    identifier_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from standard Instagram profile URLs
        match = re.search(r'(?:instagram\.com\/)([a-zA-Z0-9_\.]+)', profile_identifier)
        if match:
            identifier_for_api = match.group(1).replace('/', '') # Clean up potential trailing slash
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return {"error": f"Invalid Instagram profile URL or identifier: {profile_identifier}"}

    # Properly encode the identifier for the API endpoint
    encoded_identifier = urllib.parse.quote(identifier_for_api, safe='')
    endpoint = f"/account-info?username={encoded_identifier}" 
    
    # --- API Request with Key Rotation ---
    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST) # Get headers with the current key and host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
            conn.request("GET", endpoint, headers=current_headers)
            res = conn.getresponse()
            data = res.read()
            raw_response_str = data.decode("utf-8")
            json_data = json.loads(raw_response_str)

            # Check for API-specific errors that indicate rate limit or invalid key
            error_message = json_data.get("message") or json_data.get("error")
            
            if res.status == 429: # Too Many Requests (Common rate limit status code)
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}). Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for rate limit."}
                continue # Retry with the new key
            elif "not subscribed" in str(error_message).lower() or "invalid api key" in str(error_message).lower() or res.status in [401, 403]:
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for subscription/authentication."}
                continue # Retry with the new key
            elif res.status != 200:
                print(f"API Error {res.status}: {error_message}. Not a rate limit, returning error.")
                return {"error": f"API Error {res.status}: {error_message}"}
            
            # Check if the response contains expected data (e.g., 'username' is present)
            if safe_get(json_data, "username") == "N/A":
                error_message = safe_get(json_data, 'message', 'No specific error message provided.')
                if safe_get(json_data, 'status') == 'error':
                    error_message = safe_get(json_data, 'error', error_message)
                print(f"API returned no data or an error for {profile_identifier}: {error_message}")
                return {"error": f"API returned no data or an error for {profile_identifier}: {error_message}"}

            break # Exit loop if request was successful or a non-key-related error occurred

        except http.client.HTTPException as e:
            print(f"HTTP connection error: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors."}
            continue # Retry with next key
        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON response for {profile_identifier}. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses."}
            continue # Retry with next key
        except Exception as e:
            print(f"An unexpected error occurred for {profile_identifier}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors: {str(e)}"}
            continue # Retry with next key
        finally:
            if conn: # Ensure connection is closed even on errors
                conn.close()
    else: # This block executes if the loop completes without a 'break' (i.e., all keys tried and failed)
        return {"error": "Failed to fetch Instagram profile info after trying all available API keys."}

    # Extract data after successful API call
    username_val = safe_get(json_data, "username")
    full_name_val = safe_get(json_data, "full_name")
    follower_count = safe_get(json_data, "edge_followed_by.count")
    following_count = safe_get(json_data, "edge_follow.count")
    posts_count = safe_get(json_data, "edge_owner_to_timeline_media.count")
    
    # Construct the Instagram profile URL
    instagram_profile_url = f"https://www.instagram.com/{username_val}/" if username_val != "N/A" else "N/A"

    # Return all extracted data as a dictionary
    return {
        "Username": username_val,
        "Full Name": full_name_val,
        "Followers": str(follower_count),
        "Following": str(following_count),
        "Posts Count": str(posts_count),
        "Profile URL": instagram_profile_url,
    }
