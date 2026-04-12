# StreamHub

A modular stream recording hub that monitors multiple streaming platforms, detects when streamers go live, and auto-records them in the best quality available. 
 
<img width="1920" height="793" alt="{869A455D-05B7-4046-B368-4862F411E21C}" src="https://github.com/user-attachments/assets/c1b36a94-1f68-4729-94e5-8db130565252" />
 
<img width="1921" height="462" alt="{65E3F779-6B75-484A-BA4F-C3FB3CA33137}" src="https://github.com/user-attachments/assets/4b3cfdbf-16e4-4405-b667-ee1e5cbcd0b8" />

<img width="1914" height="471" alt="{5E1F1598-2F1F-48A1-BC4B-456A922A2A7C}" src="https://github.com/user-attachments/assets/8da3d48e-f02a-4c65-a229-0195afa3aef5" />


## What's This?

StreamHub watches your favorite streamers across multiple platforms and records them automatically when they go live. Add them to the list and forget about it.

**Supported Platforms:**
| Platform | Detection | Recording |
|----------|-----------|-----------|
| Twitch | streamlink | streamlink |
| Kick | streamlink | streamlink |
| YouTube | streamlink | streamlink |
| StripChat | API | HLS/FFmpeg |
| Chaturbate | API | HLS/FFmpeg |
| CamSoda | API | HLS/FFmpeg |
| Flirt4Free | API | HLS/FFmpeg |
| MyFreeCams | API | HLS/FFmpeg |
| Cam4 | API | HLS/FFmpeg |
| Bongacams | API | HLS/FFmpeg |
| Fansly | API (auth token) | HLS/FFmpeg |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run it
python run.py
```

Opens at `http://localhost:6969`

## Requirements

- **Python 3.8+**
- **FFmpeg** - Must be in PATH or configured in settings
- **streamlink** - For Twitch/Kick/YouTube (optional)

## Default Directories

| OS | Recordings | Cache |
|---|------------|-------|
| Windows | `./recordings` | `%LOCALAPPDATA%\StreamHub\cache` |
| macOS | `./recordings` | `~/Library/Caches/StreamHub` |
| Linux | `./recordings` | `~/.cache/StreamHub` |

## Features

- **Auto-record** when streamers go live (toggle per streamer)
- **Best quality** recording automatically
- **Modular platform plugins** - easy to add new sites
- **Web UI** - all settings via browser
- **Compression** - re-encode recordings to save space
- **Password protection** - optional web lock
- **Graceful shutdown** -Ctrl+C finishes recordings properly

## Configuration

All through web UI at `/settings`:

| Setting | Description |
|---------|------------|
| Port | Web server port (default 6969) |
| Download Directory | Where recordings are saved |
| Quality | best/1080p/720p/480p |
| Auto-record | Auto-record when live |
| Poll Interval | Seconds between checks |
| Compression | Re-encode with H.264 |
| Compression Speed | ultrafast → veryslow |
| Compression CRF | 18=lossless, 23=default, 28=small |
| Convert to MP4 | Enable moov atom for browser |
| Password | Web UI protection |

### Compression

Enable to re-encode with H.264 after recording:
- **Speed** - Faster = larger file, slower = smaller file
- **CRF** - Lower = better quality
  - 18 = visually lossless (~50% reduction)
  - 23 = default (~60-70% reduction)
  - 28 = aggressive (~80% reduction)

## Fansly Setup

1. Log into fansly.com
2. Open DevTools (F12) → Console
3. Run:
```javascript
const s = localStorage.getItem("session_active_session");
const { token } = JSON.parse(s);
console.log(token);
```
4. Copy token → paste into Settings

## Password Protection

Set a password in Settings to protect the web UI. Leave blank for open access.

## Recording Playback

Recordings are saved as MP4 with faststart atom - works in browser/video players without transcoding.

Hover over thumbnails to preview 4 timestamps (start/25%/50%/end).

## Graceful Shutdown

Press Ctrl+C to stop - active recordings will finish and compress before exiting. MP4 files remain playable.

## Project Structure

```
StreamHub/
├── run.py                 # Main entry point
├── config.json           # Runtime config
├── streamers.json        # Streamer list
├── requirements.txt      # Python deps
├── backend/
│   ├── __init__.py
│   ├── config.py       # Config management
│   ├── streamer_manager.py  # Streamer CRUD
│   ├── recorder.py    # Recording engine
│   └── platforms/    # Platform integrations
│       ├── __init__.py
│       ├── streamonitor.py  # Adult sites
│       ├── streamlink.py  # Mainstream
│       └── fansly.py     # Fansly
└── web/
    ├── static/css/    # Styles
    └── templates/    # HTML
```

## Tech Stack

- **Flask** - Web server
- **streamlink** - Twitch/Kick/YouTube
- **FFmpeg** - Recording & compression
- **Python 3.8+**

## Credits

- **[streamlink](https://streamlink.github.io/)**
- **[StreaMonitor](https://github.com/losssless1024/streamonitor)** 
- **[StreamWarden](https://github.com/youg-o/streamwarden)** 
- **[Fansly-scraper](https://github.com/agnosto/fansly-scraper)** 


## License

MIT - Use however you want.

---
