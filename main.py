import subprocess

import obspython as obs
import os
import os.path
import shutil

from dotenv import load_dotenv

stream_keys = {}
STREAM_URL = {
        "twitch": "rtmp://live.twitch.tv/app",
        "youtube": "rtmp://a.rtmp.youtube.com/live2",
        "kick": "rtmp://fa723fc1b171.global-contribute.live-video.net/app",
        "tiktok": "rtmp://push.tiktokv.com/live"
    }

src_mediamtx = None
current_settings = None
stream_processes = {}
mediamtx_process = None

def script_load(settings):
    global stream_keys
    global current_settings 
    global src_mediamtx
    global mediamtx_process

    current_settings = settings

    src_mediamtx = os.path.join(os.path.dirname(__file__), "bin", "mediamtx")

    src_keys = os.path.join(os.path.dirname(__file__), "keys", "keys.env")

    load_dotenv(src_keys)

    stream_keys = {
        "twitch": os.getenv("TWITCH_KEY"),    
        "kick": os.getenv("KICK_KEY"),    
        "tiktok": os.getenv("TIKTOK_KEY"),    
        "youtube": os.getenv("YOUTUBE_KEY")
    }   
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

def script_properties():
    props = obs.obs_properties_create()
    
    obs.obs_properties_add_text(props, "twitch_k", "Klucz Twitch", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "twitch_enabled", "Streamuj na Twitch")

    obs.obs_properties_add_text(props, "kick_k", "Klucz Kick", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "kick_enabled", "Streamuj na Kick")
    
    obs.obs_properties_add_text(props, "tiktok_k", "Klucz TikTok", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "tiktok_enabled", "Streamuj na TikTok")

    obs.obs_properties_add_text(props, "youtube_key", "Klucz YouTube", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_bool(props, "youtube_enabled", "Streamuj na YouTube")
    
    obs.obs_properties_add_button(props, "start_live", "Start", start_stream)
    obs.obs_properties_add_button(props, "end_live", "End", stop_stream)

    return props

def start_stream(props, prop):  # start streaming
    
    for name, url in STREAM_URL.items():
        enabled = obs.obs_data_get_bool(current_settings, name + "_enabled")
        key = stream_keys[name]
        if enabled and key is not None:
            try:
                stream_processes[name] = subprocess.Popen([
                    "ffmpeg",
                    "-i",
                    "rtmp://localhost/live/test",
                    "-c",
                    "copy",
                    "-f",
                    "flv",
                    url + "/" + str(stream_keys[name])
                ])
            except Exception as e:
                obs.script_log(obs.LOG_INFO, f"{name}: błąd - {e}")
        else:
            obs.script_log(obs.LOG_INFO, f"Nie znaleziono danego klucza dla {name}")

    obs.script_log(obs.LOG_INFO, "Rozpoczęto streamowanie")

def stop_stream(props, prop):  # stop streaming
    if stream_processes:
        for name, process in stream_processes.items():
            process.terminate()
    
    obs.script_log(obs.LOG_INFO, "Zakończono streamowanie")
