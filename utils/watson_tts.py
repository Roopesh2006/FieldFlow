"""
KisanVaani — Text-to-Speech
- Hindi      : IBM Watson (hi-IN_MeeraV3Voice) — native support
- All others : Gemini 2.5 Flash TTS — Tamil, Telugu, Kannada, etc.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
import time

import httpx

try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings  # type: ignore[no-redef]

logger = logging.getLogger(__name__)

# ── IBM Watson IAM token cache ────────────────────────────────────────────────
_token_cache: dict = {"token": None, "expires_at": 0}


async def _get_iam_token(api_key: str) -> str:
    """Fetch (or return cached) IBM Cloud IAM bearer token."""
    global _token_cache
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": api_key,
                    "response_type": "cloud_iam",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
            if response.status_code != 200:
                logger.error(f"IAM token fetch failed: {response.status_code}")
                return ""
            data = response.json()
            token = data.get("access_token", "")
            expires = int(data.get("expiration", time.time() + 3600))
            _token_cache = {"token": token, "expires_at": expires}
            return token
    except Exception as e:
        logger.error(f"IAM token error: {e}")
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize_speech(text: str, language: str = "hi") -> bytes:
    """
    Convert text to speech and return OGG Opus bytes (WhatsApp-compatible).

    Hindi   → IBM Watson  (hi-IN_MeeraV3Voice)
    Others  → Gemini 2.5 Flash TTS
    """
    if language == "hi":
        return await _synthesize_watson(text, "hi-IN_MeeraV3Voice")
    else:
        return await _synthesize_gemini(text, language)


# ── Watson (Hindi) ────────────────────────────────────────────────────────────

async def _synthesize_watson(text: str, voice: str) -> bytes:
    """IBM Watson TTS — used for Hindi only. Returns OGG Opus bytes."""
    try:
        text_to_speak = text[:4900]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.IBM_TTS_URL}/v1/synthesize",
                headers={
                    "Authorization": f"Bearer {await _get_iam_token(settings.IBM_TTS_API_KEY)}",
                    "Content-Type": "application/json",
                    "Accept": "audio/ogg;codecs=opus",
                },
                json={"text": text_to_speak, "voice": voice},
                timeout=30,
            )
            if response.status_code == 200:
                logger.info(f"Watson TTS generated {len(response.content)} bytes")
                return response.content
            logger.error(f"Watson TTS HTTP error: {response.status_code}")
    except Exception as e:
        logger.error(f"Watson TTS failed: {e}")
    return b""


# ── Gemini TTS (all other languages) ─────────────────────────────────────────

# Gemini prebuilt voices that handle Indian languages well
_GEMINI_VOICES = {
    "ta": "Kore",    # Tamil
    "te": "Charon",  # Telugu
    "kn": "Kore",    # Kannada
    "bn": "Leda",    # Bengali
    "gu": "Aoede",   # Gujarati
    "pa": "Charon",  # Punjabi
    "mr": "Leda",    # Marathi
    "en": "Kore",    # English fallback
}


async def _synthesize_gemini(text: str, language: str) -> bytes:
    """Async wrapper — offloads blocking Gemini SDK call to thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _synthesize_gemini_sync, text, language)


def _synthesize_gemini_sync(text: str, language: str) -> bytes:
    """
    Calls Gemini 2.5 Flash TTS, gets raw PCM audio, converts to OGG Opus via ffmpeg.
    Runs synchronously inside a thread pool executor.
    """
    import google.genai.types as genai_types
    from google import genai

    voice_name = _GEMINI_VOICES.get(language, "Kore")
    pcm_path: str = ""
    opus_path: str = ""

    try:
        # ── 1. Call Gemini TTS ────────────────────────────────────────────────
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )

        # ── 2. Extract raw PCM bytes from response ────────────────────────────
        candidate = response.candidates[0]  # type: ignore[index]
        part = candidate.content.parts[0]   # type: ignore[union-attr]
        audio_data: bytes = part.inline_data.data  # type: ignore[union-attr]
        if not audio_data:
            logger.error("Gemini TTS returned empty audio data")
            return b""

        # ── 3. Write PCM to temp file ─────────────────────────────────────────
        with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as pcm_file:
            pcm_file.write(audio_data)
            pcm_path = pcm_file.name

        opus_path = pcm_path.replace(".pcm", ".ogg")

        # ── 4. ffmpeg: PCM → OGG Opus (WhatsApp-compatible) ──────────────────
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "s16le",   # 16-bit signed little-endian PCM
                "-ar", "24000",  # Gemini TTS output sample rate
                "-ac", "1",      # mono
                "-i", pcm_path,
                "-c:a", "libopus",
                "-b:a", "24k",
                opus_path,
            ],
            check=True,
            capture_output=True,
        )

        # ── 5. Read result ────────────────────────────────────────────────────
        with open(opus_path, "rb") as f:
            result = f.read()

        logger.info(f"Gemini TTS generated {len(result)} bytes for [{language}] voice={voice_name}")
        return result

    except Exception as e:
        logger.error(f"Gemini TTS failed for [{language}]: {e}", exc_info=True)
        return b""

    finally:
        # ── 6. Always clean up temp files ─────────────────────────────────────
        for path in (pcm_path, opus_path):
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass