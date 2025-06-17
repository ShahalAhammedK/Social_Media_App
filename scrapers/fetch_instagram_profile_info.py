import http.client
import urllib.parse
import json
from tabulate import tabulate # For pretty printing tables
import re # For extracting username/ID from URLs
from datetime import datetime # For formatting timestamps

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
RAPIDAPI_KEY = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016"
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

def format_timestamp(ts, include_time=True):
    """
    Formats a Unix timestamp into a human-readable string.
    """
    if ts == "N/A" or not ts:
        return "N/A"
    try:
        ts_int = int(ts)
        if include_time:
            return datetime.utcfromtimestamp(ts_int).strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            return datetime.utcfromtimestamp(ts_int).strftime('%Y-%m-%d')
    except Exception:
        return "Invalid timestamp"

def fetch_instagram_profile_info(profile_identifier):
    """
    Fetches detailed information for an Instagram profile using its username or URL.
    Returns a dictionary of extracted details.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    
    # Determine if the identifier is a URL or a username
    identifier_for_api = profile_identifier
    if profile_identifier.startswith("http"):
        # Regex to extract username from standard Instagram profile URLs
        match = re.search(r'(?:instagram\.com\/)([a-zA-Z0-9_\.]+)', profile_identifier)
        if match:
            identifier_for_api = match.group(1).replace('/', '') # Clean up potential trailing slash
        else:
            print(f"Error: Could not extract username from URL: {profile_identifier}. Skipping.")
            return None

    # Properly encode the identifier for the API endpoint
    encoded_identifier = urllib.parse.quote(identifier_for_api, safe='')
    endpoint = f"/v1/info?username_or_id_or_url={encoded_identifier}"
    
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read()

    try:
        json_data = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON response for {profile_identifier}.")
        return None
    finally:
        conn.close() # Close connection after each request

    data_payload = json_data.get("data", {})
    if not data_payload:
        error_message = json_data.get('message', 'No data found or API error occurred')
        print(f"API returned an error or no data for {profile_identifier}: {error_message}")
        return None

    # Extract all relevant profile data points
    username_val = safe_get(data_payload, "username")
    full_name_val = safe_get(data_payload, "full_name")
    follower_count = safe_get(data_payload, "follower_count")
    following_count = safe_get(data_payload, "following_count")
    posts_count = safe_get(data_payload, "media_count") # Total posts/media
    biography_text = safe_get(data_payload, "biography")
    external_url_val = safe_get(data_payload, "external_url")
    is_private_val = safe_get(data_payload, "is_private")
    is_verified_val = safe_get(data_payload, "is_verified")
    profile_pic_url_val = safe_get(data_payload, "profile_pic_url_hd") # High-definition profile picture

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

def fetch_instagram_user_recent_media(username, limit=5):
    """
    Fetches recent media (posts) for a given Instagram username.
    Returns a list of dictionaries, each representing a media item.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    encoded_username = urllib.parse.quote(username, safe='')
    # This endpoint typically lists recent media for a user
    endpoint = f"/v1/user_medias?username={encoded_username}&limit={limit}" 

    collected_media = []
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        json_data = json.loads(data.decode("utf-8"))

        if json_data.get("status") == "fail":
            print(f"API Error for user '{username}' media: {json_data.get('message', 'Unknown error')}")
            return []
        
        data_payload = json_data.get("data", {})
        if not data_payload:
            print(f"No media data payload received for user '{username}'.")
            return []

        # The API response for user media might contain a list of media items directly
        # or under a key like 'items' or 'edges'. Adjust the path as per actual API.
        media_items = safe_get(data_payload, "items", []) # Assuming 'items' contains the list of media

        for media in media_items:
            # Extract relevant details for each media item
            shortcode = safe_get(media, "shortcode")
            media_type = safe_get(media, "media_type") # e.g., "Image", "Video", "Carousel"
            thumbnail_url = safe_get(media, "thumbnail_url")
            like_count = safe_get(media, "metrics.like_count")
            comment_count = safe_get(media, "metrics.comment_count")
            taken_at = safe_get(media, "taken_at")
            caption_text = safe_get(media, "caption.text")

            # Construct the Instagram post URL
            post_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode != "N/A" else "N/A"

            collected_media.append({
                "Shortcode": shortcode,
                "Type": media_type,
                "Likes": str(like_count),
                "Comments": str(comment_count),
                "Post URL": post_url,
                "Taken At": format_timestamp(taken_at, include_time=False), # Only date for media
                "Thumbnail URL": thumbnail_url,
                "Caption Preview": (caption_text[:50] + '...') if len(caption_text) > 50 and caption_text != "N/A" else caption_text
            })
            if len(collected_media) >= limit: # Respect the limit even if API returns more
                break

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response for user media '{username}': {e}")
        print(f"Raw response: {data.decode('utf-8')}")
    except Exception as e:
        print(f"Error fetching user media for '{username}': {e}")
    finally:
        conn.close()
    
    return collected_media

# --- Example Usage ---
if __name__ == "__main__":
    print("--- Fetching Instagram Profile Information ---")
    # Example Instagram Username or URL
    profile_identifier = "mrbeast" # You can also use "https://www.instagram.com/therock/"

    profile_info = fetch_instagram_profile_info(profile_identifier)
    if profile_info:
        # Prepare data for tabulate
        headers = list(profile_info.keys())
        data_row = list(profile_info.values())
        print(tabulate([data_row], headers=headers, tablefmt="fancy_grid"))
    else:
        print(f"Failed to retrieve profile details for {profile_identifier}")

    print("\n" + "="*80 + "\n")

    print("--- Fetching Instagram User Recent Media ---")
    user_for_media = "instagram" # Example user whose media we want to fetch
    media_limit = 3 # Number of recent media items to fetch

    print(f"\nFetching {media_limit} recent media for: @{user_for_media}")
    recent_media_data = fetch_instagram_user_recent_media(user_for_media, media_limit)

    if recent_media_data:
        # Prepare data for tabulate
        headers = list(recent_media_data[0].keys()) if recent_media_data else []
        data_rows = [[item[header] for header in headers] for item in recent_media_data]
        print(tabulate(data_rows, headers=headers, tablefmt="fancy_grid"))
    else:
        print(f"No recent media collected for @{user_for_media}.")
