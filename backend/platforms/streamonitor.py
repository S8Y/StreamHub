"""Platform implementations using StreaMonitor-style architecture"""
import json
import os
import subprocess
from typing import Optional
import requests
from . import BasePlatform, StreamStatus, StreamInfo, Recording, register_platform


class RoomIdBot(BasePlatform):
    """Base class for API-based platforms (Room ID-based)"""
    
    api_base: str = ""
    headers: dict = {}
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check if streamer is live via API"""
        url = self._get_api_url(username)
        try:
            response = self._session.get(url, headers=self.headers, timeout=15)
            data = response.json()
            return self._parse_status(username, data)
        except Exception:
            return StreamInfo(
                username=username,
                platform=self.site_slug,
                status=StreamStatus.ERROR
            )
    
    def _session(self):
        """Get or create requests session"""
        if not hasattr(self, '_session_obj'):
            self._session_obj = requests.Session()
        return self._session_obj
    
    def _get_api_url(self, username: str) -> str:
        """Get the API URL for status check"""
        raise NotImplementedError
    
    def _parse_status(self, username: str, data: dict) -> StreamInfo:
        """Parse API response to StreamInfo"""
        raise NotImplementedError
    
    async def get_room_id(self, username: str) -> Optional[str]:
        """Get room ID from username"""
        url = self._get_api_url(username)
        try:
            response = self._session.get(url, headers=self.headers, timeout=15)
            data = response.json()
            return self._extract_room_id(data)
        except Exception:
            return None
    
    def _extract_room_id(self, data: dict) -> Optional[str]:
        """Extract room ID from API response"""
        return None


class StripChatPlatform(RoomIdBot):
    """StripChat platform"""
    
    site_name = "StripChat"
    site_slug = "SC"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://stripchat.com/api/front/v2/models/username/{username}/cam"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                is_live = data.get("isLive", False)
                if is_live:
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE,
                        title=data.get("displayName", username),
                        viewers=data.get("viewerCount", 0)
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
        """Get HLS stream URL from StripChat"""
        room_id = await self.get_room_id(username)
        if not room_id:
            return None
        return f"https://edge-hls.doppiocdn.com/hls/{room_id}/master/{room_id}_auto.m3u8"
    
    def get_website_url(self, username: str) -> str:
        return f"https://stripchat.com/{username}"


class ChaturbatePlatform(RoomIdBot):
    """Chaturbate platform - uses streamlink for recording"""
    
    site_name = "Chaturbate"
    site_slug = "CB"
    
    async def get_status(self, username: str) -> StreamInfo:
        """Check if streamer is live - uses streamlink for reliability"""
        import subprocess
        import json
        
        try:
            # Use streamlink to check status (more reliable than scraping)
            result = subprocess.run(
                ['streamlink', '--json', '--no-cache', f'https://chaturbate.com/{username}', 'best'],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if data.get('streams'):
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE
                    )
        except:
            pass
        
        # Fallback to page check
        try:
            url = f"https://chaturbate.com/{username}"
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                # Check first 500 chars for offline indicator
                if 'offline' not in response.text[:500].lower():
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE
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
    
    async def get_stream_url(self, username: str, quality: str = "best") -> Optional[str]:
        """Get stream URL - now handled by streamlink in recorder"""
        # Return None since we use streamlink for recording
        return None
    
    def get_website_url(self, username: str) -> str:
        return f"https://chaturbate.com/{username}"


class CamSodaPlatform(RoomIdBot):
    """CamSoda platform"""
    
    site_name = "CamSoda"
    site_slug = "CS"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://camsoda.com/api/v1/user/{username}/status"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                is_online = data.get("is_online", False)
                if is_online:
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE,
                        title=data.get("room_name", ""),
                        viewers=data.get("viewers_n", 0)
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
        return f"https://play.camsoda.com/{username}"
    
    def get_website_url(self, username: str) -> str:
        return f"https://camsoda.com/{username}"


class Flirt4FreePlatform(RoomIdBot):
    """Flirt4Free platform"""
    
    site_name = "Flirt4Free"
    site_slug = "F4F"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://www.flirt4free.com/ajax/roomstatus.php?username={username}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "offline")
                if status == "online":
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE
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
    
    def get_website_url(self, username: str) -> str:
        return f"https://www.flirt4free.com/{username}"


class MyFreeCamsPlatform(RoomIdBot):
    """MyFreeCams platform"""
    
    site_name = "MyFreeCams"
    site_slug = "MFC"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://models.myfreecams.com/api2/jsonfcgi.php?method=user.getDetails&name[0]={username}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                user_data = data.get("user", {})
                if user_data.get("current_show") or user_data.get("status") == "public":
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE
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
    
    def get_website_url(self, username: str) -> str:
        return f"https://myfreecams.com/{username}"


class Cam4Platform(RoomIdBot):
    """Cam4 platform"""
    
    site_name = "Cam4"
    site_slug = "C4"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://cam4.com/rest/v1.3/channel/{username}/info"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("channel", {}).get("online"):
                    return StreamInfo(
                        username=username,
                        platform=self.site_slug,
                        status=StreamStatus.LIVE
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
    
    def get_website_url(self, username: str) -> str:
        return f"https://cam4.com/{username}"


class BongacamsPlatform(RoomIdBot):
    """Bongacams platform"""
    
    site_name = "Bongacams"
    site_slug = "BC"
    
    async def get_status(self, username: str) -> StreamInfo:
        url = f"https://bongacams.com/{username}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200 and "room" in response.text:
                return StreamInfo(
                    username=username,
                    platform=self.site_slug,
                    status=StreamStatus.LIVE
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
    
    def get_website_url(self, username: str) -> str:
        return f"https://bongacams.com/{username}"


# Register all platforms
register_platform(StripChatPlatform)
register_platform(ChaturbatePlatform)
register_platform(CamSodaPlatform)
register_platform(Flirt4FreePlatform)
register_platform(MyFreeCamsPlatform)
register_platform(Cam4Platform)
register_platform(BongacamsPlatform)


__all__ = [
    'RoomIdBot',
    'StripChatPlatform',
    'ChaturbatePlatform', 
    'CamSodaPlatform',
    'Flirt4FreePlatform',
    'MyFreeCamsPlatform',
    'Cam4Platform',
    'BongacamsPlatform'
]