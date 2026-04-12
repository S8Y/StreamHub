"""Platform support module for StreamHub"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
import asyncio
import subprocess
import os
import json
from pathlib import Path


class StreamStatus(Enum):
    """Stream status enumeration"""
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    LIVE = "live"
    RECORDING = "recording"
    ERROR = "error"


@dataclass
class StreamInfo:
    """Stream information"""
    username: str
    platform: str
    status: StreamStatus
    title: Optional[str] = None
    viewers: Optional[int] = None
    thumbnail: Optional[str] = None
    stream_url: Optional[str] = None


@dataclass
class Recording:
    """Recording information"""
    id: str
    username: str
    platform: str
    status: StreamStatus
    start_time: str
    duration: int = 0
    file_path: Optional[str] = None
    file_size: int = 0


class BasePlatform:
    """Base class for platform implementations"""
    
    site_name: str = "base"
    site_slug: str = "B"
    requires_auth: bool = False
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config: Dict[str, Any] = config if config is not None else {}
        self._session = None
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check if streamer is live"""
        raise NotImplementedError
    
    async def get_stream_url(self, username: str, quality: str = "best") -> str:
        """Get stream URL for recording"""
        raise NotImplementedError
    
    async def start_recording(self, username: str, output_dir: str) -> Recording:
        """Start recording process"""
        raise NotImplementedError
    
    async def stop_recording(self, recording_id: str) -> bool:
        """Stop a recording"""
        raise NotImplementedError
    
    def get_website_url(self, username: str) -> str:
        """Get the website URL for the streamer"""
        raise NotImplementedError


class StreamlinkPlatform(BasePlatform):
    """Base class for streamlink-based platforms (Twitch, Kick, YouTube)"""
    
    streamlink_path: str = "streamlink"
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check status using streamlink"""
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
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE,
                        title=data.get("title", ""),
                        stream_url=url
                    )
            return StreamInfo(
                username=username,
                platform=self.site_slug,
                status=StreamStatus.OFFLINE
            )
        except Exception as e:
            return StreamInfo(
                username=username,
                platform=self.site_slug,
                status=StreamStatus.ERROR
            )
    
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


# Platform registry
PLATFORMS: dict[str, type[BasePlatform]] = {}


def register_platform(platform_cls: type[BasePlatform]):
    """Register a platform class"""
    PLATFORMS[platform_cls.site_slug.lower()] = platform_cls
    return platform_cls


def get_platform(slug: str) -> Optional[type[BasePlatform]]:
    """Get platform class by slug"""
    return PLATFORMS.get(slug.lower())


def get_all_platforms() -> dict[str, type[BasePlatform]]:
    """Get all registered platforms"""
    return PLATFORMS.copy()


# Import and register all platforms
from backend.platforms import streamonitor, streamlink, fansly

__all__ = [
    'StreamStatus',
    'StreamInfo', 
    'Recording',
    'BasePlatform',
    'StreamlinkPlatform',
    'register_platform',
    'get_platform',
    'get_all_platforms'
]