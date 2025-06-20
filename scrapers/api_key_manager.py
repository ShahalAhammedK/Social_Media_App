# scrapers/api_key_manager.py
import os
from dotenv import load_dotenv

load_dotenv()

class RapidAPIKeyManager:
    def __init__(self):
        self.api_keys = []
        i = 1
        while True:
            key = os.getenv(f"RAPIDAPI_KEY_{i}")
            if key:
                self.api_keys.append(key)
                i += 1
            else:
                break

        if not self.api_keys:
            single_key = os.getenv("RAPIDAPI_KEY")
            if single_key:
                self.api_keys.append(single_key)
            else:
                raise ValueError("No RapidAPI keys found in environment variables (e.g., RAPIDAPI_KEY or RAPIDAPI_KEY_1, RAPIDAPI_KEY_2...)")

        self.current_key_index = 0
        self.max_key_rotations = len(self.api_keys)

    def get_current_key(self):
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_index]

    def rotate_key(self):
        if not self.api_keys:
            return False

        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        print(f"Rotating to next RapidAPI key (index: {self.current_key_index}).")

        if self.current_key_index == 0:
            return False
        return True

    # --- MODIFIED METHOD ---
    def get_headers(self, host: str): # Add host parameter here
        key = self.get_current_key()
        if not key:
            raise ValueError("No active RapidAPI key available.")
        return {
            "x-rapidapi-key": key,
            "x-rapidapi-host": host # Use the passed host here
        }

rapidapi_key_manager = RapidAPIKeyManager()