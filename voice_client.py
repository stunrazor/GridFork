"""Muse Voice Transcribe push-to-talk: speech to what-if text for the demo.

Documented values below come from Meta's official model cookbook
(https://github.com/meta-models/meta-model-cookbook,
06_muse_voice/01_voice_api_fundamentals/utils.py) and corroborating
provider briefs:
- One-shot endpoint ``POST https://api.meta.ai/v1/asr/transcribe``
- Model ``muse-voice-transcribe-1.0``
- Multipart body: JSON ``request`` part plus ``audio`` part, with
  ``Authorization: Bearer <key>``
- ``request`` requires ``model`` and ``audioEncoding: "WAV"``; ``mode``
  defaults to ``PUSH_TO_TALK`` (the caller delimits the turn by uploading
  a whole clip)
- Audio must be RIFF/WAVE, mono, signed 16-bit PCM, 16 or 24 kHz;
  caps are 32 MB and 10 minutes
- Response JSON carries the text in ``transcript``

The browser records and converts to 16 kHz mono WAV client-side, so this
module needs no audio toolchain. The API key is read from the
``META_MODEL_API_KEY`` environment variable and is never logged or
printed. Without a key, or when the call fails, the result reports
``setup-required`` / ``unavailable`` with no invented transcript.
"""

import json
import os

import httpx

# Verified contract. Do not change without checking the cookbook recipe
# above and https://dev.meta.ai/docs/speech-to-text.
TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL_ID = "muse-voice-transcribe-1.0"
API_KEY_ENV_VAR = "META_MODEL_API_KEY"
MODE = "PUSH_TO_TALK"

# Server caps: 32 MB body / 10 minutes of audio. Reject oversized uploads
# locally instead of sending a request the server would refuse.
MAX_BYTES = 32 * 1024 * 1024


def build_request_part() -> dict:
    """Build the deterministic JSON ``request`` part for one clip."""
    return {"model": MODEL_ID, "audioEncoding": "WAV", "mode": MODE}


def fetch_transcript(
    audio_bytes: bytes, filename: str, api_key: str, timeout: float = 60.0
) -> str:
    """Post one WAV clip and return the transcript text.

    Raises on transport errors, non-2xx status, or a payload without a
    usable ``transcript`` string. The key is sent only as a Bearer
    header and never logged.
    """
    response = httpx.post(
        TRANSCRIBE_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        files={"audio": (filename, audio_bytes, "audio/wav")},
        data={"request": json.dumps(build_request_part())},
        timeout=timeout,
    )
    response.raise_for_status()
    transcript = response.json().get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError("transcribe reply has no usable transcript")
    return transcript


def transcribe_audio(audio_bytes: bytes, filename: str) -> dict:
    """Transcribe a clip, or report setup/unavailable without guessing."""
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return {
            "source": "setup-required",
            "model": MODEL_ID,
            "text": None,
            "detail": (
                f"No API key: set {API_KEY_ENV_VAR} to transcribe with "
                f"{MODEL_ID}."
            ),
        }
    try:
        text = fetch_transcript(audio_bytes, filename, api_key)
    except Exception:
        return {
            "source": "unavailable",
            "model": MODEL_ID,
            "text": None,
            "detail": "Muse Voice Transcribe call failed; no transcript produced.",
        }
    return {"source": "muse-voice-transcribe", "model": MODEL_ID, "text": text}
