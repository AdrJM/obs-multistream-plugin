import subprocess
import threading
import time
import obspython as obs
import os
import os.path
import json
import shutil
from dotenv import load_dotenv
import platform

# ── Global state ──────────────────────────────────────────────────────────────
src_keys = None         # path to keys.env (stream keys)
stream_keys = {}        # dict of stream keys per platform
STREAM_URL = {          # RTMP endpoints for each platform
        "twitch": "rtmp://euc10.contribute.live-video.net/app/",
        "youtube": "rtmp://a.rtmp.youtube.com/live2",
        "kick": "rtmps://fa723fc1b171.global-contribute.live-video.net/",
        "tiktok": "rtmp://push.tiktokv.com/live"
    }

server_process = None       # Flask status server (server.py)
src_mediamtx = None         # path to mediamtx binary
current_settings = None     # reference to OBS settings object
stream_processes = {}       # active ffmpeg processes per platform
mediamtx_process = None     # mediamtx subprocess
is_stream_started = False   # flag to prevent double-start
chat_server_process = None  # chat logger subprocess (chat_server.py)
http_server_process = None  # HTTP server for chat overlay preview (python3 -m http.server)


def script_defaults(settings):
    """Load default values from .env files into OBS settings panel."""
    global src_keys, stream_keys
    src_keys = os.path.join(os.path.dirname(__file__), "config", "keys.env")
    chat_keys_path = os.path.join(os.path.dirname(__file__), "config", "chat.env")

    # Load both env files — chat.env overrides keys.env for shared keys
    load_dotenv(src_keys, override=True)
    load_dotenv(chat_keys_path, override=True)

    # Stream keys (used by ffmpeg to push to each platform)
    stream_keys = {
        "twitch": os.getenv("TWITCH_KEY"),    
        "kick": os.getenv("KICK_KEY"),    
        "tiktok": os.getenv("TIKTOK_KEY"),    
        "youtube": os.getenv("YOUTUBE_KEY")
    }
    for name, key in stream_keys.items():
        obs.obs_data_set_string(settings, name, key or "")

    # Chat logger credentials
    obs.obs_data_set_string(settings, "twitch_oauth",
        os.getenv("TWITCH_OAUTH") or "")
    obs.obs_data_set_string(settings, "twitch_client_id",
        os.getenv("TWITCH_CLIENT_ID") or "")
    obs.obs_data_set_string(settings, "twitch_client_secret",
        os.getenv("TWITCH_CLIENT_SECRET") or "")
    obs.obs_data_set_string(settings, "twitch_username",
        os.getenv("TWITCH_USERNAME") or "")
    obs.obs_data_set_string(settings, "twitch_channel",
        os.getenv("TWITCH_CHANNEL") or "")
    obs.obs_data_set_string(settings, "kick_channel",
        os.getenv("KICK_CHANNEL") or "")
    obs.obs_data_set_string(settings, "youtube_api_key",
        os.getenv("YOUTUBE_API_KEY") or "")
    obs.obs_data_set_string(settings, "youtube_channel_id",
        os.getenv("YOUTUBE_CHANNEL_ID") or "")
    obs.obs_data_set_string(settings, "logs_path",
        os.getenv("LOGS_PATH") or os.path.join(os.path.dirname(__file__), "logs"))


def on_event(event):
    """Handle OBS frontend events — start/stop stream automatically."""
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        start_stream(None, None)
    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        stop_stream(None, None)


def script_load(settings):
    """Called when OBS loads the script. Starts mediamtx and status server."""
    global current_settings, src_mediamtx, mediamtx_process, server_process

    obs.obs_frontend_add_event_callback(on_event)

    # Start Flask status server
    server_process = subprocess.Popen(["python3", 
        os.path.join(os.path.dirname(__file__), "server.py")])
    
    current_settings = settings
    src_mediamtx = os.path.join(os.path.dirname(__file__), "bin", "mediamtx")

    # Start mediamtx only if not already running
    try:
        if platform.system() == "Windows":
            subprocess.check_output(["tasklist", "/fi", "imagename eq mediamtx.exe"])
        else: 
            subprocess.check_output(["pgrep", "mediamtx"])
        obs.script_log(obs.LOG_INFO, "mediamtx już działa")
    except subprocess.CalledProcessError:
        mediamtx_process = subprocess.Popen(str(src_mediamtx))
    
    # Check for required dependencies
    if shutil.which("ffmpeg") is None:
        obs.script_log(obs.LOG_INFO, "ffmpeg nie jest zainstalowany")
        return 
    obs.script_log(obs.LOG_INFO, "ffmpeg jest już zainstalowany")

    if not os.path.exists(src_mediamtx):
        obs.script_log(obs.LOG_INFO, "mediamtx nie jest zainstalowany")
        return
    obs.script_log(obs.LOG_INFO, "mediamtx jest już zainstalowany")

def script_unload():
    """Called when OBS unloads the script. Terminates all subprocesses."""
    global mediamtx_process, server_process, chat_server_process, http_server_process
    if mediamtx_process is not None:
        mediamtx_process.terminate()
    if server_process:
        server_process.terminate()
    if chat_server_process:
        chat_server_process.terminate()
    if http_server_process:
        http_server_process.terminate()
        
def save_chat_keys(props, prop):
    """Save chat logger credentials to chat.env (separate from stream keys).
    
    Reads existing chat.env first to preserve keys not shown in the panel
    (e.g. TWITCH_REFRESH_TOKEN generated by OAuth), then overwrites only
    the keys that are managed through the UI.
    """
    # Preserve existing keys not shown in panel (e.g. refresh token from OAuth)
    existing = {}
    chat_keys_path = os.path.join(os.path.dirname(__file__), "config", "chat.env")
    if os.path.exists(chat_keys_path):
        with open(chat_keys_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    existing[k.strip()] = v.strip()

    # Override with values from the panel
    existing.update({
        "TWITCH_OAUTH":         obs.obs_data_get_string(current_settings, "twitch_oauth"),
        "TWITCH_USERNAME":      obs.obs_data_get_string(current_settings, "twitch_username"),
        "TWITCH_CHANNEL":       obs.obs_data_get_string(current_settings, "twitch_channel"),
        "TWITCH_CLIENT_ID":     obs.obs_data_get_string(current_settings, "twitch_client_id"),
        "TWITCH_CLIENT_SECRET": obs.obs_data_get_string(current_settings, "twitch_client_secret"),
        "KICK_CHANNEL":         obs.obs_data_get_string(current_settings, "kick_channel"),
        "YOUTUBE_API_KEY":      obs.obs_data_get_string(current_settings, "youtube_api_key"),
        "YOUTUBE_CHANNEL_ID":   obs.obs_data_get_string(current_settings, "youtube_channel_id"),
        "LOGS_PATH":            obs.obs_data_get_string(current_settings, "logs_path"),
    })

    with open(chat_keys_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    obs.script_log(obs.LOG_INFO, "klucze czatu zapisano")

def twitch_login(props, prop):
    """Open Twitch OAuth login in browser and auto-update token in settings panel.
    
    Starts twitch_auth.py as a subprocess which opens the browser and handles
    the OAuth callback. A background thread polls chat.env every second for up
    to 60 seconds waiting for the token to change, then calls refresh_chat_keys
    to update the panel automatically.
    """
    old_token = obs.obs_data_get_string(current_settings, "twitch_oauth")
    
    subprocess.Popen([
        "python3",
        os.path.join(os.path.dirname(__file__), "chat_logs", "twitch_auth.py")
    ])
    
    def wait_for_token():
        import time
        chat_keys_path = os.path.join(os.path.dirname(__file__), "config", "chat.env")
        for _ in range(60):  # poll for max 60 seconds
            time.sleep(1)
            values = {}
            if os.path.exists(chat_keys_path):
                with open(chat_keys_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line:
                            k, _, v = line.partition("=")
                            values[k.strip()] = v.strip()
            new_token = values.get("TWITCH_OAUTH", "")
            if new_token and new_token != old_token:
                # Token changed — update panel
                refresh_chat_keys(None, None)
                obs.script_log(obs.LOG_INFO, "Token Twitcha zaktualizowany automatycznie")
                return
    
    threading.Thread(target=wait_for_token, daemon=True).start()

def refresh_chat_keys(props, prop):
    """Reload chat credentials from chat.env directly into OBS settings panel.
    
    Reads the file directly instead of using load_dotenv — avoids the issue
    where os.getenv() returns cached values even after the file changes.
    Note: OBS does not expose an API to visually refresh the panel, so fields
    will show updated values only after the user reopens the settings window.
    """
    chat_keys_path = os.path.join(os.path.dirname(__file__), "config", "chat.env")
    
    values = {}
    if os.path.exists(chat_keys_path):
        with open(chat_keys_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    values[k.strip()] = v.strip()
    
    obs.obs_data_set_string(current_settings, "twitch_oauth",        values.get("TWITCH_OAUTH", ""))
    obs.obs_data_set_string(current_settings, "twitch_client_id",    values.get("TWITCH_CLIENT_ID", ""))
    obs.obs_data_set_string(current_settings, "twitch_client_secret",values.get("TWITCH_CLIENT_SECRET", ""))
    obs.obs_data_set_string(current_settings, "twitch_username",     values.get("TWITCH_USERNAME", ""))
    obs.obs_data_set_string(current_settings, "twitch_channel",      values.get("TWITCH_CHANNEL", ""))
    obs.obs_data_set_string(current_settings, "kick_channel",        values.get("KICK_CHANNEL", ""))
    obs.obs_data_set_string(current_settings, "youtube_api_key",     values.get("YOUTUBE_API_KEY", ""))
    obs.obs_data_set_string(current_settings, "youtube_channel_id",  values.get("YOUTUBE_CHANNEL_ID", ""))
    obs.obs_data_set_string(current_settings, "logs_path",           values.get("LOGS_PATH", ""))
    
    obs.script_log(obs.LOG_INFO, "dane czatu odświeżone")


def script_properties():
    """Build the OBS script settings UI with two collapsible groups."""
    props = obs.obs_properties_create()
    
    # ── Multistreaming group ──────────────────────────────────────────────────
    stream_group = obs.obs_properties_create()
    obs.obs_properties_add_text(stream_group, "twitch", "Klucz Twitch", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(stream_group, "twitch_enabled", "Streamuj na Twitch")
    obs.obs_properties_add_text(stream_group, "kick", "Klucz Kick", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(stream_group, "kick_enabled", "Streamuj na Kick")
    obs.obs_properties_add_text(stream_group, "tiktok", "Klucz TikTok", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(stream_group, "tiktok_enabled", "Streamuj na TikTok")
    obs.obs_properties_add_text(stream_group, "youtube", "Klucz YouTube", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(stream_group, "youtube_enabled", "Streamuj na YouTube")
    obs.obs_properties_add_button(stream_group, "save_keys", "Zapisz klucze", save_keys)
    obs.obs_properties_add_group(props, "stream_group", "Ustawienia multistreamingu", obs.OBS_GROUP_NORMAL, stream_group)

    # ── Chat logger group (checkable = enabled/disabled) ──────────────────────
    chat_group = obs.obs_properties_create()
    obs.obs_properties_add_button(chat_group, "twitch_login", "Połącz z Twitchem", twitch_login)
    obs.obs_properties_add_button(chat_group, "refresh_keys", "Odśwież dane z pliku", refresh_chat_keys)
    obs.obs_properties_add_text(chat_group, "twitch_oauth", "Twitch OAuth", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(chat_group, "twitch_client_id", "Twitch Client ID", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(chat_group, "twitch_client_secret", "Twitch Client Secret", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(chat_group, "twitch_username", "Twitch nazwa konta", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(chat_group, "twitch_channel", "Twitch kanał", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(chat_group, "kick_channel", "Kick kanał", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(chat_group, "youtube_api_key", "YouTube API key", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(chat_group, "youtube_channel_id", "YouTube Channel ID", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_path(chat_group, "logs_path", "Folder logów czatu", obs.OBS_PATH_DIRECTORY, "", None)
    obs.obs_properties_add_button(chat_group, "save_chat_keys", "Zapisz klucze czatu", save_chat_keys)
    obs.obs_properties_add_group(props, "chat_enabled", "Włącz chat logger", obs.OBS_GROUP_CHECKABLE, chat_group)
    
    obs.script_log(obs.LOG_INFO, "dane czatu odświeżone")

    return props


def script_update(settings):
    """Called whenever any setting changes. Syncs stream keys and logs path."""
    global stream_keys
    for name in stream_keys:
        value = obs.obs_data_get_string(settings, name)
        if value:
            stream_keys[name] = value

    # Keep logs_path in sync (needed because it's inside a group)
    logs_path = obs.obs_data_get_string(settings, "logs_path")
    if logs_path:
        obs.obs_data_set_string(settings, "logs_path", logs_path)


def save_keys(props, prop):
    """Save stream keys to keys.env."""
    current_keys = ""
    for name in stream_keys:
        stream_keys[name] = obs.obs_data_get_string(current_settings, name)
        current_keys += name.upper() + "_KEY=" + str(stream_keys[name]) + "\n"  
    with open(str(src_keys), "w") as f:
        f.write(current_keys)
    for name, key in stream_keys.items():
        obs.obs_data_set_string(current_settings, name, key or "")
    obs.script_log(obs.LOG_INFO, "nowe klucze zapisano")

def build_ffmpeg_command(url, key):
    """Build ffmpeg command to forward local RTMP stream to a platform."""
    return [
        "ffmpeg",
        "-i", "rtmp://localhost/live/test",  # input from mediamtx
        "-c", "copy",                         # no re-encoding
        "-f", "flv",
        "-progress", "pipe:2",                # bitrate output to stderr
        url + "/" + str(key)
    ]


def update_status(bitrate):
    """Write current stream status and bitrate to status.json.
    
    Used by chat_server.py to know which platforms are currently live.
    """
    all_status = {}
    for name in STREAM_URL:
        all_status[name] = {
            "active": name in stream_processes, 
            "bitrate": bitrate.get(name, "N/A")
        }    
    src_status = os.path.join(os.path.dirname(__file__), "config", "status.json")
    with open(src_status, "w") as f:
        json.dump(all_status, f)


def check_bitrate(process):
    """Read current bitrate from ffmpeg stderr output."""
    line = process.stderr.read1().decode('utf-8')
    for l in line.splitlines():
        if l.startswith('bitrate='):
            return l.split('=')[1]
    return "N/A"


def monitor_streams():
    """Background thread — monitors ffmpeg processes and restarts if they crash."""
    while is_stream_started:
        bitrates = {}
        for name, process in stream_processes.items():
            bitrates[name] = check_bitrate(process)
            if process.poll() is None:
                continue
            else:
                # Process died — update status and restart
                src_status = os.path.join(os.path.dirname(__file__), "config", "status.json")
                with open(src_status, "r") as f:
                    current = json.load(f)
                current[name] = "reconnecting"
                with open(src_status, "w") as f:
                    json.dump(current, f)
                stream_processes[name] = subprocess.Popen(
                    build_ffmpeg_command(STREAM_URL[name], stream_keys[name]),
                    stderr=subprocess.PIPE
                )
        update_status(bitrates)
        time.sleep(2)


def start_stream(props, prop):
    """Start ffmpeg processes for all enabled platforms and optionally chat logger."""
    global is_stream_started, chat_server_process, http_server_process

    if not is_stream_started:
        chat_enabled = obs.obs_data_get_bool(current_settings, "chat_enabled")
        obs.script_log(obs.LOG_INFO, f"chat_enabled: {chat_enabled}")
        obs.script_log(obs.LOG_INFO, f"logs_path: {obs.obs_data_get_string(current_settings, 'logs_path')}")

        # Start chat server if enabled — logs stdout/stderr to chat_server.log
        if chat_enabled:
            logs_path = obs.obs_data_get_string(current_settings, "logs_path")
            obs.script_log(obs.LOG_INFO, f"logs_path przekazany do chat_server: {logs_path}")
            log_file = open(os.path.join(os.path.dirname(__file__), "chat_logs", "chat_server.log"), "w")
            chat_server_process = subprocess.Popen([
                "python3",
                os.path.join(os.path.dirname(__file__), "chat_logs", "chat_server.py"),
                "--logs-path", logs_path
            ], stdout=log_file, stderr=log_file)

            # Start HTTP server for chat overlay preview in browser
            http_server_process = subprocess.Popen([
                "python3", "-m", "http.server", "8080"
            ], cwd=os.path.join(os.path.dirname(__file__), "chat_logs"))

        # Start ffmpeg for each enabled platform
        for name, url in STREAM_URL.items():
            enabled = obs.obs_data_get_bool(current_settings, name + "_enabled")
            key = stream_keys[name]
            if enabled and key is not None:
                try:
                    stream_processes[name] = subprocess.Popen(
                        build_ffmpeg_command(url, stream_keys[name]),
                        stderr=subprocess.PIPE
                    )
                except Exception as e:
                    obs.script_log(obs.LOG_INFO, f"{name}: błąd - {e}")
            else:
                obs.script_log(obs.LOG_INFO, f"Nie znaleziono danego klucza dla {name}")

        update_status({})
        is_stream_started = True
        
        # Start stream monitor in a daemon thread
        monitor_thread = threading.Thread(target=monitor_streams)
        monitor_thread.daemon = True
        monitor_thread.start()

        obs.script_log(obs.LOG_INFO, "Rozpoczęto streamowanie")
    else:
        obs.script_log(obs.LOG_INFO, "Jesteś już w trakcie streamowania")


def stop_stream(props, prop):
    """Terminate all ffmpeg processes and chat server, reset stream state."""
    global is_stream_started, chat_server_process, http_server_process

    if stream_processes:
        for name, process in stream_processes.items():
            process.terminate()
    
    if chat_server_process:
        chat_server_process.terminate()
        chat_server_process = None
    
    if http_server_process:
        http_server_process.terminate()
        http_server_process = None
        
    stream_processes.clear()
    update_status({})
    is_stream_started = False
    obs.script_log(obs.LOG_INFO, "Zakończono streamowanie")