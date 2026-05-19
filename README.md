# OBS Multistream Plugin
OBS Python plugin for simultaneous streaming to multiple platforms (Twitch, YouTube, Kick, TikTok).

---

## Features

- Simultaneous streaming to up to 4 platforms at once
- Stream forwarding powered by [ffmpeg](https://ffmpeg.org/) and [MediaMTX](https://github.com/bluenviron/mediamtx)
- Built-in OBS panel — start/stop streams directly from OBS Scripts window
- Per-platform toggle — enable or disable each platform independently
- Stream key management via `.env` file
- Automatic MediaMTX startup on script load
- Error handling — warns when a stream key is missing or ffmpeg fails

---

## Requirements

- OBS Studio 28+ with Python scripting support
- Python 3.10+
- ffmpeg installed and available in PATH
- MediaMTX v1.9.0 (included in `bin/`)
- Linux (tested on Linux Mint 21.3)

---

## Installation

```bash
git clone https://github.com/AdrJM/obs-multistream-plugin.git
cd obs-multistream-plugin
pip install -r requirements.txt
```

Download MediaMTX and place it in `bin/`:

```bash
wget https://github.com/bluenviron/mediamtx/releases/download/v1.9.0/mediamtx_v1.9.0_linux_amd64.tar.gz
tar -xzf mediamtx_v1.9.0_linux_amd64.tar.gz
mkdir bin && mv mediamtx bin/
```

---

## Configuration

Create a `keys/keys.env` file based on the example:

```env
TWITCH_KEY=your_twitch_stream_key
YOUTUBE_KEY=your_youtube_stream_key
KICK_KEY=your_kick_stream_key
TIKTOK_KEY=your_tiktok_stream_key
```

Stream server URLs are preconfigured:

| Platform | RTMP URL |
|----------|----------|
| Twitch   | rtmp://live.twitch.tv/app |
| YouTube  | rtmp://a.rtmp.youtube.com/live2 |
| Kick     | rtmp://fa723fc1b171.global-contribute.live-video.net/app |
| TikTok   | rtmp://push.tiktokv.com/live |

---

## Usage

1. In OBS go to **Tools → Scripts** and add `main.py`
2. Configure OBS stream output to `rtmp://localhost/live/test` (**Settings → Stream → Custom**)
3. In the Scripts panel check which platforms you want to stream to
4. Click **Rozpocznij stream** in OBS to start sending video to MediaMTX
5. Click **Start** in the Scripts panel to forward the stream to all selected platforms
6. Click **Stop** to end all streams

---

## Project Structure

```
bin/            # MediaMTX binary
keys/           # Stream keys (.env) — not tracked by git
streaming/      # Stream management modules
tests/          # Tests
main.py         # OBS plugin entry point
```

---

## Roadmap

- [ ] Custom Browser Dock panel with stream status for each platform

---

If you find this project useful, you can support its development here:
 
[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/psychoamj)

## License

MIT