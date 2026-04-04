"""
KisanVaani — WhatsApp AI Agricultural Assistant
Main FastAPI Application
"""

# ── Standard library ─────────────────────────────────────────────────────────
import asyncio
import logging
import os
import time
import uuid

# ── Third-party ──────────────────────────────────────────────────────────────
import httpx
from fastapi import BackgroundTasks, FastAPI, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from twilio.twiml.messaging_response import MessagingResponse

# ── Internal — relative imports (running from fieldflow/ directory) ─────────
from config.settings import settings
from agents.orchestrator import KisanOrchestrator
from utils.twilio_handler import send_whatsapp_message, send_whatsapp_voice
from utils.watson_stt import transcribe_audio
from utils.watson_tts import synthesize_speech
from utils.watson_translator import translate_from_english, translate_to_english
from utils.language_detector import detect_language
from utils.db import get_or_create_farmer, log_message

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="KisanVaani API",
    description="Voice-first multilingual AI agricultural assistant for Indian farmers",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static audio directory for serving TTS voice notes via Ngrok
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "audio_responses")
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

orchestrator = KisanOrchestrator()


# ── Health / root endpoints ───────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "KisanVaani",
        "status": "running",
        "tagline": "Har kisan ka AI saathi — Every farmer's AI companion",
        "languages": ["Hindi", "Tamil", "Telugu", "Marathi", "Kannada", "Bengali", "Gujarati", "Punjabi"],
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


# ── Background worker (all heavy lifting lives here) ─────────────────────────

async def process_whatsapp_message(
    phone_number: str,
    body: str | None,
    media_url: str | None,
    media_content_type: str | None,
) -> None:
    """
    Background task — runs after Twilio has already received the 200 <Response/>.

    Pipeline:
        1. Resolve / create farmer profile
        2. STT  — transcribe voice message via transcribe_audio()
        3. Language detection
        4. Translate input → English
        5. Log inbound message
        6. Orchestrate LLM agents
        7. Translate response → farmer's language
        8. TTS (voice) or plain text reply via Twilio
        9. Log outbound message
    """
    start_time = time.time()

    try:
        logger.info(f"[BG] Processing message from {phone_number}")

        # ── Step 1: Farmer profile ────────────────────────────────────────────
        farmer = await get_or_create_farmer(phone_number)

        raw_text: str = body or ""
        detected_language: str = "ta"   # TEMPORARY OVERRIDE — swap for detect_language() in production
        is_voice: bool = False

        # ── Step 2: Voice / audio message ────────────────────────────────────
        if media_content_type and "audio" in media_content_type and media_url:
            is_voice = True
            logger.info(f"[BG] Transcribing voice message from {phone_number}")

            # transcribe_audio now handles Twilio download with Basic Auth + Gemini transcription
            raw_text = await transcribe_audio(
                audio_url=media_url,
                language="ta",  # FORCE TAMIL FOR TESTING — remove when live
            )
            logger.info(f"[BG] Voice transcribed: {raw_text!r}")

        # ── Step 3: Language detection ────────────────────────────────────────
        if raw_text:
            detected_language = await detect_language(raw_text, farmer.get("language", "hi"))

        # ── Step 4: Translate input → English ────────────────────────────────
        english_text = await translate_to_english(raw_text, detected_language)

        # ── Step 5: Log inbound ───────────────────────────────────────────────
        await log_message(
            phone_number=phone_number,
            farmer_id=farmer.get("id"),
            direction="inbound",
            message_type="voice" if is_voice else "text",
            content=raw_text,
            language_detected=detected_language,
        )

        # ── Step 6: LLM orchestrator ──────────────────────────────────────────
        logger.info(f"[BG] Running LLM orchestrator for {phone_number}")
        image_url = media_url if media_content_type and "image" in (media_content_type or "") else None
        response_english, intent = await orchestrator.process(
            english_query=english_text,
            farmer=farmer,
            original_query=raw_text,
            language=detected_language,
            image_url=image_url,
        )

        # ── Step 7: Translate response → farmer's language ────────────────────
        final_response = await translate_from_english(response_english, detected_language)

        response_time_ms = int((time.time() - start_time) * 1000)

        # ── Step 8: Send reply ────────────────────────────────────────────────
        if is_voice:
            logger.info(f"[BG] Generating TTS via ElevenLabs for {phone_number}")
            import httpx as _httpx
            tts_response = await _httpx.AsyncClient().post(
                "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM",
                headers={
                    "xi-api-key": "sk_7b632fb3ff3c2acd8e4e7ff6d8496084e69792bc289856f9",
                    "Content-Type": "application/json",
                },
                json={"text": final_response, "model_id": "eleven_multilingual_v2"},
                timeout=30,
            )
            audio_content = tts_response.content
            audio_filename = f"response_{uuid.uuid4().hex[:8]}.mp3"
            audio_path = os.path.join(AUDIO_DIR, audio_filename)
            with open(audio_path, "wb") as fh:
                fh.write(audio_content)
            base_url = settings.NGROK_URL.rstrip("/") if settings.NGROK_URL else "http://localhost:8000"
            tts_audio_url = f"{base_url}/audio/{audio_filename}"
            await send_whatsapp_voice(phone_number, final_response, tts_audio_url)
        else:
            logger.info(f"[BG] Sending text response to {phone_number}")
            await send_whatsapp_message(phone_number, final_response)

        # ── Step 9: Log outbound ──────────────────────────────────────────────
        await log_message(
            phone_number=phone_number,
            farmer_id=farmer.get("id"),
            direction="outbound",
            message_type="voice" if is_voice else "text",
            content=final_response,
            intent=intent,
            response_time_ms=response_time_ms,
        )

        logger.info(
            f"[BG] ✅ Done in {response_time_ms}ms | intent={intent} | lang={detected_language}"
        )

    except Exception as exc:
        logger.error(f"[BG] ❌ Background processing error: {exc}", exc_info=True)
        try:
            fallback_msg = "Maaf kijiye, abhi kuch technical samasya hai. Thodi der baad phir try karein. 🙏"
            await send_whatsapp_message(phone_number, fallback_msg)
        except Exception as fallback_err:
            logger.error(f"[BG] Failed to send fallback message: {fallback_err}")


# ── Twilio webhook ────────────────────────────────────────────────────────────

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(None),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    """
    Receives Twilio webhook POST and returns <Response/> immediately (< 1 s).
    All processing is delegated to the background task to avoid the
    Twilio 11200 / 15-second timeout error.
    """
    background_tasks.add_task(
        process_whatsapp_message,
        From,               # → phone_number
        Body,               # → body
        MediaUrl0,          # → media_url
        MediaContentType0,  # → media_content_type
    )

    # Empty TwiML — tells Twilio "received, no immediate reply"
    return Response(content=str(MessagingResponse()), media_type="application/xml")


# ── Demo / dev endpoints ──────────────────────────────────────────────────────

@app.get("/demo/farmer/{phone}")
async def demo_farmer(phone: str):
    """Dev endpoint — look up or create a farmer profile."""
    farmer = await get_or_create_farmer(f"whatsapp:{phone}")
    return farmer


@app.get("/demo/community/{district}/{state}")
async def demo_community(district: str, state: str):
    """Dev endpoint — fetch community disease alerts for an area."""
    from utils.db import get_community_alerts
    return await get_community_alerts(district, state)