"""
IBM Watson Language Translator Integration
Bidirectional translation: regional ↔ English
"""

import httpx
import logging
import time
try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

logger = logging.getLogger(__name__)

# Token cache for Watson Translator IAM tokens
_token_cache = {"token": None, "expires_at": 0}


async def _get_iam_token(api_key: str) -> str:
    """Get IBM IAM token for Watson Language Translator authentication"""
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
                    "response_type": "cloud_iam"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20
            )
            if response.status_code != 200:
                logger.error(f"Failed to get IAM token: {response.status_code}")
                return ""
            data = response.json()
            token = data.get("access_token", "")
            expires = int(data.get("expiration", time.time() + 3600))
            _token_cache = {"token": token, "expires_at": expires}
            return token
    except Exception as e:
        logger.error(f"Error getting IAM token: {e}")
        return ""

# IBM Watson Language Translator model IDs
TO_ENGLISH = {
    "hi": "hi-en",   # Hindi → English
    "ta": "ta-en",   # Tamil → English
    "te": "te-en",   # Telugu → English
    "mr": "mr-en",   # Marathi → English
    "kn": "kn-en",   # Kannada → English
    "bn": "bn-en",   # Bengali → English
    "gu": "gu-en",   # Gujarati → English
    "pa": "pa-en",   # Punjabi → English
    "en": None,      # Already English
}

FROM_ENGLISH = {
    "hi": "en-hi",
    "ta": "en-ta",
    "te": "en-te",
    "mr": "en-mr",
    "kn": "en-kn",
    "bn": "en-bn",
    "gu": "en-gu",
    "pa": "en-pa",
    "en": None,
}


async def _translate(text: str, model_id: str) -> str:
    """Core translation function using IBM Watson Language Translator"""
    if not settings.IBM_TRANSLATOR_API_KEY:
        return text
    try:
        token = await _get_iam_token(settings.IBM_TRANSLATOR_API_KEY)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.IBM_TRANSLATOR_URL}/v3/translate",
                params={"version": "2018-05-01"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "text": [text],
                    "model_id": model_id
                },
                timeout=15
            )
            result = response.json()
            translated = result["translations"][0]["translation"]
            return translated.strip()
    except Exception as e:
        logger.error(f"Translation failed [{model_id}]: {e}")
        return text  # Return original if translation fails


async def translate_to_english(text: str, language: str) -> str:
    """Translate regional language text to English for AI processing"""
    if language == "en" or not text:
        return text
    model_id = TO_ENGLISH.get(language)
    if not model_id:
        return text
    return await _translate(text, model_id)


async def translate_from_english(text: str, language: str) -> str:
    """Translate English AI response back to farmer's regional language"""
    if language == "en" or not text:
        return text
    model_id = FROM_ENGLISH.get(language)
    if not model_id:
        return text
    return await _translate(text, model_id)
