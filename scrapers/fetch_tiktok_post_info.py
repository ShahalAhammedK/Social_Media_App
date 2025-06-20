# scrapers/fetch_tiktok_post_info.py
import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this TikTok API) ---
RAPIDAPI_HOST_TIKTOK = "tiktok89.p.rapidapi.com"

def fetch_tiktok_post_info(video_url): # Function name remains as provided
    """
    Fetches basic details for a given TikTok video URL using the TikTok API,
    implementing API key rotation for resilience against rate limits or invalid keys.
    Returns a dictionary of extracted details or an error dictionary if fetching fails.
    """
    
    # Properly encode the URL for the GET request
    encoded_url = urllib.parse.quote(video_url, safe='')
    endpoint = f"/tiktok?link={encoded_url}"
    
    # --- API Request with Key Rotation Loop ---
    # This loop attempts to fetch data, rotating API keys if a failure occurs due to
    # rate limits, invalid keys, or other transient errors.
    for _ in range(rapidapi_key_manager.max_key_rotations):
        conn = None # Initialize conn to None at the start of each loop iteration
        try:
            # Get headers with the current active API key and the specific host for TikTok
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_TIKTOK)
            
            # Establish an HTTPS connection to the RapidAPI host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST_TIKTOK)
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
            error_message_from_api = response_json.get('message', response_json.get('reason', ''))
            
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
            
            # Check if the response indicates success from the TikTok API itself (e.g., 'ok' field)
            if not response_json.get('ok'):
                final_api_error_message = response_json.get('message', response_json.get('reason', 'Unknown error from TikTok API.'))
                print(f"TikTok API returned an error for {video_url}: {final_api_error_message}")
                return {"error": f"TikTok API returned an error for {video_url}: {final_api_error_message}"}

            break # Exit loop if the request was successful and data is valid

        except http.client.HTTPException as e:
            # Catch HTTP connection errors (e.g., host unreachable)
            print(f"HTTP connection error for {video_url}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors for TikTok."}
            continue # Retry with next key
        except json.JSONDecodeError:
            # Catch errors if the response is not valid JSON
            print(f"Error for {video_url}: Could not decode JSON response from TikTok API. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses from TikTok API."}
            continue # Retry with next key
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred for TikTok video {video_url}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors with TikTok API: {str(e)}"}
            continue # Retry with next key
        finally:
            # Ensure the HTTP connection is closed whether the request succeeded or failed
            if conn:
                conn.close()
    else: # This 'else' block is for the 'for' loop. It executes if the loop completes without a 'break'.
        return {"error": "Failed to fetch TikTok post info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # If we reach this point, it means the API call was successful and `response_json` contains valid data.
    author_info = safe_get(response_json, 'author', {})
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
        "Video Duration (seconds)": str(video_duration_seconds),
        "Video Language": caption_language,
        "Caption Language": caption_language, # Often the same field for TikTok
        "Created Date (UTC)": create_time_utc
    }

# --- Example Usage (only runs when this file is executed directly) ---
if __name__ == "__main__":
    # Define multiple TikTok video URLs in a list for testing
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
        video_details = fetch_tiktok_post_info(video_url)
        if video_details and not video_details.get("error"): # Check for successful fetch and no error
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [video_details.get(header, 'N/A') for header in output_headers]
            collected_video_rows.append(row_data_list)
            print("Successfully extracted basic video details.")
        else:
            # Print the error message if the fetch failed
            error_msg = video_details.get("error", "Unknown error") if video_details else "No details retrieved."
            print(f"Failed to retrieve video details for {video_url}. Error: {error_msg}")
        print("-" * 40)

    # Print the collected data as a formatted table using tabulate
    if collected_video_rows:
        print("\n--- TikTok Video Basic Information Table ---")
        try:
            from tabulate import tabulate # Import tabulate here if not already at top for main guard
            print(tabulate(collected_video_rows, headers=output_headers, tablefmt="fancy_grid"))
        except ImportError:
            print("Please install 'tabulate' library (pip install tabulate) to view formatted table.")
            # Fallback to simple print if tabulate is not available
            for row in collected_video_rows:
                print(row)
        print("------------------------------------------")
    else:
        print("\nNo basic video details collected for the specified TikTok videos.")
