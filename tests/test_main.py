from unittest.mock import MagicMock, patch
import sys
import pytest
sys.modules['obspython'] = MagicMock()

import main

@pytest.fixture
def keys(tmp_path):
    keys = tmp_path / "keys.env"
    keys.write_bytes(b"fake")

    return keys

def test_if_save_keys_saves_keys_correctly(tmp_path):
    main.src_keys = tmp_path / "keys.env"
    main.stream_keys = {
        "twitch": "TEST_TWITCH_KEY",    
        "kick": "TEST_KICK_KEY",    
        "tiktok": "TEST_TIKTOK_KEY",    
        "youtube": "TEST_YOUTUBE_KEY"
    }
    with patch('main.obs.obs_data_get_string', side_effect=lambda s, name: main.stream_keys[name]):
        main.save_keys(None, None)
    content = (tmp_path / "keys.env").read_text()
    
    assert "TWITCH_KEY=TEST_TWITCH_KEY" in content
    assert "KICK_KEY=TEST_KICK_KEY" in content
    assert "TIKTOK_KEY=TEST_TIKTOK_KEY" in content
    assert "YOUTUBE_KEY=TEST_YOUTUBE_KEY" in content

def test_if_is_stream_started_is_true_after_start_stream():
    with patch('main.subprocess.Popen'), patch('main.obs.obs_data_get_bool', return_value=True):
        main.start_stream(None, None)

    assert main.is_stream_started == True


def test_if_start_stream_fails_when_is_stream_started_is_true():
    main.is_stream_started = True
    with patch('main.obs.script_log') as mock_log:
        main.start_stream(None, None)
        mock_log.assert_called_with(main.obs.LOG_INFO, "Jesteś już w trakcie streamowania")

def test_if_stop_stream_changes_is_stream_started_to_false():
    main.is_stream_started = True
    with patch('main.obs.script_log') as mock_log:
        main.stop_stream(None, None)
    
    assert main.is_stream_started == False

def test_build_ffmpeg_command():
    result = main.build_ffmpeg_command("rtmp://live.twitch.tv/app", "TEST_KEY")
    assert result[-1] == "rtmp://live.twitch.tv/app/TEST_KEY"