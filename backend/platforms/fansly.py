"""Fansly platform implementation"""
import json
import time
from typing import Optional, Dict, Any
import requests
from . import BasePlatform, StreamStatus, StreamInfo, Recording, register_platform


class FanslyPlatform(BasePlatform):
    """Fansly platform"""
    
    site_name = "Fansly"
    site_slug = "FL"
    requires_auth = True
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """Setup session with auth token"""
        auth_token = self.config.get("auth_token", "")
        if auth_token:
            self.session.headers.update({
                "Authorization": f"Bearer {auth_token}"
            })
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check if streamer is live on Fansly"""
        # Fansly uses a different API - check for live
        url = f"https://api.fansly.com/content/v1beta/account/{username}"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                # Check for live streaming status
                if data.get("isLive") or data.get("isBroadcasting"):
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE,
                        title=data.get("displayName", username)
                    )
            return StreamInfo(
                username=username,
                platform=self.site_slug,
                status=StreamStatus.OFFLINE
            )
        except Exception:
            return StreamInfo(
                username=username,
                platform=self.site_slug,
                status=StreamStatus.ERROR
            )
    
    async def get_stream_url(self, username: str, quality: str = "best") -> str:
        """Get HLS stream URL from Fansly"""
        # Fansly uses M3U8 HLS streams for live
        url = f"https://api.fansly.com/streaming/{username}/m3u8"
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return data.get("url", "")
        except Exception:
            pass
        return ""
    
    def get_website_url(self, username: str) -> str:
        return f"https://fansly.com/live/{username}"


# Register platform
register_platform(FanslyPlatform)


__all__ = ['FanslyPlatform']