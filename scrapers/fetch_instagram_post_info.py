import http.client
import urllib.parse
import json
from datetime import datetime
import re
from langdetect import detect, DetectorFactory

# Set consistent results for language detection
DetectorFactory.seed = 0

# --- Configuration ---
RAPIDAPI_KEY = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016"  # Replace with your actual key
RAPIDAPI_HOST = "instagram-social-api.p.rapidapi.com"

headers = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": RAPIDAPI_HOST
}

def safe_get(data, path, default="N/A"):
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, {})
        else:
            return default
    return value if value else default

def format_timestamp(ts, include_time=True):
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

def fetch_instagram_post_info(post_identifier):
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    
    # Extract shortcode from URL if needed
    post_shortcode = post_identifier
    if post_identifier.startswith("http"):
        match = re.search(r'(?:instagram\.com\/p\/|instagram\.com\/reel\/)([a-zA-Z0-9_-]+)', post_identifier)
        if match:
            post_shortcode = match.group(1)
        else:
            print(f"Error: Could not extract shortcode from URL: {post_identifier}")
            return None

    encoded_identifier = urllib.parse.quote(post_shortcode, safe='')
    endpoint = f"/v1/post_info?code_or_id_or_url={encoded_identifier}"

    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        json_data = json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None
    finally:
        conn.close()

    data_payload = json_data.get("data", {})
    if not data_payload:
        return None

    is_video = data_payload.get("is_video", False)

    caption_text = safe_get(data_payload, "caption.text") 
    likes_count = safe_get(data_payload, "metrics.like_count")
    comments_count = safe_get(data_payload, "metrics.comment_count")
    shares_count = safe_get(data_payload, "metrics.share_count", "N/A")
    video_views_count = safe_get(data_payload, "metrics.play_count") if is_video else "N/A"
    raw_taken_at = safe_get(data_payload, "caption.created_at")
    taken_at_formatted = format_timestamp(raw_taken_at, include_time=True)
    username_val = safe_get(data_payload, "user.username")
    full_name_val = safe_get(data_payload, "user.full_name")

    instagram_post_url = post_identifier
    if not post_identifier.startswith("http"):
        instagram_post_url = f"https://www.instagram.com/p/{post_shortcode}/"

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
