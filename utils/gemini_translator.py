import os
import httpx
import logging
from dotenv import load_dotenv

# Explicitly load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

class GeminiTranslator:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("❌ ERROR: GEMINI_API_KEY is missing from your .env file.")
        else:
            print("✅ Gemini Translator connected (Direct API Mode).")
            
        # Using the direct REST API endpoint to bypass deprecated libraries
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    def translate_and_clean(self, text: str, target_language: str) -> str:
        """
        Translates text and removes all formatting characters (**, #, etc.) 
        so the TTS engine doesn't sound glitchy.
        """
        if not text or target_language == 'en' or not self.api_key:
            return text

        # The 'Secret Sauce' prompt for clean audio
        prompt = f"""
        You are a professional translator for Indian farmers. 
        Translate the following English text into {target_language}.
        
        STRICT RULES:
        1. Return ONLY the translated spoken text.
        2. NO Markdown (No asterisks **, no hashtags #, no bullet points).
        3. NO emojis.
        4. Keep technical terms like 'eNAM', 'KVK', 'PM-KISAN' and all phone numbers in English.
        5. Make the tone conversational and natural for a farmer to hear.

        Text to translate:
        {text}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            # Direct HTTP request (No Google SDK required)
            with httpx.Client() as client:
                response = client.post(self.api_url, json=payload, timeout=15.0)
                response.raise_for_status() # Check for HTTP errors
                data = response.json()
                
                # Extract the text from the API response
                translated_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return translated_text.strip()
                
        except Exception as e:
            logger.error(f"⚠️ Gemini Translation failed: {e}")
            return text # Safe fallback to English