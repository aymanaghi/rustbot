"""
steam/client.py
Handles Steam login, session management, and Steam Guard 2FA.
"""

import os
import logging
from dotenv import load_dotenv
from steampy.client import SteamClient
from steampy.models import GameOptions

load_dotenv()
logger = logging.getLogger(__name__)

RUST_APP_ID = "252490"
RUST_CONTEXT_ID = "2"


class SteamSession:
    def __init__(self):
        self.username = os.getenv("STEAM_USERNAME")
        self.password = os.getenv("STEAM_PASSWORD")
        self.api_key = os.getenv("STEAM_API_KEY")
        self.steam_id = os.getenv("STEAM_ID_64")
        self.shared_secret = os.getenv("STEAM_SHARED_SECRET")
        self.identity_secret = os.getenv("STEAM_IDENTITY_SECRET")

        if not all([self.username, self.password, self.api_key, self.steam_id]):
            raise EnvironmentError(
                "Missing required Steam credentials in .env file. "
                "Check STEAM_USERNAME, STEAM_PASSWORD, STEAM_API_KEY, STEAM_ID_64."
            )

        self.client = SteamClient(self.api_key)
        self._logged_in = False

    def login(self) -> bool:
        """Log into Steam with optional Mobile Authenticator support."""
        try:
            logger.info(f"Logging into Steam as {self.username}...")

            if self.shared_secret:
                # Full login with Mobile Authenticator (recommended)
                self.client.login(
                    username=self.username,
                    password=self.password,
                    steam_guard={
                        "shared_secret": self.shared_secret,
                        "identity_secret": self.identity_secret,
                    },
                )
            else:
                # Basic login without 2FA (will fail if Steam Guard is enabled)
                self.client.login(
                    username=self.username,
                    password=self.password,
                )

            self._logged_in = True
            logger.info("Steam login successful.")
            return True

        except Exception as e:
            logger.error(f"Steam login failed: {e}")
            self._logged_in = False
            return False

    def ensure_logged_in(self):
        """Re-login if session has expired."""
        if not self._logged_in:
            success = self.login()
            if not success:
                raise ConnectionError("Unable to establish Steam session.")

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
