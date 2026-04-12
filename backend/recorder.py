"""Recorder engine for StreamHub"""
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from backend.platforms import get_platform, PLATFORMS


class Recorder:
    """Recording engine that monitors and records streams"""
    
    def __init__(self, config, streamer_manager):
        self.config = config
        self.streamer_manager = streamer_manager
        self.active_recordings: Dict[str, Dict] = {}
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start the background monitoring loop"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop the background monitoring loop"""
        self.monitoring = False
    
    def _monitor_loop(self):
        """Background loop to check streamer status"""
        while self.monitoring:
            try:
                self._check_all_streamers()
            except Exception as e:
                print(f"Monitor error: {e}")
            time.sleep(self.config.poll_interval)
    
    def _check_all_streamers(self):
        """Check status of all streamers"""
        for streamer in self.streamer_manager.get_all_streamers():
            if not streamer.get('auto_record', True):
                continue
            
            status_info = self.streamer_manager.check_status(streamer['id'])
            if status_info.get('status') == 'live':
                # Auto-start recording if not already recording
                if not self._is_recording(streamer['id']):
                    self.start_recording(streamer['id'])
    
    def _is_recording(self, streamer_id: str) -> bool:
        """Check if streamer is currently being recorded"""
        return streamer_id in self.active_recordings
    
    def start_recording(self, streamer_id: str) -> bool:
        """Start recording a streamer"""
        streamer = self.streamer_manager.get_streamer(streamer_id)
        if not streamer:
            return False
        
        if self._is_recording(streamer_id):
            return True
        
        platform_slug = streamer['platform']
        username = streamer['username']
        
        # Create output filename - default to mp4 for browser compatibility
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        container = self.config.container
        filename = f"{username}_{platform_slug}_{timestamp}.{container}"
        output_path = os.path.join(self.config.downloads_dir, filename)
        
        # Get stream URL based on platform
        stream_url = self._get_stream_url(platform_slug, username)
        if not stream_url:
            return False
        
        # Start recording process
        try:
            if platform_slug.lower() in ['tw', 'kc', 'yt']:
                # Use streamlink for Twitch/Kick/YouTube
                cmd = [
                    self.config.streamlink_path or "streamlink",
                    stream_url,
                    streamer.get('quality', 'best'),
                    "-o", output_path
                ]
            else:
                # Use ffmpeg directly for HLS streams - save as mp4 for browser
                cmd = [
                    self.config.ffmpeg_path or "ffmpeg",
                    "-i", stream_url,
                    "-c", "copy",
                    "-movflags", "+faststart",
                    "-f", "mp4",
                    output_path
                ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Store recording info
            self.active_recordings[streamer_id] = {
                'id': streamer_id,
                'process': process,
                'file_path': output_path,
                'start_time': time.time(),
                'status': 'recording'
            }
            
            return True
        except Exception as e:
            print(f"Failed to start recording: {e}")
            return False
    
    def stop_recording(self, streamer_id: str) -> bool:
        """Stop recording a streamer"""
        if streamer_id not in self.active_recordings:
            return False
        
        recording = self.active_recordings[streamer_id]
        process = recording.get('process')
        file_path = recording.get('file_path', '')
        
        # Get start time for duration tracking
        start_time = recording.get('start_time', time.time())
        
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # Compress after recording if enabled (async in background)
        if file_path and os.path.exists(file_path) and self.config._config.get('compress_recordings', False):
            threading.Thread(target=self._compress_recording, args=(file_path,), daemon=True).start()
        
        # Update recording status
        del self.active_recordings[streamer_id]
        
        return True
    
    def _compress_recording(self, file_path: str) -> bool:
        """Compress a recording file using configured settings"""
        if not os.path.exists(file_path):
            return False
        
        preset = self.config._config.get('compression_preset', 'medium')
        crf = self.config._config.get('compression_crf', 23)
        
        # Output file with _compressed suffix
        base, ext = os.path.splitext(file_path)
        compressed_path = f"{base}_compressed.mp4"
        
        cmd = [
            self.config.ffmpeg_path or 'ffmpeg',
            '-i', file_path,
            '-c:v', 'libx264',
            '-preset', preset,
            '-crf', str(crf),
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y', compressed_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=3600)  # 1 hour max
            if result.returncode == 0 and os.path.exists(compressed_path):
                # Replace original with compressed
                os.replace(compressed_path, file_path)
                return True
            elif os.path.exists(compressed_path):
                os.remove(compressed_path)
        except Exception as e:
            print(f"Compression error: {e}")
        
        return False
    
    def _get_stream_url(self, platform_slug: str, username: str) -> Optional[str]:
        """Get stream URL for a platform"""
        # For now, construct the URL based on platform
        # In production, this would query the platform API
        urls = {
            'SC': f"https://stripchat.com/{username}",
            'CB': f"https://chaturbate.com/{username}",
            'CS': f"https://camsoda.com/{username}",
            'F4F': f"https://www.flirt4free.com/{username}",
            'MFC': f"https://myfreecams.com/{username}",
            'C4': f"https://cam4.com/{username}",
            'BC': f"https://bongacams.com/{username}",
            'FL': f"https://fansly.com/live/{username}",
            'TW': f"https://www.twitch.tv/{username}",
            'KC': f"https://kick.com/{username}",
            'YT': f"https://www.youtube.com/@{username}"
        }
        
        return urls.get(platform_slug.upper())
    
    def get_active_recordings(self) -> Dict:
        """Get all active recordings"""
        return self.active_recordings.copy()
    
    def get_recording_status(self, streamer_id: str) -> Optional[Dict]:
        """Get recording status for a streamer"""
        return self.active_recordings.get(streamer_id)