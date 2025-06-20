# scrapers/fetch_snapchat_profile_info.py
import http.client
import urllib.parse
import json
import re
from datetime import datetime # For formatting timestamps

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this Snapchat API) ---
RAPIDAPI_HOST_SNAPCHAT = "snapchat-scraper2.p.rapidapi.com"

def fetch_snapchat_profile_info(profile_identifier):
    """
    Fetches detailed information for a Snapchat profile using its username or URL,
    implementing API key rotation for resilience against rate limits or invalid keys.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    conn = None # Initialize conn to None to ensure it's defined for the finally block
    
    # Extract username from URL if needed. This regex targets 'snapchat.com/add/username'
    username_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        match = re.search(r'snapchat\.com\/add\/([a-zA-Z0-9_.\-]+)', profile_identifier)
        if match:
            username_for_api = match.group(1)
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return {"error": f"Invalid Snapchat profile URL or identifier: {profile_identifier}"}

    # Properly encode the username for the GET request URL to handle special characters
    encoded_username = urllib.parse.quote(username_for_api, safe='')
    endpoint = f"/api/v1/users/detail?username={encoded_username}"

    # --- API Request with Key Rotation Loop ---
    # This loop attempts to fetch data, rotating API keys if a failure occurs due to
    # rate limits, invalid keys, or other transient errors.
    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            # Get headers with the current active API key and the specific host for Snapchat
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_SNAPCHAT)
            
            # Establish an HTTPS connection to the RapidAPI host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST_SNAPCHAT)
            # Send the GET request
            conn.request("GET", endpoint, headers=current_headers)
            # Get the response
            res = conn.getresponse()
            data = res.read() # Read the response body

            # Decode the raw API response from bytes to a UTF-8 string
            raw_response_str = data.decode("utf-8")
            # Parse the JSON response
            response_json = json.loads(raw_response_str)

            # Check HTTP status codes and API-specific error messages for key rotation triggers
            error_message_from_api = safe_get(response_json, 'message', '')
            
            # 429 status code indicates Too Many Requests (Rate Limit)
            if res.status == 429:
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}) for Snapchat API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for Snapchat rate limit."}
                continue # Retry the request with the new key in the next iteration

            # Check for messages indicating invalid key or subscription issues, or 401/403 status
            elif ("not subscribed" in str(error_message_from_api).lower() or 
                  "invalid api key" in str(error_message_from_api).lower() or 
                  res.status in [401, 403]):
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue for Snapchat API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for Snapchat subscription/authentication."}
                continue # Retry the request with the new key

            # If it's not a 200 OK and not a key/rate limit issue, it's a general API error
            elif res.status != 200:
                print(f"Snapchat API Error {res.status}: {error_message_from_api}. Not a rate limit, returning error.")
                return {"error": f"Snapchat API Error {res.status}: {error_message_from_api}"}
            
            # Navigate to the relevant profile information based on the new JSON structure
            # This is specific to the Snapchat API's response format
            page_props = safe_get(response_json, 'data.props.pageProps', {})
            user_profile_info = safe_get(page_props, 'userProfile.publicProfileInfo', {})
            page_links = safe_get(page_props, 'pageLinks', {})

            # Check if valid profile data is extracted (e.g., username should be present)
            if safe_get(user_profile_info, 'username') == "N/A": 
                # If no valid username, report the API's specific error message if available
                final_api_error_message = safe_get(response_json, 'message', 'No specific error message from API and no valid profile data.')
                print(f"Snapchat API returned no valid data or an error for {profile_identifier}: {final_api_error_message}")
                return {"error": f"Snapchat API returned no valid data or an error for {profile_identifier}: {final_api_error_message}"}

            break # Exit loop if the request was successful and data is valid

        except http.client.HTTPException as e:
            # Catch HTTP connection errors (e.g., host unreachable)
            print(f"HTTP connection error for {profile_identifier}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors for Snapchat."}
            continue # Retry with next key
        except json.JSONDecodeError:
            # Catch errors if the response is not valid JSON
            print(f"Error for {profile_identifier}: Could not decode JSON response for Snapchat. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses from Snapchat API."}
            continue # Retry with next key
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred for {profile_identifier} with Snapchat API: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors with Snapchat API: {str(e)}"}
            continue # Retry with next key
        finally:
            # Ensure the HTTP connection is closed whether the request succeeded or failed
            if conn:
                conn.close()
    else:
        # This 'else' block executes if the loop completes without a 'break' statement,
        # meaning all available API keys were tried and failed to get a successful response.
        return {"error": "Failed to fetch Snapchat profile info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful) ---
    # Extract specific profile details from the parsed JSON response
    profile_username = safe_get(user_profile_info, 'username', username_for_api)
    display_name = safe_get(user_profile_info, 'title') # 'title' field now holds the display name
    followers = safe_get(user_profile_info, 'subscriberCount') # 'subscriberCount' for followers
    profile_url = safe_get(page_links, 'snapchatCanonicalUrl', f"https://www.snapchat.com/add/{profile_username}")

    # Return the extracted details as a dictionary
    return {
        "Username": profile_username,
        "Display Name": display_name,
        "Followers": str(followers), # Convert to string for consistent output
        "Profile URL": profile_url
    }

# --- Example Usage (only runs when this file is executed directly) ---
if __name__ == "__main__":
    # Define multiple Snapchat usernames or URLs in a list for testing
    snapchat_identifiers_to_process = [
        "https://www.snapchat.com/add/muskansharma.22", 
        "Mrwhosetheboss",
        "https://www.snapchat.com/add/therock", 
        "charlidamelio", 
        "https://www.snapchat.com/add/nonexistentuser12345" # Example of a non-existent user URL
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table for consistency
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
        print("\n--- Snapchat Profile Basic Information Table ---")
        try:
            from tabulate import tabulate # Import tabulate here if not already at top for main guard
            print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        except ImportError:
            print("Please install 'tabulate' library (pip install tabulate) to view formatted table.")
            # Fallback to simple print if tabulate is not available
            for row in collected_profile_rows_for_output:
                print(row)
        print("----------------------------------------------")
    else:
        print("\nNo basic profile details collected for the specified Snapchat usernames/URLs.")
