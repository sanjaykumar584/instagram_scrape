import os
from pathlib import Path
from typing import List, Dict

from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

SETTINGS_PATH = Path(__file__).parent / "data" / "ig_settings.json"


class InstagramService:
    def __init__(self) -> None:
        self.client = Client()
        self.logged_in = False

    def _credentials(self) -> Dict[str, str]:
        return {
            "username": os.getenv("IG_USERNAME", "").strip(),
            "password": os.getenv("IG_PASSWORD", "").strip(),
        }

    def login(self) -> bool:
        creds = self._credentials()
        if not creds["username"] or not creds["password"]:
            return False

        if SETTINGS_PATH.exists():
            try:
                self.client.load_settings(SETTINGS_PATH)
            except Exception:
                pass

        try:
            self.client.login(creds["username"], creds["password"])  # persists device if settings loaded
            self.logged_in = True
            try:
                self.client.dump_settings(SETTINGS_PATH)
            except Exception:
                pass
            return True
        except Exception:
            self.logged_in = False
            return False

    def ensure_login(self) -> None:
        if not self.logged_in:
            ok = self.login()
            if not ok:
                raise RuntimeError("Instagram login failed or credentials missing")

    def maybe_login_on_startup(self) -> bool:
        return self.login()

    def search_users(self, query: str, limit: int = 10) -> List[Dict]:
        self.ensure_login()
        users = self.client.user_search(query) or []
        results = []
        for u in users[:limit]:
            results.append({
                "id": getattr(u, "pk", None),
                "username": getattr(u, "username", None),
                "full_name": getattr(u, "full_name", None),
                "is_private": getattr(u, "is_private", None),
                "profile_pic_url": getattr(u, "profile_pic_url", None),
            })
        return results

    def get_profile(self, username: str) -> Dict:
        self.ensure_login()
        user_id = self.client.user_id_from_username(username)
        info = self.client.user_info(user_id)
        return {
            "id": getattr(info, "pk", None),
            "username": getattr(info, "username", None),
            "full_name": getattr(info, "full_name", None),
            "biography": getattr(info, "biography", None),
            "is_private": getattr(info, "is_private", None),
            "is_verified": getattr(info, "is_verified", None),
            "follower_count": getattr(info, "follower_count", None),
            "following_count": getattr(info, "following_count", None),
            "media_count": getattr(info, "media_count", None),
            "external_url": getattr(info, "external_url", None),
            "profile_pic_url": getattr(info, "profile_pic_url", None),
        }


service = InstagramService()
