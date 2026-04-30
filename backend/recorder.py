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
            is_live = status_info.get('status') == 'live'
            
            if is_live:
                # Auto-start recording if not already recording
                if not self._is_recording(streamer['id']):
                    self.start_recording(streamer['id'])
            else:
                # Stop recording if streamer went offline
                if self._is_recording(streamer['id']):
                    self.stop_recording(streamer['id'])
    
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
            # Use streamlink for platforms it supports
            streamlink_platforms = ['TW', 'KC', 'YT', 'CB', 'CS', 'BC', 'SC', 'F4F', 'MFC', 'C4']
            
            if platform_slug.upper() in streamlink_platforms:
                # Use streamlink for these platforms (handles stream extraction)
                cmd = [
                    self.config.streamlink_path or "streamlink",
                    stream_url,
                    streamer.get('quality', 'best'),
                    "-o", output_path
                ]
            else:
                # Use FFmpeg directly for other HLS streams
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
    
    def _detect_hardware_acceleration(self) -> tuple:
        """Detect available hardware acceleration (NVENC, QSV, VCE)"""
        ffmpeg = self.config.ffmpeg_path or 'ffmpeg'
        
        # Check for NVIDIA GPU
        try:
            result = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, timeout=10)
            if 'h264_nvenc' in result.stderr:
                return ('nvenc', 'h264_nvenc', 'hevc_nvenc')
        except:
            pass
        
        # Check for AMD VCE
        try:
            result = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, timeout=10)
            if 'h264_amf' in result.stderr:
                return ('amf', 'h264_amf', 'hevc_amf')
        except:
            pass
        
        # Check for Intel QuickSync
        try:
            result = subprocess.run([ffmpeg, '-hide_banner', '-encoders'], capture_output=True, timeout=10)
            if 'h264_qsv' in result.stderr:
                return ('qsv', 'h264_qsv', 'hevc_qsv')
        except:
            pass
        
        return (None, None, None)


    def _compress_recording(self, file_path: str) -> bool:
        """Compress a recording file using configured settings - handles large files up to 20GB+"""
        if not os.path.exists(file_path):
            print(f"[Compression] File not found: {file_path}")
            return False
        
        preset = self.config._config.get('compression_preset', 'medium')
        crf = self.config._config.get('compression_crf', 23)
        
        # Get file size for timeout calculation
        file_size = os.path.getsize(file_path)
        file_size_gb = file_size / (1024**3)
        
        print(f"[Compression] File size: {file_size_gb:.2f} GB")
        
        # Calculate timeout based on file size (rough estimate: ~1GB per 5 minutes with ultrafast)
        # Use longer timeout for larger files
        base_timeout = 3600  # 1 hour base
        size_based_timeout = int(file_size_gb * 300)  # 5 minutes per GB
        timeout = max(base_timeout, size_based_timeout)
        # Cap at 8 hours for very large files
        timeout = min(timeout, 28800)
        print(f"[Compression] Timeout set to {timeout} seconds ({timeout/3600:.1f} hours)")
        
        base, ext = os.path.splitext(file_path)
        
        # Handle .ts files - need to convert to MP4 first
        intermediate_path = None
        input_file = file_path
        
        if ext.lower() == '.ts':
            print(f"[Compression] Converting .ts to MP4: {file_path}")
            intermediate_path = base + '_intermediate.mp4'
            convert_cmd = [
                self.config.ffmpeg_path or 'ffmpeg',
                '-threads', '4',
                '-i', file_path,
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', intermediate_path
            ]
            try:
                result = subprocess.run(convert_cmd, capture_output=True, timeout=timeout)
                if result.returncode == 0 and os.path.exists(intermediate_path):
                    input_file = intermediate_path
                else:
                    print(f"[Compression] .ts conversion failed")
                    return False
            except Exception as e:
                print(f"[Compression] .ts conversion error: {e}")
                return False
        
        # Detect hardware acceleration
        hw_accel, hw_encoder, hw_hevc = self._detect_hardware_acceleration()
        
        # Compress the (converted) recording
        compressed_path = base + '_compressed.mp4'
        
        # Build command with hardware acceleration if available
        if hw_accel:
            print(f"[Compression] Using hardware acceleration: {hw_accel} ({hw_encoder})")
            cmd = [
                self.config.ffmpeg_path or 'ffmpeg',
                '-hwaccel', 'auto',  # Auto-detect hardware decoding
                '-threads', '4',  # Limit threads to prevent memory issues
                '-i', input_file,
                '-c:v', hw_encoder,
                '-preset', 'fast' if hw_accel != 'qsv' else 'medium',  # HW encoders have different presets
                '-rc', 'cbr',  # Constant bitrate for consistent output
                '-cq', str(crf),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y', compressed_path
            ]
        else:
            # Software encoding - use ultrafast for large files to speed up
            # Use 'ultrafast' for very large files, otherwise use configured preset
            effective_preset = 'ultrafast' if file_size_gb > 5 else preset
            
            cmd = [
                self.config.ffmpeg_path or 'ffmpeg',
                '-threads', '4',  # Limit threads to prevent memory issues
                '-i', input_file,
                '-c:v', 'libx264',
                '-preset', effective_preset,
                '-crf', str(crf),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-profile:v', 'main',  # Compatible profile
                '-level', '4.1',  # Compatible level
                '-y', compressed_path
            ]
            print(f"[Compression] Using software encoding with preset: {effective_preset}")
        
        print(f"[Compression] Starting: {file_path}")
        print(f"[Compression] CRF: {crf}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=timeout)
            
            # Verify compressed file exists and is valid
            if result.returncode == 0 and os.path.exists(compressed_path):
                # Verify the file is playable by checking file size
                compressed_size = os.path.getsize(compressed_path)
                
                if compressed_size < 1000:
                    print(f"[Compression] Compressed file too small, possibly corrupted")
                    os.remove(compressed_path)
                    return False
                
                # Verify compression actually worked - should be smaller
                if compressed_size >= file_size:
                    print(f"[Compression] Warning: compressed file not smaller ({compressed_size} >= {file_size})")
                    # Still accept it but log the warning
                
                print(f"[Compression] Success: {file_size_gb:.2f}GB -> {compressed_size/(1024**3):.2f}GB ({compressed_size*100/file_size:.1f}%)")
                
                # Replace original with compressed
                os.replace(compressed_path, file_path)
                
                # Clean up intermediate file if exists
                if intermediate_path and os.path.exists(intermediate_path):
                    os.remove(intermediate_path)
                
                return True
            else:
                print(f"[Compression] FFmpeg failed with code {result.returncode}")
                if result.stderr:
                    # Log last 1000 chars of error
                    error_msg = result.stderr.decode('utf8', errors='ignore')
                    print(f"[Compression] Error: {error_msg[-1000:]}")
        except subprocess.TimeoutExpired:
            print(f"[Compression] Timeout after {timeout} seconds - file may be too large for timely compression")
            print(f"[Compression] Consider disabling compression for very long recordings or increasing timeout")
        except Exception as e:
            print(f"[Compression] Error: {e}")
        
        # Cleanup on failure
        if 'compressed_path' in locals() and compressed_path and os.path.exists(compressed_path):
            try:
                os.remove(compressed_path)
            except:
                pass
        if intermediate_path and os.path.exists(intermediate_path):
            try:
                os.remove(intermediate_path)
            except:
                pass
        
        return False
    
    def _get_stream_url(self, platform_slug: str, username: str) -> Optional[str]:
        """Get stream URL for a platform"""
        # Use streamlink for platforms it supports (more reliable)
        streamlink_platforms = ['CB', 'CS', 'BC', 'SC', 'F4F', 'MFC', 'C4']
        
        if platform_slug.upper() in streamlink_platforms:
            return f"https://{platform_slug.lower()}.com/{username}"
        
        # Use platform classes for other platforms (HLS URLs)
        from backend.platforms import get_platform
        platform_cls = get_platform(platform_slug)
        if platform_cls:
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                url = loop.run_until_complete(
                    platform_cls().get_stream_url(username, "best")
                )
                loop.close()
                if url:
                    return url
            except Exception as e:
                print(f"Platform URL error: {e}")
        
        # Fall back to website URLs for streamlink
        urls = {
            'TW': f"https://www.twitch.tv/{username}",
            'KC': f"https://kick.com/{username}",
            'YT': f"https://www.youtube.com/@{username}",
            'FL': f"https://fansly.com/live/{username}"
        }
        
        return urls.get(platform_slug.upper())
    
    def get_active_recordings(self) -> Dict:
        """Get all active recordings"""
        return self.active_recordings.copy()
    
    def get_recording_status(self, streamer_id: str) -> Optional[Dict]:
        """Get recording status for a streamer"""
        return self.active_recordings.get(streamer_id)