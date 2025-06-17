# scrapers/__init__.py

# Import and re-export each individual fetch function from its own file
from .fetch_instagram_post_info import fetch_instagram_post_info
from .fetch_instagram_profile_info import fetch_instagram_profile_info
from .fetch_instagram_hashtag_media import fetch_instagram_hashtag_media
from .fetch_tiktok_post_info import fetch_tiktok_post_info
from .fetch_tiktok_profile_info import fetch_tiktok_profile_info
from .fetch_youtube_post_info import fetch_youtube_post_info
from .fetch_youtube_profile_info import fetch_youtube_profile_info
from .fetch_snapchat_profile_info import fetch_snapchat_profile_info

# Optional: Define __all__ for explicit 'from scrapers import *' behavior
# This specifies what symbols are imported when `from scrapers import *` is used.
__all__ = [
    'fetch_instagram_post_info',
    'fetch_instagram_profile_info',
    'fetch_instagram_hashtag_media',
    'fetch_tiktok_post_info',
    'fetch_tiktok_profile_info',
    'fetch_youtube_post_info',
    'fetch_youtube_profile_info',
    'fetch_snapchat_profile_info'
]