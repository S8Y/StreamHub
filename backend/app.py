"""StreamHub Flask Application - All original project features"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS

# Import backend modules
from backend.config import Config
from backend.streamer_manager import StreamerManager
from backend.recorder import Recorder
from backend.platforms import get_all_platforms, PLATFORMS


# Initialize Flask
BASE_DIR = Path(__file__).parent.parent
app = Flask(__name__, 
    template_folder=str(BASE_DIR / 'web' / 'templates'),
    static_folder=str(BASE_DIR / 'web' / 'static'),
    static_url_path='/static')
CORS(app)

# Initialize config (loads from config.json with default port 6969)
config = Config()

# Override port from config if specified
WEB_PORT = config.web_port

# Initialize managers
streamer_manager = StreamerManager(config)
recorder = Recorder(config, streamer_manager)


@app.route('/')
def index():
    """Dashboard page"""
    try:
        streamers = streamer_manager.get_all_streamers()
        recordings = streamer_manager.get_recordings()
        live_count = sum(1 for s in streamers if s.get('status') == 'live')
        recording_count = len(recordings)  # Total recordings count
        
        return render_template(
            'dashboard.html',
            streamers_count=len(streamers),
            live_count=live_count,
            recording_count=recording_count,
            recordings=recordings[:10]
        )
    except Exception as e:
        import traceback
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500


@app.route('/streamers')
def streamers_page():
    """Streamers management page"""
    streamers = streamer_manager.get_all_streamers()
    platforms = get_all_platforms()
    return render_template(
        'streamers.html',
        streamers=streamers,
        platforms=platforms
    )


@app.route('/recordings')
def recordings_page():
    """Recordings page"""
    recordings = streamer_manager.get_recordings()
    return render_template(
        'recordings.html',
        recordings=recordings
    )


@app.route('/settings')
def settings_page():
    """Settings page"""
    return render_template(
        'settings.html',
        config=config._config
    )


# API Routes

@app.route('/api/streamers', methods=['GET'])
def get_streamers():
    """Get all streamers"""
    return jsonify(streamer_manager.get_all_streamers())


@app.route('/api/streamers', methods=['POST'])
def add_streamer():
    """Add a new streamer"""
    data = request.json
    username = data.get('username')
    platform = data.get('platform')
    
    if not username or not platform:
        return jsonify({'error': 'Username and platform required'}), 400
    
    streamer = streamer_manager.add_streamer(username, platform)
    if streamer:
        return jsonify(streamer), 201
    return jsonify({'error': 'Failed to add streamer'}), 400


@app.route('/api/streamers/<streamer_id>', methods=['DELETE'])
def remove_streamer(streamer_id):
    """Remove a streamer"""
    if streamer_manager.remove_streamer(streamer_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Streamer not found'}), 404


@app.route('/api/streamers/<streamer_id>/start', methods=['POST'])
def start_recording(streamer_id):
    """Start recording a streamer"""
    success = recorder.start_recording(streamer_id)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to start recording'}), 400


@app.route('/api/streamers/<streamer_id>/stop', methods=['POST'])
def stop_recording(streamer_id):
    """Stop recording a streamer"""
    success = recorder.stop_recording(streamer_id)
    if success:
        return jsonify({'success': True})
    return jsonify({'error': 'Failed to stop recording'}), 400


@app.route('/api/streamers/<streamer_id>/status', methods=['GET'])
def get_streamer_status(streamer_id):
    """Get status for a specific streamer"""
    status = streamer_manager.check_status(streamer_id)
    return jsonify(status)


@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """Get all recordings"""
    return jsonify(streamer_manager.get_recordings())


@app.route('/api/recordings/<recording_id>', methods=['DELETE'])
def delete_recording(recording_id):
    """Delete a recording"""
    if streamer_manager.delete_recording(recording_id):
        return jsonify({'success': True})
    return jsonify({'error': 'Recording not found'}), 404


@app.route('/api/recordings/<recording_id>/download', methods=['GET'])
def download_recording(recording_id):
    """Download a recording file"""
    info = streamer_manager.get_recording_info(recording_id)
    if info and info.get('file_path'):
        directory = os.path.dirname(info['file_path'])
        filename = os.path.basename(info['file_path'])
        return send_from_directory(directory, filename, as_attachment=True)
    return jsonify({'error': 'Recording not found'}), 404


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    streamers = streamer_manager.get_all_streamers()
    recordings = streamer_manager.get_recordings()
    return jsonify({
        'streamers_count': len(streamers),
        'live_count': sum(1 for s in streamers if s.get('status') == 'live'),
        'recording_count': len([r for r in recordings if r.get('status') == 'recording']),
        'recordings_size': sum(r.get('file_size', 0) for r in recordings),
        'platforms': list(PLATFORMS.keys()),
        'config': {
            'web_port': config.web_port,
            'quality': config.quality,
            'auto_record': config.auto_record,
            'poll_interval': config.poll_interval
        }
    })


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get config"""
    # Don't send password back for security
    safe_config = {k: v for k, v in config._config.items() if k != 'password'}
    return jsonify(safe_config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update config - handles ALL settings from original projects"""
    data = request.json
    
    # Update all config values
    config.update_all(data)
    
    return jsonify({'success': True})


# Static files
@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording files"""
    return send_from_directory(config.downloads_dir, filename)


def main():
    """Main entry point"""
    global WEB_PORT
    
    # Ensure download directory exists
    os.makedirs(config.downloads_dir, exist_ok=True)
    
    # Start recorder background monitoring
    if config.check_on_startup:
        recorder.start_monitoring()
        print("[OK] Started monitoring {} streamers...".format(len(streamer_manager.get_all_streamers())))
    
# Print startup info
    print("""
==============================================================
           StreamHub v0.1.0                       
           Stream Recording Hub                      
==============================================================
Platforms: {}
Port: {}
Downloads: {}
Quality: {}
Auto-record: {}
==============================================================
""".format(
        ', '.join(PLATFORMS.keys())[:40],
        WEB_PORT,
        config.downloads_dir[:40],
        config.quality,
        config.auto_record
    ))
    
    # Run Flask
    app.run(host='0.0.0.0', port=WEB_PORT, debug=config.debug)


if __name__ == '__main__':
    main()
