# scrapers/fetch_youtube_post_info.py
import http.client
import urllib.parse
import json
import re
from datetime import datetime # For formatting timestamps
from langdetect import detect, DetectorFactory # Import language detection library

# Set seed for langdetect to ensure consistent results (optional but good for reproducibility)
DetectorFactory.seed = 0

# Assuming utils.py is in the same directory or accessible via package import
from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager # Import the key manager

# --- Configuration (Host specific to this YouTube API) ---
RAPIDAPI_HOST_YOUTUBE = "youtube-v38.p.rapidapi.com"

def fetch_youtube_post_info(video_url): # Function name remains as provided
    """
    Fetches basic details for a given YouTube video URL, implementing API key rotation
    for resilience against rate limits or invalid keys. Extracts the video ID from the URL
    and uses it to query the API. Returns a dictionary of extracted details or an error
    dictionary if fetching fails.
    """
    conn = None # Initialize conn to None to ensure it's defined for the finally block
    
    video_id = None
    # Extract video ID from the URL using regular expressions
    match = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', video_url)
    if match:
        video_id = match.group(1)
    else:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return {"error": f"Could not extract video ID from URL: {video_url}"}

    # Properly encode the video ID for the GET request URL
    encoded_video_id = urllib.parse.quote(video_id, safe='')
    endpoint = f"/video/details/?id={encoded_video_id}&hl=en&gl=US"

    # --- API Request with Key Rotation Loop ---
    # This loop attempts to fetch data, rotating API keys if a failure occurs due to
    # rate limits, invalid keys, or other transient errors.
    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            # Get headers with the current active API key and the specific host for YouTube
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST_YOUTUBE)
            
            # Establish an HTTPS connection to the RapidAPI host
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST_YOUTUBE)
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
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}) for YouTube API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube rate limit."}
                continue # Retry the request with the new key in the next iteration

            # Check for messages indicating invalid key or subscription issues, or 401/403 status
            elif ("not subscribed" in str(error_message_from_api).lower() or 
                  "invalid api key" in str(error_message_from_api).lower() or 
                  res.status in [401, 403]):
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue for YouTube API. Rotating key...")
                # Attempt to rotate to the next key. If no more keys, return error.
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for YouTube subscription/authentication."}
                continue # Retry the request with the new key

            # If it's not a 200 OK and not a key/rate limit issue, it's a general API error
            elif res.status != 200:
                print(f"YouTube API Error {res.status}: {error_message_from_api}. Not a rate limit, returning error.")
                return {"error": f"YouTube API Error {res.status}: {error_message_from_api}"}
            
            # Check if the API call returned valid data (e.g., 'videoId' or 'title')
            if not (response_json.get('videoId') or response_json.get('title')):
                final_api_error_message = error_message_from_api if error_message_from_api else 'No valid data or specific error message from API.'
                print(f"API returned no valid data or an error for Video ID {video_id}: {final_api_error_message}")
                return {"error": f"YouTube API returned no valid data or an error for Video ID {video_id}: {final_api_error_message}"}

            break # Exit loop if the request was successful and data is valid

        except http.client.HTTPException as e:
            # Catch HTTP connection errors (e.g., host unreachable)
            print(f"HTTP connection error for Video ID {video_id}: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors for YouTube."}
            continue # Retry with next key
        except json.JSONDecodeError:
            # Catch errors if the response is not valid JSON
            print(f"Error for Video ID {video_id}: Could not decode JSON response from YouTube API. Raw response: {raw_response_str}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses from YouTube API."}
            continue # Retry with next key
        except Exception as e:
            # Catch any other unexpected errors
            print(f"An unexpected error occurred for Video ID {video_id} with YouTube API: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors with YouTube API: {str(e)}"}
            continue # Retry with next key
        finally:
            # Ensure the HTTP connection is closed whether the request succeeded or failed
            if conn:
                conn.close()
    else:
        # This 'else' block executes if the loop completes without a 'break' statement,
        # meaning all available API keys were tried and failed to get a successful response.
        return {"error": "Failed to fetch YouTube post info after trying all available API keys."}

    # --- Data Extraction (executed only if API call was successful and loop broke) ---
    # Extract statistics and details from the provided JSON structure
    stats_info = safe_get(response_json, 'stats', {})
    views_count = safe_get(stats_info, 'views')
    likes_count = safe_get(stats_info, 'likes')
    comments_count = safe_get(stats_info, 'comments')

    author_info = safe_get(response_json, 'author', {})
    channel_name = safe_get(author_info, 'title')

    # Extract channel ID to construct Channel URL
    channel_id = safe_get(author_info, 'channelId')
    # MODIFIED: Construct Channel URL in the requested format
    channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id != "N/A" else "N/A"

    # Duration is directly available in 'lengthSeconds'
    video_duration_seconds = safe_get(response_json, 'lengthSeconds')

    # Published date is directly available in 'publishedDate'
    published_date_raw = safe_get(response_json, 'publishedDate')
    published_date_formatted = format_timestamp(published_date_raw, include_time=True) # Full timestamp

    # Extract the video description
    video_description = safe_get(response_json, 'description')

    # Detect language of the description
    detected_description_language = "N/A" # Default if detection fails
    if video_description and len(video_description.strip()) > 0 and video_description != "N/A":
        try:
            detected_description_language = detect(video_description)
        except Exception as e:
            detected_description_language = "Undetectable"
            print(f"    Warning: Could not detect language for video {video_id} description: {e}")

    return {
        "Views": str(views_count),
        "Likes": str(likes_count),
        "Comments": str(comments_count),
        "Video URL": video_url, # Use the original full URL for the output
        "Channel Name": channel_name,
        "Channel URL": channel_url,
        "Video Duration (seconds)": str(video_duration_seconds),
        "Published Date (UTC)": published_date_formatted,
        "Description Language": detected_description_language
    }

# --- Example Usage (only runs when this file is executed directly) ---
if __name__ == "__main__":
    # Define multiple YouTube Video URLs in a list
    youtube_video_urls_to_process = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ", # Rick Astley - Never Gonna Give You Up
        "https://www.youtube.com/watch?v=yYn9d-21p5I", # Example with comments
        "https://www.youtube.com/watch?v=invalid_id_xyz", # Example of an invalid ID
        "https://youtu.be/qQYfA3I_g8E" # Shortened URL example
    ]

    # List to store all video data rows for tabulate display
    collected_video_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Views",
        "Likes",
        "Comments",
        "Video URL",
        "Channel Name",
        "Channel URL",
        "Video Duration (seconds)",
        "Published Date (UTC)",
        "Description Language"
    ]

    print("--- Processing YouTube Videos ---")

    for url in youtube_video_urls_to_process:
        print(f"\nProcessing URL: {url}")
        video_details = fetch_youtube_post_info(url) # Updated function call
        if video_details and not video_details.get("error"): # Check for successful fetch and no error
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [video_details.get(header, 'N/A') for header in output_headers]
            collected_video_rows_for_output.append(row_data_list)
            print("Successfully extracted basic video details and detected description language.")
        else:
            # Print the error message if the fetch failed
            error_msg = video_details.get("error", "Unknown error") if video_details else "No details retrieved."
            print(f"Failed to retrieve video details for {url}. Error: {error_msg}")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_video_rows_for_output:
        print("\n--- YouTube Video Basic Information Table ---")
        try:
            from tabulate import tabulate # Import tabulate here if not already at top for main guard
            print(tabulate(collected_video_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        except ImportError:
            print("Please install 'tabulate' library (pip install tabulate) to view formatted table.")
            # Fallback to simple print if tabulate is not available
            for row in collected_video_rows_for_output:
                print(row)
        print("-------------------------------------------")
    else:
        print("\nNo basic video details collected for the specified YouTube videos.")
