"""StreamHub"""
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))
os.chdir(PROJECT_DIR)

from flask import Flask, render_template, jsonify, request, session, redirect
from flask_cors import CORS
from backend.config import Config
from backend.streamer_manager import StreamerManager
from backend.recorder import Recorder
from backend.platforms import PLATFORMS

app = Flask(__name__,
    template_folder=str(PROJECT_DIR / 'web' / 'templates'),
    static_folder=str(PROJECT_DIR / 'web' / 'static'),
    static_url_path='/static')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
CORS(app, resources={r"/recordings/*": {"origins": "*"}})

config = Config()
streamer_manager = StreamerManager(config)
recorder = Recorder(config, streamer_manager)

# In-memory log storage
app_logs = []
session_auth = {'authenticated': False, 'time': None}

@app.route('/')
def index():
    # Check password protection
    if config._config.get('password') and not session_auth.get('authenticated'):
        return redirect('/login')
    s = streamer_manager.get_all_streamers()
    r = streamer_manager.get_recordings()
    
    # Count live OR recording as "live" - status can be either during active session
    active_ids = set(recorder.get_active_recordings().keys())
    lc = sum(1 for x in s if x.get('status') == 'live' or x['id'] in active_ids)
    active_recs = len(recorder.get_active_recordings())
    return render_template('dashboard.html', streamers_count=len(s), live_count=lc, recording_count=active_recs, recordings=r[:10])

@app.route('/login')
def login_page():
    # Only show login if password is set
    if not config._config.get('password'):
        return redirect('/')
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login_api():
    pwd = request.json.get('password', '')
    if pwd == config._config.get('password'):
        session_auth['authenticated'] = True
        session_auth['time'] = datetime.now().isoformat()
        return jsonify({'success': True})
    return jsonify({'success': False}), 401

@app.route('/logout')
def logout():
    session_auth['authenticated'] = False
    return redirect('/')

@app.route('/streamers')
def sp():
    if config._config.get('password') and not session_auth.get('authenticated'):
        return redirect('/login')
    active = recorder.get_active_recordings()
    active_ids = set(active.keys())
    streamers = streamer_manager.get_all_streamers()
    for s in streamers:
        if s['id'] in active_ids:
            s['status'] = 'recording'
    
    # Sort: live > recording > offline
    def sort_key(s):
        status = s.get('status', 'offline')
        if status == 'recording': return 0
        if status == 'live': return 1
        return 2
    
    streamers.sort(key=sort_key)
    return render_template('streamers.html', streamers=streamers, platforms=PLATFORMS, active_recordings=active_ids)

@app.route('/recordings')
def rp():
    if config._config.get('password') and not session_auth.get('authenticated'):
        return redirect('/login')
    return render_template('recordings.html', recordings=streamer_manager.get_recordings())

@app.route('/settings')
def sp2():
    if config._config.get('password') and not session_auth.get('authenticated'):
        return redirect('/login')
    return render_template('settings.html', config=config._config)

@app.route('/api/streamers', methods=['GET', 'POST'])
def sr_api():
    if request.method == 'POST':
        d = request.json
        username = d.get('username')
        platform = d.get('platform')
        result = streamer_manager.add_streamer(username, platform)
        log_event(f"+ {username} ({platform})", 'info')
        return jsonify(result)
    return jsonify(streamer_manager.get_all_streamers())

def log_event(message, event_type=''):
    """Add event to log"""
    app_logs.append({
        'time': datetime.now().strftime('%H:%M:%S'),
        'message': message,
        'type': event_type
    })
    # Keep only last 50
    if len(app_logs) > 50:
        app_logs[:] = app_logs[-50:]

@app.route('/api/streamers/<id>', methods=['DELETE', 'PUT'])
def s_del(id):
    if request.method == 'PUT':
        data = request.json
        streamer_manager.update_streamer(id, data)
        return jsonify({'success': True})
    s = streamer_manager.get_streamer(id)
    result = streamer_manager.remove_streamer(id)
    if result and s:
        log_event(f"- {s.get('username', id)}", 'info')
    return jsonify({'success': result})

@app.route('/api/streamers/<id>/status', methods=['GET', 'POST'])
def check_st(id):
    """Check live status of a streamer"""
    status_info = streamer_manager.check_status(id)
    return jsonify(status_info)

@app.route('/api/streamers/<id>/start', methods=['POST'])
def start_rec(id):
    """Start recording a streamer"""
    success = recorder.start_recording(id)
    if success:
        streamer = streamer_manager.get_streamer(id)
        if streamer:
            app_logs.append({'time': datetime.now().strftime('%H:%M:%S'), 'message': f"Started: {streamer.get('username', id)}", 'type': 'recording'})
    return jsonify({'success': success})

@app.route('/api/streamers/<id>/stop', methods=['POST'])
def stop_rec(id):
    """Stop recording a streamer"""
    success = recorder.stop_recording(id)
    return jsonify({'success': success})

@app.route('/api/check-all', methods=['POST'])
def check_all():
    """Force check all streamers and auto-record"""
    results = []
    for s in streamer_manager.get_all_streamers():
        old_status = s.get('status', 'offline')
        status = streamer_manager.check_status(s['id'])
        new_status = status.get('status', 'offline')
        results.append(status)
        
        # Log status changes
        if new_status != old_status:
            if new_status == 'live':
                log_event(f"● ONLINE: {s.get('username')}", 'live')
            elif new_status == 'offline' and old_status == 'live':
                log_event(f"○ OFFLINE: {s.get('username')}", 'info')
            elif new_status == 'offline':
                log_event(f"○ OFFLINE: {s.get('username')}", 'info')
        
        # Auto-record
        if s.get('auto_record', True) and new_status == 'live' and not recorder._is_recording(s['id']):
            streamer_manager.update_streamer(s['id'], {'status': 'live'})
            recorder.start_recording(s['id'])
            log_event(f"◉ REC: {s.get('username')}", 'recording')
    
    return jsonify({'results': results})

@app.route('/api/recordings', methods=['GET'])
def rec_api(): return jsonify(streamer_manager.get_recordings())

@app.route('/api/recordings/<id>', methods=['DELETE'])
def delete_recording(id):
    """Delete a recording"""
    for rec in streamer_manager.get_recordings():
        if rec.get('id') == id:
            filepath = rec.get('file_path', '')
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
            streamer_manager.delete_recording(id)
            return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/api/recordings/cleanup', methods=['POST'])
def cleanup_recordings():
    """Remove recordings that no longer exist on disk"""
    cleaned = 0
    for rec in streamer_manager.get_recordings()[:]:
        filepath = rec.get('file_path', '')
        if filepath and not os.path.exists(filepath):
            streamer_manager.delete_recording(rec.get('id'))
            cleaned += 1
    return jsonify({'cleaned': cleaned})

@app.route('/api/status', methods=['GET'])
def st_api(): return jsonify({'streamers_count': len(streamer_manager.get_all_streamers()), 'platforms': list(PLATFORMS.keys())})

@app.route('/api/config', methods=['GET', 'POST'])
def cfg_api():
    if request.method == 'POST': config.update_all(request.json)
    return jsonify({k: v for k, v in config._config.items() if k != 'password'})

# Serve recordings - proper MIME types with range support for scrubbing
from flask import send_from_directory, make_response
import os

@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    as_attachment = request.args.get('download', '0') == '1'
    
    # Determine MIME type
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mt_map = {'mp4': 'video/mp4', 'mkv': 'video/x-matroska', 'webm': 'video/webm', 'ts': 'video/mp2t'}
    mt = mt_map.get(ext, 'application/octet-stream')
    
    file_path = os.path.join(config.downloads_dir, filename)
    
    # Use send_file for proper streaming
    from flask import send_file
    resp = send_file(
        file_path,
        mimetype=mt,
        as_attachment=as_attachment,
        conditional=True,
        etag=True
    )
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/api/logs', methods=['GET'])
def logs_api():
    # Return recent logs
    return jsonify({'logs': app_logs[-20:]})

@app.route('/api/recording-stats', methods=['GET'])
def recording_stats_api():
    # Return live stats for all active recordings
    stats = {}
    import time
    import os
    now = time.time()
    active = recorder.get_active_recordings()
    for sid, rec in active.items():
        # Calculate duration
        start = rec.get('start_time', now)
        if isinstance(start, str):
            try:
                start = datetime.fromisoformat(start).timestamp()
            except:
                start = now
        duration = int(now - start)
        hours = duration // 3600
        mins = (duration % 3600) // 60
        secs = duration % 60
        
        # Get real file size
        filepath = rec.get('file_path', '')
        size_mb = 0
        bitrate = 0
        if filepath and os.path.exists(filepath):
            size_bytes = os.path.getsize(filepath)
            size_mb = size_bytes / 1024 / 1024
            # Estimate bitrate from size and duration
            if duration > 0:
                bitrate = int((size_bytes * 8) / duration / 1000)  # kbps
        
        stats[sid] = {
            'duration': f'{hours:02d}:{mins:02d}:{secs:02d}',
            'size': f'{size_mb:.1f} MB',
            'bitrate': f'{bitrate} kbps' if bitrate > 0 else '---'
        }
    return jsonify(stats)

@app.route('/thumbnails/<recording_id>_<int:thumb_num>')
@app.route('/thumbnails/<recording_id>')
def get_thumbnail(recording_id, thumb_num=1):
    """Generate and serve thumbnails for recording at different timestamps"""
    import subprocess
    
    # Parse recording_id (might include _1, _2 etc)
    parts = recording_id.rsplit('_', 1)
    base_id = parts[0]
    if len(parts) > 1 and parts[1].isdigit():
        thumb_num = int(parts[1])
    
    # Find recording
    rec = None
    for r in streamer_manager.get_recordings():
        if r.get('id') == base_id:
            rec = r
            break
    
    if not rec:
        return "Not found", 404
    
    filepath = rec.get('file_path', '')
    if not filepath or not os.path.exists(filepath):
        return "File not found", 404
    
    # Quick thumbnail - just grab frame at 10 seconds, no probing
    timestamp = 10
    
    thumb_dir = os.path.join(config.downloads_dir, '.thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f'{base_id}_{thumb_num}.jpg')
    
    # Generate thumbnail with OpenCV (instant)
    if not os.path.exists(thumb_path):
        try:
            import cv2
            cap = cv2.VideoCapture(filepath)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_LINEAR)
                    cv2.imwrite(thumb_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        except ImportError:
            # Fallback to FFmpeg
            try:
                cmd = [
                    config.ffmpeg_path or 'ffmpeg',
                    '-threads', '1',
                    '-i', filepath,
                    '-ss', str(timestamp),
                    '-vframes', '1',
                    '-s', '320x180',
                    '-q:v', '2',
                    '-preset', 'ultrafast',
                    '-y', thumb_path
                ]
                subprocess.run(cmd, capture_output=True, timeout=60)
            except:
                pass
        except Exception as e:
            print(f"Thumbnail error: {e}")
    
    if os.path.exists(thumb_path):
        return send_from_directory(thumb_dir, f'{base_id}_{thumb_num}.jpg')
    
    return "No thumbnail", 404

@app.route('/api/regenerate-thumbnails', methods=['POST'])
def regenerate_thumbnails():
    """Regenerate thumbnails for all recordings"""
    thumb_dir = os.path.join(config.downloads_dir, '.thumbnails')
    os.makedirs(thumb_dir, exist_ok=True)
    
    count = 0
    for rec in streamer_manager.get_recordings():
        filepath = rec.get('file_path', '')
        rec_id = rec.get('id', '')
        if not filepath or not os.path.exists(filepath):
            continue
        
        thumb_path = os.path.join(thumb_dir, f'{rec_id}.jpg')
        if not os.path.exists(thumb_path):
            try:
                import cv2
                cap = cv2.VideoCapture(filepath)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_MSEC, 10000)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        frame = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_LINEAR)
                        cv2.imwrite(thumb_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        count += 1
            except ImportError:
                # Fallback to FFmpeg
                try:
                    import subprocess
                    cmd = [
                        config.ffmpeg_path or 'ffmpeg',
                        '-i', filepath,
                        '-ss', '00:00:10',
                        '-vframes', '1',
                        '-s', '320x180',
                        '-y', thumb_path
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=60)
                    count += 1
                except:
                    pass
    
    return jsonify({'generated': count})

@app.route('/api/fix-recordings', methods=['POST'])
def fix_recordings():
    """Fix MP4 metadata for all recordings"""
    import subprocess
    fixed = 0
    for rec in streamer_manager.get_recordings():
        filepath = rec.get('file_path', '')
        if not filepath or not os.path.exists(filepath):
            continue
        
        # Skip non-mp4
        if not filepath.endswith('.mp4'):
            continue
        
        # Check if already has faststart by probing
        temp_output = filepath + '.fixed.mp4'
        try:
            cmd = [
                config.ffmpeg_path or 'ffmpeg',
                '-i', filepath,
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', temp_output
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and os.path.exists(temp_output):
                os.replace(temp_output, filepath)
                fixed += 1
            elif os.path.exists(temp_output):
                os.remove(temp_output)
        except Exception as e:
            if os.path.exists(temp_output):
                os.remove(temp_output)
            print(f"Fix error: {e}")
    
    return jsonify({'fixed': fixed})

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear thumbnail cache"""
    thumb_dir = os.path.join(config.downloads_dir, '.thumbnails')
    deleted = 0
    if os.path.exists(thumb_dir):
        for f in os.listdir(thumb_dir):
            try:
                os.remove(os.path.join(thumb_dir, f))
                deleted += 1
            except:
                pass
    return jsonify({'deleted': deleted})

import signal
import atexit

def shutdown_handler(signum=None, frame=None):
    """Handle Ctrl+C gracefully - finish recordings before exit"""
    print("\n[Shutdown] Finishing active recordings...")
    recorder.stop_monitoring()
    
    # Stop all active recordings (this triggers compression if enabled)
    active = recorder.get_active_recordings()
    for streamer_id in list(active.keys()):
        recorder.stop_recording(streamer_id)
    
    print("[Shutdown] Done. Exiting.")
    sys.exit(0)

# Register shutdown handlers
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)
atexit.register(shutdown_handler)

if __name__ == '__main__':
    os.makedirs(config.downloads_dir, exist_ok=True)
    recorder.start_monitoring()
    print('StreamHub: http://localhost:{}'.format(config.web_port))
    app.run(host='0.0.0.0', port=config.web_port, debug=False)