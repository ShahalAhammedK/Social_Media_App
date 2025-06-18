import http.client
import urllib.parse
import json
from tabulate import tabulate # For pretty printing tables
import re # For extracting username/ID from URLs
from datetime import datetime # Although not explicitly used in this snippet, kept for consistency with utils

# Note: If you encounter an error like "ModuleNotFoundError: No module named 'tabulate'",
# you need to install the tabulate library. Open your terminal or command prompt and run:
# pip install tabulate

# --- Configuration ---
# Instagram API
RAPIDAPI_KEY = "06e813f846mshd0abac9d8ccb0e0p17d5e9jsn610b6a71b016" # Your RapidAPI key
RAPIDAPI_HOST = "simple-instagram-api.p.rapidapi.com"

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

def fetch_instagram_profile_info(profile_identifier):
    """
    Fetches detailed information for an Instagram profile using its username or URL
    from the 'simple-instagram-api'.
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
    endpoint = f"/account-info?username={encoded_identifier}" 
    
    try:
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()

        raw_response_str = data.decode("utf-8")
        json_data = json.loads(raw_response_str)

        # Check if the response contains expected data (e.g., 'username' is present)
        if safe_get(json_data, "username") == "N/A":
            error_message = safe_get(json_data, 'message', 'No specific error message provided.')
            # If the API returns a status or error message, prioritize that
            if safe_get(json_data, 'status') == 'error':
                error_message = safe_get(json_data, 'error', error_message)
            print(f"API returned no data or an error for {profile_identifier}: {error_message}")
            # print(f"Full response for debugging: {json.dumps(json_data, indent=2)}") # Uncomment for debugging
            return None

        username_val = safe_get(json_data, "username")
        full_name_val = safe_get(json_data, "full_name")
        # Corrected paths based on the JSON example
        follower_count = safe_get(json_data, "edge_followed_by.count")
        following_count = safe_get(json_data, "edge_follow.count")
        posts_count = safe_get(json_data, "edge_owner_to_timeline_media.count")
        
        # biography_text = safe_get(json_data, "biography") # Not used in final output
        # external_url_val = safe_get(json_data, "external_url")
        # is_private_val = safe_get(json_data, "is_verified")
        # is_verified_val = safe_get(json_data, "is_verified")
        # profile_pic_url_val = safe_get(json_data, "profile_pic_url_hd")

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
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON response for {profile_identifier}.")
        # print(f"Raw response: {raw_response_str}") # Uncomment for debugging
        return None
    except Exception as e:
        print(f"An unexpected error occurred for {profile_identifier}: {e}")
        return None
    finally:
        conn.close() # Close connection after each request

# --- Example Usage ---
if __name__ == "__main__":
    # List of Instagram usernames or profile URLs to process
    instagram_profile_identifiers = [
        "mrbeast",
        "https://www.instagram.com/therock/",
        "charlidamelio",
        "https://www.instagram.com/arianagrande/",
        "nonexistent_user_12345" # Example of a potentially non-existent user
    ]

    # List to store all collected profile data rows for tabulate display
    collected_profile_rows_for_output = []

    # Define the headers for the output table
    output_headers = [
        "Username",
        "Full Name",
        "Followers",
        "Following",
        "Posts Count",
        "Profile URL"
    ]

    print("--- Processing Instagram Profiles ---")

    for profile_identifier in instagram_profile_identifiers:
        print(f"\nFetching info for: {profile_identifier}")
        profile_info = fetch_instagram_profile_info(profile_identifier)
        if profile_info:
            # Convert the dictionary output to a list based on output_headers order
            row_data_list = [profile_info.get(header, 'N/A') for header in output_headers]
            collected_profile_rows_for_output.append(row_data_list)
            print("Successfully extracted all profile details.")
        else:
            print(f"Failed to retrieve profile details for {profile_identifier}.")
        print("-" * 40)

    # Print the collected data as a formatted table
    if collected_profile_rows_for_output:
        print("\n--- Instagram Profile Details Table ---")
        print(tabulate(collected_profile_rows_for_output, headers=output_headers, tablefmt="fancy_grid"))
        print("---------------------------------------")
    else:
        print("\nNo details collected for the specified Instagram profiles.")
