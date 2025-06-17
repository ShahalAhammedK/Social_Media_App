import http.client
import urllib.parse
import json
from datetime import datetime # For formatting timestamps
from tabulate import tabulate # For pretty printing tables
from langdetect import detect, DetectorFactory # Import language detection library

# Set seed for langdetect to ensure consistent results (optional but good for reproducibility)
DetectorFactory.seed = 0

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'"
# or "ModuleNotFoundError: No module named 'langdetect'",
# you need to install these libraries. Open your terminal or command prompt and run:
# pip install tabulate langdetect

# --- Configuration ---
# Instagram API
RAPIDAPI_KEY = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key for Instagram
RAPIDAPI_HOST = "instagram-social-api.p.rapidapi.com"

headers = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST
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

def fetch_instagram_hashtag_media(hashtag): # Renamed function
    """
    Fetches posts/media for a given Instagram hashtag using the RapidAPI endpoint.
    Returns a list of dictionaries, each representing a post/media item with extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    # Ensure hashtag is URL-encoded
    encoded_hashtag = urllib.parse.quote(hashtag, safe='')
    endpoint = f"/v1/hashtag?hashtag={encoded_hashtag}"
    
    collected_posts = []
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()

        json_data = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON response for #{hashtag}.")
        return []
    finally:
        conn.close()

    items = json_data.get("data", {}).get("items", [])
    if not items:
        print(f"No posts found for #{hashtag}")
        return []

    for item in items:
        caption = item.get("caption", {})
        user = item.get("user", {})
        
        is_video_val = item.get("is_video", False)
        video_views_val = item.get("ig_play_count", "N/A") if is_video_val else "N/A"

        taken_at_timestamp = item.get("taken_at", "0")
        taken_at_formatted = format_timestamp(taken_at_timestamp, include_time=False)

        username_val = user.get("username", "N/A")
        full_name_val = user.get("full_name", "N/A")
        caption_text_val = caption.get("text", "N/A")
        
        hashtags_val = ", ".join(caption.get("hashtags", [])) or "N/A"
        mentions_val = ", ".join(caption.get("mentions", [])) or "N/A"
        
        likes_count = item.get("like_count", "N/A")
        comments_count = item.get("comment_count", "N/A")
        
        video_url_val = item.get("video_url", "N/A") if is_video_val else "N/A"
        thumbnail_url_val = item.get("thumbnail_url", "N/A")
        instagram_url_val = f"https://www.instagram.com/p/{item.get('code', '')}/" if item.get('code') else "N/A"

        detected_caption_language = "N/A"
        if caption_text_val and len(caption_text_val.strip()) > 0:
            try:
                detected_caption_language = detect(caption_text_val)
            except Exception:
                detected_caption_language = "Undetectable"

        collected_posts.append({
            "Username": username_val,
            "Full Name": full_name_val,
            "Caption Text": (caption_text_val[:70] + '...') if len(caption_text_val) > 70 and caption_text_val != "N/A" else caption_text_val,
            "Hashtags": hashtags_val,
            "Is Video": str(is_video_val),
            "Likes": str(likes_count),
            "Comments": str(comments_count),
            "Video Views": str(video_views_val),
            "Created At": taken_at_formatted,
            "Instagram URL": instagram_url_val,
            "Caption Language": detected_caption_language
        })
    
    return collected_posts

# --- Example Usage ---
if __name__ == "__main__":
    # Define hashtags to process
    hashtags_to_process = ["honor400", "sunset", "travel"] # Example hashtags

    # List to store all collected post data rows for tabulate display
    collected_posts_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Username",
        "Full Name",
        "Caption Text",
        "Hashtags",
        "Is Video",
        "Likes",
        "Comments",
        "Video Views",
        "Created At",
        "Instagram URL",
        "Caption Language"
    ]

    print("--- Processing Instagram Hashtag Posts ---")

    for tag in hashtags_to_process:
        print(f"\n🔍 Fetching posts under #{tag}")
        posts = fetch_instagram_hashtag_media(tag) # Updated function call
        if posts:
            for post_item in posts:
                # Convert the dictionary output to a list based on output_headers order
                row_data_list = [post_item.get(header, 'N/A') for header in output_headers]
                collected_posts_for_output.append(row_data_list)
            print(f"Successfully extracted {len(posts)} posts for #{tag}.")
        else:
            print(f"No posts were found or an error occurred for #{tag}.")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_posts_for_output:
        print("\n--- Instagram Hashtag Posts Details Table ---")
        print(tabulate(collected_posts_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("---------------------------------------------")
    else:
        print("\nNo details collected for the specified Instagram hashtags.")
