import os
from pathlib import Path
from instagrapi import Client


class InstagramClient:
    def __init__(self, username: str = None, password: str = None, session_path: str = "insta_session.json"):
        self.cl = Client()
        self.session_path = Path(session_path)

        username = os.environ.get("IG_USERNAME", username)
        password = os.environ.get("IG_PASSWORD", password)
        if not username or not password:
            raise RuntimeError("IG_USERNAME and IG_PASSWORD must be set in env or passed to InstagramClient.")

        if self.session_path.exists():
            self.cl.load_settings(str(self.session_path))
            try:
                self.cl.login(username, password)
                return
            except Exception:
                pass  # fall back to clean login if session invalid

        self.cl.login(username, password)
        self.cl.dump_settings(str(self.session_path))

    def upload_photo(self, image_path: str, caption: str) -> str:
        media = self.cl.photo_upload(image_path, caption)
        return str(media.pk)
    
    def album_upload(self, image_paths: list, caption: str) -> str:
        media = self.cl.album_upload(image_paths, caption)
        return str(media.pk)
