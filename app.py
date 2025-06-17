import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template

# Load environment variables from .env file
load_dotenv()

# Import all your individual fetching functions from the scrapers package
from scrapers import (
    fetch_instagram_post_info,
    fetch_instagram_profile_info,
    fetch_instagram_hashtag_media,
    fetch_tiktok_post_info,
    fetch_tiktok_profile_info,
    fetch_youtube_post_info,
    fetch_youtube_profile_info,
    fetch_snapchat_profile_info
)

app = Flask(__name__)

@app.route('/')
def home():
    """Renders the main HTML page for the social media info fetcher."""
    return render_template("index.html")

@app.route('/api/fetch-info', methods=['POST'])
def get_info():
    """
    API endpoint to fetch social media information for multiple inputs.
    Expects a JSON payload with 'type' and a list of 'identifiers'.
    """
    data = request.get_json()
    info_type = data.get("type", "")
    identifiers = data.get("identifiers", []) # Now expecting a list of identifiers

    # Basic validation
    if not info_type or not identifiers:
        return jsonify({"error": "Missing 'type' or 'identifiers' in request. Please provide at least one identifier."}), 400

    all_results = []
    overall_status = "success" # Will be "partial_success" or "failure" if errors occur

    for identifier in identifiers:
        info_for_current_identifier = None
        current_item_error_message = None

        try:
            # Call the appropriate scraper function based on info_type
            if info_type == "instagram_post":
                info_for_current_identifier = fetch_instagram_post_info(identifier)
            elif info_type == "instagram_profile":
                info_for_current_identifier = fetch_instagram_profile_info(identifier)
            elif info_type == "instagram_hashtag":
                # Instagram Hashtag Media returns a LIST of posts.
                # We need to extend the main all_results list with these.
                hashtag_posts = fetch_instagram_hashtag_media(identifier)
                if hashtag_posts and isinstance(hashtag_posts, list):
                    all_results.extend(hashtag_posts)
                elif hashtag_posts and isinstance(hashtag_posts, dict) and hashtag_posts.get("error"):
                    current_item_error_message = hashtag_posts["error"]
                    overall_status = "partial_success" # At least one error occurred
                else:
                    current_item_error_message = "No data or unexpected format from Instagram Hashtag Media API."
                    overall_status = "partial_success"

            elif info_type == "tiktok_post":
                info_for_current_identifier = fetch_tiktok_post_info(identifier)
            elif info_type == "tiktok_profile":
                info_for_current_identifier = fetch_tiktok_profile_info(identifier)
            elif info_type == "youtube_post":
                info_for_current_identifier = fetch_youtube_post_info(identifier)
            elif info_type == "youtube_profile":
                info_for_current_identifier = fetch_youtube_profile_info(identifier)
            elif info_type == "snapchat_profile":
                info_for_current_identifier = fetch_snapchat_profile_info(identifier)
            else:
                current_item_error_message = "Invalid info type provided."
                overall_status = "partial_success" # Invalid type counts as an error for that item

            # If a single item (not a list from hashtag) was fetched and it's not an error
            if info_for_current_identifier and isinstance(info_for_current_identifier, dict) and not info_for_current_identifier.get("error"):
                all_results.append(info_for_current_identifier)
            # If a single item was fetched but it contained an error
            elif info_for_current_identifier and isinstance(info_for_current_identifier, dict) and info_for_current_identifier.get("error"):
                current_item_error_message = info_for_current_identifier["error"]
                overall_status = "partial_success" # An error occurred for this item

        except Exception as e:
            import traceback
            traceback.print_exc() # Print full traceback to console for debugging
            current_item_error_message = f"An unexpected server error occurred for identifier '{identifier}': {str(e)}"
            overall_status = "partial_success" # Mark as partial success due to an error

        # If there was an error for the current identifier, add an error record to results
        if current_item_error_message:
            all_results.append({
                "Requested Identifier": identifier,
                "Status": "Failed",
                "Error Details": current_item_error_message,
                "Platform": info_type.split('_')[0].capitalize() # Get platform name
            })

    # Determine final response based on overall status
    if not all_results and overall_status == "partial_success":
        # This case means all requests failed or returned no data
        return jsonify({"error": "No data could be fetched for any of the provided identifiers, or all failed. Please check inputs and API keys."}), 500
    elif overall_status == "partial_success":
        # Some items succeeded, some failed
        return jsonify({
            "results": all_results,
            "warning": "Some identifiers failed to fetch data. Please check the 'Status' and 'Error Details' for individual records."
        }), 200
    else:
        # All items succeeded
        return jsonify({"results": all_results}), 200

if __name__ == '__main__':
    # Run the Flask app in debug mode. Set debug=False for production.
    app.run(debug=True)

