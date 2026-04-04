"""
KisanVaani — Configuration Settings
All API keys loaded from environment variables
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # ── IBM Watson ──────────────────────────────────────
    IBM_STT_API_KEY: str = ""
    IBM_STT_URL: str = "https://api.au-syd.speech-to-text.watson.cloud.ibm.com"

    IBM_TTS_API_KEY: str = ""
    IBM_TTS_URL: str = "https://api.au-syd.text-to-speech.watson.cloud.ibm.com"

    IBM_TRANSLATOR_API_KEY: str = ""
    IBM_TRANSLATOR_URL: str = "https://api.au-syd.language-translator.watson.cloud.ibm.com"

    # ── IBM watsonx.ai ───────────────────────────────────
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://us-south.ml.cloud.ibm.com"
    WATSONX_TOKEN: Optional[str] = None

    # ── Neo4j ────────────────────────────────────────────
    NEO4J_URI: str = ""
    NEO4J_USERNAME: str = ""
    NEO4J_PASSWORD: str = ""

    # ── Twilio (WhatsApp) ────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = "whatsapp:+14155238886"  # Twilio sandbox default

    # ── Ngrok Tunnel ─────────────────────────────────────
    NGROK_URL: str = ""  # e.g., https://xxxx-xx-xxx-xxx-xx.ngrok.io

    # ── Supabase ─────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # ── External APIs ────────────────────────────────────
    OPENWEATHER_API_KEY: str = ""
    AGMARKNET_API_KEY: str = ""         # data.gov.in
    GEMINI_API_KEY: str = ""

    # ── App ──────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    MAX_RESPONSE_TIME_MS: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
