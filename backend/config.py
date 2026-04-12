"""Configuration management for StreamHub - All features from StreaMonitor, StreamWarden, Fansly-scraper"""
import os
import sys
import json
import platform
from pathlib import Path

def get_default_dirs():
    """Get default directories based on OS"""
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get('USERPROFILE', Path.home()))
        recordings = base / "Videos" / "StreamHub"
        cache = base / "AppData" / "Local" / "StreamHub" / "cache"
    elif system == "Darwin":  # macOS
        base = Path.home()
        recordings = base / "Movies" / "StreamHub"
        cache = base / "Library" / "Caches" / "StreamHub"
    else:  # Linux
        base = Path.home()
        recordings = base / "Videos" / "StreamHub"
        cache = base / ".cache" / "StreamHub"
    
    return str(recordings), str(cache)

DEFAULT_DOWNLOADS, DEFAULT_CACHE = get_default_dirs()

class Config:
    """Main configuration manager with all original project features"""
    
    DEFAULT_CONFIG = {
        # Web Interface
        "web_port": 6969,
        "username": "admin",
        "password": "",
        
        # Recording Settings
        "downloads_dir": DEFAULT_DOWNLOADS,
        "cache_dir": DEFAULT_CACHE,
        "quality": "best",
        "quality_preference": "prefer_higher",
        "container": "mp4",
        "auto_record": True,
        
        # Compression - efficient re-encode for space saving
        "compress_recordings": False,
        "compression_preset": "medium",  # ultrafast, fast, medium, slow, veryslow
        "compression_crf": 23,  # 18=visually lossless, 23=default, 28=smaller
        
        # Monitoring Settings
        "poll_interval": 180,  # 3 minutes
        "check_on_startup": True,
        
        # FFmpeg Settings
        "ffmpeg_path": "ffmpeg",
        "ffmpeg_recording_options": "-movflags +faststart",
        "ffmpeg_convert": True,
        "ffmpeg_output_options": "-c:v libx264 -crf 23 -preset fast",
        
        # Streamlink Settings
        "streamlink_path": "streamlink",
        "streamlink_default_quality": "best",
        
        # Fansly-scraper Settings (full options)
        "fansly_auth_token": "",
        "fansly_user_agent": "",
        "fansly_save_location": "",
        "fansly_vods_file_extension": ".mp4",
        "fansly_generate_contact_sheet": True,
        "fansly_contact_sheet_rows": 5,
        "fansly_contact_sheet_cols": 5,
        "fansly_filename_template": "{date}-{content}",
        "fansly_date_format": "%Y%m%d_%H%M%S",
        "fansly_record_chat": True,
        "fansly_chat_format": "json",
        "fansly_download_videos": True,
        "fansly_download_images": True,
        "fansly_download_messages": True,
        "fansly_convert_live": True,
        "fansly_skip_previews": False,
        "fansly_use_content_as_filename": False,
        
        # Notifications
        "notify_on_live": True,
        "notify_on_recording_start": True,
        "notify_on_recording_stop": True,
        
        # Advanced
        "debug": False,
        "split_files": False,
        "split_duration": 0,
        "max_viewers": 0,
        "per_platform_config": {}
    }
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config: dict = {}
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config = {**self.DEFAULT_CONFIG, **json.load(f)}
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self.save()
    
    def save(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get config value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """Set config value"""
        self._config[key] = value
        self.save()
    
    def update_all(self, data: dict):
        """Update multiple config values"""
        for key, value in data.items():
            if key in self.DEFAULT_CONFIG:
                self._config[key] = value
        self.save()
    
    @property
    def web_port(self) -> int:
        return self._config.get("web_port", 6969)
    
    @property
    def username(self) -> str:
        return self._config.get("username", "admin")
    
    @property
    def password(self) -> str:
        return self._config.get("password", "")
    
    @property
    def downloads_dir(self) -> str:
        return os.path.abspath(self._config.get("downloads_dir", "./recordings"))
    
    @property
    def quality(self) -> str:
        return self._config.get("quality", "best")
    
    @property
    def quality_preference(self) -> str:
        return self._config.get("quality_preference", "prefer_higher")
    
    @property
    def container(self) -> str:
        return self._config.get("container", "ts")
    
    @property
    def auto_record(self) -> bool:
        return self._config.get("auto_record", True)
    
    @property
    def poll_interval(self) -> int:
        return self._config.get("poll_interval", 180)
    
    @property
    def check_on_startup(self) -> bool:
        return self._config.get("check_on_startup", True)
    
    @property
    def ffmpeg_path(self) -> str:
        return self._config.get("ffmpeg_path", "ffmpeg")
    
    @property
    def ffmpeg_recording_options(self) -> str:
        return self._config.get("ffmpeg_recording_options", "")
    
    @property
    def ffmpeg_convert(self) -> bool:
        return self._config.get("ffmpeg_convert", True)
    
    @property
    def ffmpeg_output_options(self) -> str:
        return self._config.get("ffmpeg_output_options", "-c:v libx264 -crf 23")
    
    @property
    def streamlink_path(self) -> str:
        return self._config.get("streamlink_path", "streamlink")
    
    @property
    def streamlink_default_quality(self) -> str:
        return self._config.get("streamlink_default_quality", "best")
    
    @property
    def fansly_auth_token(self) -> str:
        return self._config.get("fansly_auth_token", "")
    
    @property
    def fansly_save_location(self) -> str:
        return self._config.get("fansly_save_location", "")
    
    @property
    def fansly_vods_file_extension(self) -> str:
        return self._config.get("fansly_vods_file_extension", ".ts")
    
    @property
    def fansly_generate_contact_sheet(self) -> bool:
        return self._config.get("fansly_generate_contact_sheet", True)
    
    @property
    def fansly_filename_template(self) -> str:
        return self._config.get("fansly_filename_template", "{model_username}_{date}")
    
    @property
    def fansly_date_format(self) -> str:
        return self._config.get("fansly_date_format", "%Y%m%d_%H%M%S")
    
    @property
    def fansly_record_chat(self) -> bool:
        return self._config.get("fansly_record_chat", True)
    
    @property
    def notify_on_live(self) -> bool:
        return self._config.get("notify_on_live", True)
    
    @property
    def notify_on_recording_start(self) -> bool:
        return self._config.get("notify_on_recording_start", True)
    
    @property
    def notify_on_recording_stop(self) -> bool:
        return self._config.get("notify_on_recording_stop", True)
    
    @property
    def debug(self) -> bool:
        return self._config.get("debug", False)
    
    @property
    def split_files(self) -> bool:
        return self._config.get("split_files", False)
    
    @property
    def split_duration(self) -> int:
        return self._config.get("split_duration", 0)
    
    @property
    def max_viewers(self) -> int:
        return self._config.get("max_viewers", 0)
    
    @property
    def per_platform_config(self) -> dict:
        return self._config.get("per_platform_config", {})


# Global config instance
config = Config()