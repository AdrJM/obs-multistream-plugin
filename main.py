import subprocess
import threading
import time
import obspython as obs
import os
import os.path
import json
import shutil
from dotenv import load_dotenv

src_keys = None
stream_keys = {}
STREAM_URL = {
        "twitch": "rtmp://euc10.contribute.live-video.net/app/",
        "youtube": "rtmp://b.rtmp.youtube.com/live2?backup=1",
        "kick": "rtmps://fa723fc1b171.global-contribute.live-video.net/",
        "tiktok": "rtmp://push.tiktokv.com/live"
    }

server_process = None
src_mediamtx = None
current_settings = None
stream_processes = {}
mediamtx_process = None
is_stream_started = False

def script_defaults(settings):
    global src_keys, stream_keys
    src_keys = os.path.join(os.path.dirname(__file__), "config", "keys.env")
    load_dotenv(src_keys, override=True)
    stream_keys = {
        "twitch": os.getenv("TWITCH_KEY"),    
        "kick": os.getenv("KICK_KEY"),    
        "tiktok": os.getenv("TIKTOK_KEY"),    
        "youtube": os.getenv("YOUTUBE_KEY")
    }
    for name, key in stream_keys.items():
        obs.obs_data_set_string(settings, name, key or "")

def on_event(event):
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        start_stream(None, None)
    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        stop_stream(None, None)

def script_load(settings):
    global current_settings 
    global src_mediamtx
    global mediamtx_process
    global server_process
    

    obs.obs_frontend_add_event_callback(on_event)

    server_process = subprocess.Popen(["python3", 
        os.path.join(os.path.dirname(__file__), "server.py")])
    
    current_settings = settings

    src_mediamtx = os.path.join(os.path.dirname(__file__), "bin", "mediamtx")

    try:
        subprocess.check_output(["pgrep", "mediamtx"])
        obs.script_log(obs.LOG_INFO, "mediamtx już działa")
    except subprocess.CalledProcessError:
        mediamtx_process = subprocess.Popen(str(src_mediamtx))
    
    if shutil.which("ffmpeg") is None:
        obs.script_log(obs.LOG_INFO, "ffmpeg nie jest zainstalowany")
        return 
        
    obs.script_log(obs.LOG_INFO, "ffmpeg jest już zainstalowany")
    if not os.path.exists(src_mediamtx):
        obs.script_log(obs.LOG_INFO, "mediamtx nie jest zainstalowany")
        return
    

    obs.script_log(obs.LOG_INFO, "mediamtx jest już zainstalowany")

def script_unload():
    if mediamtx_process is not None:
        mediamtx_process.terminate()
    if server_process:
        server_process.terminate()

def script_properties():
    props = obs.obs_properties_create()
    
    obs.obs_properties_add_text(props, "twitch", "Klucz Twitch", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "twitch_enabled", "Streamuj na Twitch")

    obs.obs_properties_add_text(props, "kick", "Klucz Kick", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "kick_enabled", "Streamuj na Kick")
    
    obs.obs_properties_add_text(props, "tiktok", "Klucz TikTok", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "tiktok_enabled", "Streamuj na TikTok")

    obs.obs_properties_add_text(props, "youtube", "Klucz YouTube", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "youtube_enabled", "Streamuj na YouTube")

    obs.obs_properties_add_button(props, "save_keys", "Zapisz klucze", save_keys)

    return props

def script_update(settings):
    global stream_keys
    for name in stream_keys:
        value = obs.obs_data_get_string(settings, name)
        if value:
            stream_keys[name] = value

def save_keys(props, prop):
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
    return [
            "ffmpeg",
            "-i",
            "rtmp://localhost/live/test",
            "-c",
            "copy",
            "-f",
            "flv",
            url + "/" + str(key)
        ]

def update_status():
    all_status = {}
    for name in STREAM_URL:
        all_status[name] = name in stream_processes
    
    src_status = os.path.join(os.path.dirname(__file__), "config", "status.json")
    with open(src_status, "w") as f:
        json.dump(all_status, f)

def monitor_streams():
    while is_stream_started:
        for name, process in stream_processes.items():
            if process.poll() == None:
                continue
            else:
                stream_processes[name] = subprocess.Popen(build_ffmpeg_command(STREAM_URL[name], stream_keys[name]))
                update_status()
        time.sleep(5)

def start_stream(props, prop):  # start streaming
    global is_stream_started

    if not is_stream_started:
        for name, url in STREAM_URL.items():
            enabled = obs.obs_data_get_bool(current_settings, name + "_enabled")
            key = stream_keys[name]
            if enabled and key is not None:
                try:
                    stream_processes[name] = subprocess.Popen(build_ffmpeg_command(url, stream_keys[name]))
                except Exception as e:
                    obs.script_log(obs.LOG_INFO, f"{name}: błąd - {e}")
            else:
                obs.script_log(obs.LOG_INFO, f"Nie znaleziono danego klucza dla {name}")
        update_status()
        is_stream_started = True
        
        monitor_thread = threading.Thread(target=monitor_streams)
        monitor_thread.daemon = True
        monitor_thread.start()

        obs.script_log(obs.LOG_INFO, "Rozpoczęto streamowanie")
    else:
        obs.script_log(obs.LOG_INFO, "Jesteś już w trakcie streamowania")

def stop_stream(props, prop):  # stop streaming
    global is_stream_started

    if stream_processes:
        for name, process in stream_processes.items():
            process.terminate()
    
    stream_processes.clear()
    update_status()
    is_stream_started = False
    obs.script_log(obs.LOG_INFO, "Zakończono streamowanie")

