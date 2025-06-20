# scrapers/fetch_instagram_post_info.py
import http.client
import urllib.parse
import json
import re
from langdetect import detect, DetectorFactory

from .utils import safe_get, format_timestamp
from .api_key_manager import rapidapi_key_manager

DetectorFactory.seed = 0

# --- Configuration (Host for Instagram API) ---
RAPIDAPI_HOST = "instagram-social-api.p.rapidapi.com" # Keep this defined here

def fetch_instagram_post_info(post_identifier):
    post_shortcode = post_identifier
    url_path_type = "p"  # Default to 'p' for posts

    if post_identifier.startswith("http"):
        # Regex to extract shortcode and determine if it's a reel or a regular post URL
        match = re.search(r'(?:instagram\.com\/(p|reel)\/)([a-zA-Z0-9_-]+)', post_identifier)
        if match:
            url_path_type = match.group(1) # 'p' or 'reel'
            post_shortcode = match.group(2)
        else:
            print(f"Error: Could not extract shortcode from URL: {post_identifier}")
            return {"error": f"Invalid Instagram post URL or identifier: {post_identifier}"}

    encoded_identifier = urllib.parse.quote(post_shortcode, safe='')
    endpoint = f"/v1/post_info?code_or_id_or_url={encoded_identifier}"

    for _ in range(rapidapi_key_manager.max_key_rotations):
        try:
            current_headers = rapidapi_key_manager.get_headers(RAPIDAPI_HOST) # Pass RAPIDAPI_HOST
            conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
            conn.request("GET", endpoint, headers=current_headers)
            res = conn.getresponse()
            data = res.read()
            json_data = json.loads(data.decode("utf-8"))
            conn.close()

            error_message = json_data.get("message") or json_data.get("error")

            if res.status == 429:
                print(f"Rate limit hit with current key (index: {rapidapi_key_manager.current_key_index}). Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for rate limit."}
                continue
            elif "not subscribed" in str(error_message).lower() or "invalid api key" in str(error_message).lower() or res.status in [401, 403]:
                print(f"Current key (index: {rapidapi_key_manager.current_key_index}) invalid or subscription issue. Rotating key...")
                if not rapidapi_key_manager.rotate_key():
                    return {"error": "All RapidAPI keys exhausted or invalid for subscription/authentication."}
                continue
            elif res.status != 200:
                print(f"API Error {res.status}: {error_message}. Not a rate limit, returning error.")
                return {"error": f"API Error {res.status}: {error_message}"}

            break

        except http.client.HTTPException as e:
            print(f"HTTP connection error: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to HTTP connection errors."}
            continue
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}. Raw response: {data.decode('utf-8')}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": "All RapidAPI keys exhausted due to invalid JSON responses."}
            continue
        except Exception as e:
            print(f"An unexpected error occurred: {e}. Retrying with next key...")
            if not rapidapi_key_manager.rotate_key():
                return {"error": f"All RapidAPI keys exhausted due to unexpected errors: {str(e)}"}
            continue
    else:
        return {"error": "Failed to fetch Instagram post info after trying all available API keys."}

    data_payload = json_data.get("data", {})
    if not data_payload:
        return {"error": "No data payload found in API response."}

    is_video = data_payload.get("is_video", False) # This indicates if the media is a video, not necessarily a 'reel' URL type.

    caption_text = safe_get(data_payload, "caption.text")
    likes_count = safe_get(data_payload, "metrics.like_count")
    comments_count = safe_get(data_payload, "metrics.comment_count")
    shares_count = safe_get(data_payload, "metrics.share_count", "N/A")
    video_views_count = safe_get(data_payload, "metrics.play_count") if is_video else "N/A"
    raw_taken_at = safe_get(data_payload, "caption.created_at")
    taken_at_formatted = format_timestamp(raw_taken_at, include_time=True)
    username_val = safe_get(data_payload, "user.username")
    full_name_val = safe_get(data_payload, "user.full_name")

    # Construct the Instagram post URL using the determined url_path_type
    instagram_post_url = f"https://www.instagram.com/{url_path_type}/{post_shortcode}/"


    author_profile_url = f"https://www.instagram.com/{username_val}/" if username_val != "N/A" else "N/A"

    detected_caption_language = "N/A"
    if caption_text and len(caption_text.strip()) > 0:
        try:
            detected_caption_language = detect(caption_text)
        except Exception as e:
            detected_caption_language = "Undetectable"

    return {
        "Caption": caption_text,
        "Likes": str(likes_count),
        "Comments": str(comments_count),
        "Shares": str(shares_count),
        "Video Views": str(video_views_count),
        "Created At": taken_at_formatted,
        "Username": username_val,
        "Full Name": full_name_val,
        "Post URL": instagram_post_url,
        "Author Profile URL": author_profile_url,
        "Caption Language": detected_caption_language
    }
