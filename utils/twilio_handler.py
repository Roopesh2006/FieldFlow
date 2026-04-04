"""
KisanVaani — Twilio WhatsApp Handler
Sends text and voice responses back to farmers
"""

import httpx
import base64
import logging
import tempfile
import os
from twilio.rest import Client
try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

logger = logging.getLogger(__name__)

_twilio_client = None


def get_twilio() -> Client:
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return _twilio_client


async def send_whatsapp_message(to: str, message: str):
    """Send text message via WhatsApp"""
    try:
        client = get_twilio()
        msg = client.messages.create(
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
            body=message[:1600]  # WhatsApp limit
        )
        logger.info(f"Message sent to {to}: {msg.sid}")
        return msg.sid
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")


async def send_whatsapp_voice(to: str, text_fallback: str, audio_url: str | None = None):
    """Send voice note via WhatsApp media URL + text fallback"""
    try:
        client = get_twilio()
        
        # Send with media URL if available (voice note)
        if audio_url:
            msg = client.messages.create(
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
                body=text_fallback[:1500],
                media_url=[audio_url]
            )
            logger.info(f"Voice note sent to {to}: {msg.sid} | Media: {audio_url}")
        else:
            # Fallback: send text with voice emoji if no audio URL
            msg = client.messages.create(
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to if to.startswith("whatsapp:") else f"whatsapp:{to}",
                body=f"🎙️ {text_fallback[:1500]}"
            )
            logger.info(f"Voice response (text fallback) sent to {to}: {msg.sid}")
        
        return msg.sid
    except Exception as e:
        logger.error(f"Failed to send voice response: {e}")
