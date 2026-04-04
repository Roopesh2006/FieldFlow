# utils/watson_stt.py

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import httpx
# ✅ Import the SDK's types under an alias to avoid shadowing Python's built-in `types` module
import google.genai.types as genai_types
from google import genai

try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

logger = logging.getLogger(__name__)

# --- Client Initialization ---
# Initialize once at module level (thread-safe, reusable)
GEMINI_API_KEY = settings.GEMINI_API_KEY  # Load from settings/.env
_gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-2.5-flash"


def _transcribe_gemini_sync(file_path: str) -> str:
    """
    Synchronous core: reads an .ogg file and sends it to Gemini for transcription.

    Uses Part.from_bytes() — the correct 2026 google-genai SDK method.
    Signature: Part.from_bytes(*, data: bytes, mime_type: str) -> Part

    Args:
        file_path: Path to a local .ogg audio file.

    Returns:
        Transcribed text string, or empty string on failure.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    audio_bytes = path.read_bytes()
    if not audio_bytes:
        raise ValueError(f"Audio file is empty: {file_path}")

    # ✅ Correct 2026 SDK syntax — keyword-only args, aliased import
    audio_part = genai_types.Part.from_bytes(
        data=audio_bytes,
        mime_type="audio/ogg",  # or "audio/webm", "audio/mpeg", etc.
    )

    prompt_part = genai_types.Part.from_text(
        text="Transcribe the audio accurately. Return only the transcribed text, no commentary."
    )

    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            genai_types.Content(
                role="user",
                parts=[audio_part, prompt_part],
            )
        ],
    )

    return response.text.strip() if response.text else ""


async def _transcribe_gemini(file_path: str) -> str:
    """
    Async wrapper: runs the blocking Gemini SDK call in a thread pool executor
    so it doesn't block FastAPI's event loop.

    Args:
        file_path: Path to a local .ogg audio file.

    Returns:
        Transcribed text string, or empty string on failure.
    """
    try:
        transcript = await asyncio.get_running_loop().run_in_executor(
            None,  # Uses the default ThreadPoolExecutor
            _transcribe_gemini_sync,
            file_path,
        )
        logger.info(f"Transcription successful for: {file_path}")
        return transcript
    except FileNotFoundError as e:
        logger.error(f"File error during transcription: {e}")
        return ""
    except Exception as e:
        logger.exception(f"Gemini transcription failed for {file_path}: {e}")
        return ""


# ── Public API ────────────────────────────────────────────────────────────────

async def transcribe_audio(
    audio_url: str | None = None,   # ✅ This says: "Can be string OR None"
    file_path: str | None = None,   # ✅ This says: "Can be string OR None"
    language: str = "ta",
) -> str:
    """
    Public API for transcribing audio files.
    
    Either provides a local file_path or audio_url (for Twilio downloads).
    Uses Gemini 2.5 Flash for transcription.

    Args:
        audio_url: URL to remote audio (e.g., from Twilio). Downloaded with Basic Auth, then transcribed.
        file_path: Path to local audio file (e.g., saved via transcribe flow). Used directly if provided.
        language: Language code (e.g., 'ta', 'hi', 'en'). Used for logging/context.

    Returns:
        Transcribed text string, or empty string on failure.
    """
    try:
        # If both are provided, prefer file_path
        if file_path:
            logger.info(f"Transcribing local file: {file_path} (language: {language})")
            transcript = await _transcribe_gemini(file_path)
        elif audio_url:
            logger.info(f"Downloading and transcribing from Twilio URL (language: {language})")
            
            # ── Step 1: Download from Twilio with Basic Auth ──────────────────
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        audio_url,
                        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                        follow_redirects=True,
                        timeout=30.0,
                    )
                
                if response.status_code != 200:
                    logger.error(f"Failed to download audio from Twilio: {response.status_code}")
                    return ""
                
                audio_bytes = response.content
                if not audio_bytes:
                    logger.error("Downloaded audio file is empty")
                    return ""
                
                logger.info(f"Successfully downloaded {len(audio_bytes)} bytes from Twilio")
                
            except Exception as e:
                logger.error(f"Error downloading from Twilio: {e}", exc_info=True)
                return ""
            
            # ── Step 2: Save to temp file ──────────────────────────────────────
            try:
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                logger.info(f"Saved downloaded audio to temp file: {tmp_path}")
            except Exception as e:
                logger.error(f"Error saving temp file: {e}", exc_info=True)
                return ""
            
            # ── Step 3: Transcribe via Gemini ──────────────────────────────────
            transcript = ""  # ← add this line
            try:
                transcript = await _transcribe_gemini(tmp_path)
            finally:
                # Always clean up the temp file
                try:
                    os.unlink(tmp_path)
                    logger.info(f"Cleaned up temp file: {tmp_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")
        else:
            logger.error("Must provide either audio_url or file_path")
            transcript = ""

        return transcript

    except Exception as e:
        logger.error(f"transcribe_audio failed: {e}", exc_info=True)
        return ""