# scrapers/utils.py

from datetime import datetime
import requests # Using requests for better HTTP handling

def safe_get(data, path, default="N/A"):
    """
    Safely gets nested dictionary values given a dot-separated path.
    Returns default if any part of the path is not found or is not a dictionary.
    """
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None: # If a key is found but its value is None, return default
                return default
        else:
            return default
    return value if value is not None else default

def format_timestamp(ts, include_time=True):
    """
    Formats a Unix timestamp (or similar numeric string) to a human-readable string.
    """
    if ts is None or ts == "N/A":
        return "N/A"
    try:
        # Attempt to convert to int, supporting string numbers
        ts_int = int(ts)
        # Handle milliseconds vs. seconds timestamps by checking magnitude
        if ts_int > 10**10: # Likely milliseconds
            ts_int //= 1000
        dt_object = datetime.utcfromtimestamp(ts_int)
        if include_time:
            return dt_object.strftime('%Y-%m-%d %H:%M:%S UTC')
        else:
            return dt_object.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return "Invalid timestamp"

def make_api_request(host, endpoint, headers=None, params=None):
    """
    Generic helper function to make an API request using requests library.
    """
    url = f"https://{host}{endpoint}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Error: Request to {url} timed out.")
        return {"error": "API request timed out"}
    except requests.exceptions.HTTPError as e:
        print(f"Error: HTTP error occurred during request to {url}: {e.response.status_code} - {e.response.text}")
        return {"error": f"API HTTP error: {e.response.status_code} - {e.response.text}"}
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to {host}.")
        return {"error": "API connection error"}
    except requests.exceptions.RequestException as e:
        print(f"Error during API request to {url}: {e}")
        return {"error": f"API request failed: {str(e)}"}
    except ValueError: # Catches JSONDecodeError if response is not valid JSON
        print(f"Error: Could not decode JSON from response for {url}. Response content: {response.text}")
        return {"error": "Invalid JSON response from API"}