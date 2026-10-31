"""Tests for Muse Voice Transcribe push-to-talk input (fully mocked, no network).

No test here requires a real API key or network access: HTTP is stubbed and
META_MODEL_API_KEY is controlled via monkeypatch with a fake value.
"""

import base64

import httpx
import pytest
from fastapi import HTTPException

import voice_client
from main import north_sea_storm_transcribe

FAKE_KEY = "test-key-not-real"
FAKE_WAV = b"RIFF....WAVEfake-audio-bytes"


def _ok_response(transcript="What if Rotterdam closes for six more hours?"):
    return httpx.Response(
        200,
        json={
            "transcript": transcript,
            "audioDurationMs": 2500,
            "sessionId": "session-123",
        },
        request=httpx.Request("POST", voice_client.TRANSCRIBE_URL),
    )


def test_request_part_is_deterministic():
    first = voice_client.build_request_part()
    assert first == voice_client.build_request_part()
    assert first["model"] == "muse-voice-transcribe-1.0"
    assert first["audioEncoding"] == "WAV"
    assert first["mode"] == "PUSH_TO_TALK"


def test_fetch_uses_documented_endpoint_and_multipart_shape(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["files"] = files
        captured["data"] = data
        return _ok_response()

    monkeypatch.setattr(voice_client.httpx, "post", fake_post)
    text = voice_client.fetch_transcript(FAKE_WAV, "clip.wav", FAKE_KEY)
    assert text == "What if Rotterdam closes for six more hours?"
    assert captured["url"] == "https://api.meta.ai/v1/asr/transcribe"
    assert captured["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert captured["files"]["audio"][0] == "clip.wav"
    assert captured["files"]["audio"][1] == FAKE_WAV
    import json

    request_part = json.loads(captured["data"]["request"])
    assert request_part["model"] == "muse-voice-transcribe-1.0"


def test_transcribe_reports_setup_required_without_key_and_no_network(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)

    def fail_post(*args, **kwargs):
        raise AssertionError("must not call network without a key")

    monkeypatch.setattr(voice_client.httpx, "post", fail_post)
    result = voice_client.transcribe_audio(FAKE_WAV, "clip.wav")
    assert result["source"] == "setup-required"
    assert result["text"] is None
    assert "META_MODEL_API_KEY" in result["detail"]


def test_transcribe_reports_unavailable_on_api_error(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)

    def error_post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(voice_client.httpx, "post", error_post)
    result = voice_client.transcribe_audio(FAKE_WAV, "clip.wav")
    assert result["source"] == "unavailable"
    assert result["text"] is None


def test_transcribe_reports_unavailable_on_malformed_payload(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    bad = httpx.Response(
        200,
        json={"no_transcript_here": True},
        request=httpx.Request("POST", voice_client.TRANSCRIBE_URL),
    )
    monkeypatch.setattr(voice_client.httpx, "post", lambda *a, **k: bad)
    result = voice_client.transcribe_audio(FAKE_WAV, "clip.wav")
    assert result["source"] == "unavailable"
    assert result["text"] is None


def test_transcribe_returns_text_on_success(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        voice_client.httpx, "post", lambda *a, **k: _ok_response("hello grid")
    )
    result = voice_client.transcribe_audio(FAKE_WAV, "clip.wav")
    assert result["source"] == "muse-voice-transcribe"
    assert result["text"] == "hello grid"
    assert result["model"] == "muse-voice-transcribe-1.0"


def _payload(b64=None, filename="clip.wav"):
    return {
        "audio_b64": b64 if b64 is not None else base64.b64encode(FAKE_WAV).decode(),
        "filename": filename,
    }


def test_endpoint_returns_transcript_with_mocked_voice(monkeypatch):
    monkeypatch.setenv("META_MODEL_API_KEY", FAKE_KEY)
    monkeypatch.setattr(
        voice_client.httpx, "post", lambda *a, **k: _ok_response("rail plus ten")
    )
    body = north_sea_storm_transcribe(_payload())
    assert body["source"] == "muse-voice-transcribe"
    assert body["text"] == "rail plus ten"


def test_endpoint_reports_setup_required_without_key(monkeypatch):
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    body = north_sea_storm_transcribe(_payload())
    assert body["source"] == "setup-required"
    assert body["text"] is None


def test_endpoint_rejects_empty_audio_with_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_transcribe(_payload(b64=""))
    assert exc_info.value.status_code == 400


def test_endpoint_rejects_oversize_audio_with_400(monkeypatch):
    monkeypatch.setattr(voice_client, "MAX_BYTES", 10)
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_transcribe(_payload())
    assert exc_info.value.status_code == 400


def test_endpoint_rejects_bad_base64_with_400():
    with pytest.raises(HTTPException) as exc_info:
        north_sea_storm_transcribe(_payload(b64="!!!not-base64!!!"))
    assert exc_info.value.status_code == 400
