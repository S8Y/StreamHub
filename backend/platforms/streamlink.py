"""Streamlink-based platforms (Twitch, Kick, YouTube)"""
import json
import subprocess
from typing import Optional
import requests
from . import BasePlatform, StreamStatus, StreamInfo, Recording, register_platform


class StreamlinkPlatform(BasePlatform):
    """Base class for streamlink-based platforms"""
    
    streamlink_path: str = "streamlink"
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check status using streamlink CLI"""
        url = self._get_url(username)
        try:
            result = subprocess.run(
                [self.streamlink_path, url, "--json", "--no-cache"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("streams"):
                    meta = data.get("meta", {})
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE,
                        title=meta.get("title", ""),
                        viewers=meta.get("viewer", 0)
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
        """Get stream URL using streamlink"""
        url = self._get_url(username)
        quality_arg = self._get_quality_arg(quality)
        try:
            result = subprocess.run(
                [self.streamlink_path, url, quality_arg, "--print", "--url-only"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return url
    
    def _get_url(self, username: str) -> str:
        """Get the platform URL for username"""
        raise NotImplementedError
    
    def _get_quality_arg(self, quality: str) -> str:
        """Convert quality to streamlink quality arg"""
        quality_map = {
            "best": "best",
            "1080p": "1080p",
            "720p": "720p",
            "480p": "480p",
            "worst": "worst"
        }
        return quality_map.get(quality, "best")
    
    def get_website_url(self, username: str) -> str:
        return self._get_url(username)


class TwitchPlatform(StreamlinkPlatform):
    """Twitch platform"""
    
    site_name = "Twitch"
    site_slug = "TW"
    
    def _get_url(self, username: str) -> str:
        return f"https://www.twitch.tv/{username}"


class KickPlatform(StreamlinkPlatform):
    """Kick platform"""
    
    site_name = "Kick"
    site_slug = "KC"
    
    def _get_url(self, username: str) -> str:
        return f"https://kick.com/{username}"


class YouTubePlatform(StreamlinkPlatform):
    """YouTube platform"""
    
    site_name = "YouTube"
    site_slug = "YT"
    
    def _get_url(self, username: str) -> str:
        return f"https://www.youtube.com/@{username}"


# Register platforms
register_platform(TwitchPlatform)
register_platform(KickPlatform)
register_platform(YouTubePlatform)


__all__ = [
    'StreamlinkPlatform',
    'TwitchPlatform',
    'KickPlatform',
    'YouTubePlatform'
]