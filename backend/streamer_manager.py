"""Streamer management for StreamHub"""
import os
import json
import uuid
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from backend.platforms import get_platform


class StreamerManager:
    """Manages streamers and their configurations"""
    
    def __init__(self, config):
        self.config = config
        self.streamers: Dict[str, Dict] = {}
        self.recordings: Dict[str, Dict] = {}
        self._load_streamers()
        self._scan_recordings()
    
    def _load_streamers(self):
        """Load streamers from config"""
        streamers_file = Path("streamers.json")
        if streamers_file.exists():
            with open(streamers_file, 'r') as f:
                data = json.load(f)
                self.streamers = data.get('streamers', {})
    
    def _save_streamers(self):
        """Save streamers to config"""
        with open("streamers.json", 'w') as f:
            json.dump({'streamers': self.streamers}, f, indent=2)
    
    def _scan_recordings(self):
        """Scan recordings directory for existing files"""
        downloads_dir = Path(self.config.downloads_dir)
        if not downloads_dir.exists():
            downloads_dir.mkdir(parents=True, exist_ok=True)
        
        self.recordings = {}
        for file_path in downloads_dir.glob("*.ts"):
            self._add_recording_file(file_path)
        for file_path in downloads_dir.glob("*.mp4"):
            self._add_recording_file(file_path)
    
    def _add_recording_file(self, file_path: Path):
        """Add recording file from disk - use filename-based ID for consistency"""
        # Use first 8 chars of filename (without extension) as ID for consistency
        # Falls back to UUID only if filename is too short
        name_no_ext = file_path.stem
        if len(name_no_ext) >= 8:
            recording_id = name_no_ext[:8]
        else:
            recording_id = str(uuid.uuid4())[:8]
        
        # Handle duplicates by appending suffix
        base_id = recording_id
        suffix = 1
        while recording_id in self.recordings:
            recording_id = base_id + str(suffix)
            suffix += 1
        
        stat = file_path.stat()
        
        # Parse filename: username_platform_timestamp.mp4
        name_parts = file_path.stem.split('_')
        username = name_parts[0] if name_parts else 'Unknown'
        platform = name_parts[1] if len(name_parts) > 1 else ''
        
        # Calculate duration and bitrate
        duration = 0
        bitrate = ''
        try:
            import subprocess
            cmd = [self.config.ffmpeg_path or 'ffmpeg', '-i', str(file_path)]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = proc.communicate(timeout=10)
            output = stderr.decode('utf8', errors='ignore')
            import re
            # Parse duration
            m = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', output)
            if m:
                dur_sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                duration = int(dur_sec)
            # Estimate bitrate
            if duration > 0:
                kbps = int(stat.st_size * 8 / duration / 1000)
                bitrate = f'{kbps} kbps'
        except:
            pass
        
        # Format duration as HH:MM:SS
        if duration:
            dur_str = f'{duration//3600:02d}:{(duration%3600)//60:02d}:{duration%60:02d}'
        else:
            dur_str = '--:--:--'
        
        self.recordings[recording_id] = {
            'id': recording_id,
            'file_path': str(file_path),
            'filename': file_path.name,
            'username': username,
            'platform': platform,
            'file_size': stat.st_size,
            'duration': dur_str,
            'bitrate': bitrate,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'status': 'completed'
        }
    
    def get_all_streamers(self) -> List[Dict]:
        """Get all streamers"""
        return list(self.streamers.values())
    
    def get_streamer(self, streamer_id: str) -> Optional[Dict]:
        """Get a specific streamer"""
        return self.streamers.get(streamer_id)
    
    def add_streamer(self, username: str, platform: str) -> Optional[Dict]:
        """Add a new streamer"""
        platform_cls = get_platform(platform)
        if not platform_cls:
            return None
        
        # Create unique ID
        streamer_id = f"{platform}_{username}"
        
        streamer = {
            'id': streamer_id,
            'username': username,
            'platform': platform,
            'status': 'offline',
            'auto_record': True,
            'quality': self.config.quality,
            'created': datetime.now().isoformat()
        }
        
        self.streamers[streamer_id] = streamer
        self._save_streamers()
        return streamer
    
    def remove_streamer(self, streamer_id: str) -> bool:
        """Remove a streamer"""
        if streamer_id in self.streamers:
            del self.streamers[streamer_id]
            self._save_streamers()
            return True
        return False
    
    def update_streamer(self, streamer_id: str, data: Dict) -> bool:
        """Update streamer configuration"""
        if streamer_id in self.streamers:
            self.streamers[streamer_id].update(data)
            self._save_streamers()
            return True
        return False
    
    def check_status(self, streamer_id: str) -> Dict:
        """Check status of a streamer using platform APIs"""
        streamer = self.get_streamer(streamer_id)
        if not streamer:
            return {'error': 'Streamer not found'}
        
        username = streamer['username']
        platform = streamer['platform']
        
        # Use streamlink for Twitch/Kick/YouTube
        if platform.upper() in ['TW', 'KC', 'YT']:
            status = self._check_streamlink(username, platform)
            streamer['status'] = status
            self._save_streamers()
            return {'id': streamer_id, 'username': username, 'platform': platform, 'status': status}
        
# Check via API for other platforms
        status = self._check_api(username, platform)
        streamer['status'] = status
        self._save_streamers()
        return {'id': streamer_id, 'username': username, 'platform': platform, 'status': status}
    
    def _check_streamlink(self, username: str, platform: str) -> str:
        """Check status via streamlink"""
        import subprocess
        urls = {'TW': f'https://www.twitch.tv/{username}', 'KC': f'https://kick.com/{username}', 'YT': f'https://www.youtube.com/@{username}'}
        url = urls.get(platform.upper(), '')
        if not url:
            return 'offline'
        try:
            result = subprocess.run(['streamlink', url, 'best', '--json'], capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                return 'live'
        except:
            pass
        return 'offline'
    
    def _check_api(self, username: str, platform: str) -> str:
        """Check status via API (StreaMonitor-style)"""
        import requests
        platform = platform.upper()
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.google.com/'}
        
        # StripChat
        if platform == 'SC':
            try:
                r = requests.get(f'https://stripchat.com/api/front/v2/models/username/{username}/cam', timeout=10)
                if r.status_code == 200 and r.json().get('isLive'):
                    return 'live'
            except:
                pass
        
        # Chaturbate - page scraping (streamlink doesn't support CB natively)
        # Note: Cloudflare protection may block requests - we'll try multiple methods
        elif platform == 'CB':
            # Try with cloudflare bypass headers
            cb_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            try:
                # First try the room API endpoint
                r = requests.get(
                    f'https://chaturbate.com/{username}/',
                    timeout=15,
                    headers=cb_headers,
                    allow_redirects=True
                )
                
                # Check if we got blocked by Cloudflare
                if 'cloudflare' in r.text.lower()[:500] or 'just a moment' in r.text.lower()[:100]:
                    print(f"[Status] Chaturbate Cloudflare blocked for {username}, trying alternate method")
                    
                    # Try alternate URL pattern
                    try:
                        alt_url = f'https://www.chaturbate.com/{username}/'
                        r2 = requests.get(alt_url, timeout=15, headers=cb_headers)
                        if r2.status_code == 200 and len(r2.text) > 10000:
                            r = r2
                    except:
                        pass
                
                if r.status_code == 200:
                    text = r.text[:3000]  # Check first 3000 chars
                    text_lower = text.lower()
                    
                    # Check for Cloudflare block
                    if 'just a moment' in text_lower[:200]:
                        return 'unknown'  # Can't determine due to Cloudflare
                    
                    # If these strings appear, the room is offline
                    if 'room_status="offline"' in text_lower:
                        return 'offline'
                    if '"is_online": false' in text:
                        return 'offline'
                    if '<title>Offline - ' in text or 'offline - chaturbate' in text_lower:
                        return 'offline'
                    
                    # Check for online indicators  
                    if '"is_online": true' in text:
                        return 'live'
                    if 'room_status="online"' in text_lower:
                        return 'live'
                    
                    # If page loaded fully and no offline indicator, likely online
                    if len(r.text) > 30000:
                        # Additional check: login form means offline
                        if 'type="password"' in text_lower and 'placeholder="Room Password"' in text_lower:
                            return 'offline'
                        return 'live'
                        
            except Exception as e:
                print(f"[Status] Chaturbate error for {username}: {e}")
                return 'unknown'
        
        # CamSoda
        elif platform == 'CS':
            try:
                r = requests.get(f'https://camsoda.com/api/v1/{username}/is-online', timeout=10)
                if r.status_code == 200 and r.json().get('is_online'):
                    return 'live'
            except:
                pass
        
        # Flirt4Free
        elif platform == 'F4F':
            try:
                r = requests.get(f'https://www.flirt4free.com/ajax/roomstatus.php?username={username}', timeout=10)
                if r.status_code == 200 and r.json().get('status') == 'online':
                    return 'live'
            except:
                pass
        
        # MyFreeCams
        elif platform == 'MFC':
            try:
                r = requests.get(f'https://models.myfreecams.com/api2/jsonfcgi.php?method=user.getDetails&name[0]={username}', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    user = data.get('user', {})
                    if user.get('current_show') or user.get('status') == 'public':
                        return 'live'
            except:
                pass
        
        # Cam4
        elif platform == 'C4':
            try:
                r = requests.get(f'https://www.cam4.com/_ui/api/v1/model/{username}/status', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('online'):
                        return 'live'
            except:
                pass
        
        # Bongacams
        elif platform == 'BC':
            try:
                r = requests.get(f'https://bongacams.com/api/v1/models/{username}', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('isOnline'):
                        return 'live'
            except:
                pass
        
        # Fansly
        elif platform == 'FL':
            try:
                r = requests.get(f'https://api.fansly.com/account/{username}', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get('isLiveStream'):
                        return 'live'
            except:
                pass
        
        return 'offline'
    
    def get_recordings(self) -> List[Dict]:
        """Get all recordings"""
        return list(self.recordings.values())
    
    def get_recording_info(self, recording_id: str) -> Optional[Dict]:
        """Get recording info"""
        return self.recordings.get(recording_id)
    
    def delete_recording(self, recording_id: str) -> bool:
        """Delete a recording"""
        recording = self.recordings.get(recording_id)
        if recording:
            try:
                os.remove(recording['file_path'])
                del self.recordings[recording_id]
                return True
            except Exception:
                pass
        return False