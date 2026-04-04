"""
KisanVaani — General Advisor Agent
Greetings, general farming advice, fallback
"""

import logging
try:
    from utils.watsonx_client import WatsonxClient
except ImportError:
    from fieldflow.utils.watsonx_client import WatsonxClient
try:
    from utils.gemini_translator import GeminiTranslator
except ImportError:
    from fieldflow.utils.gemini_translator import GeminiTranslator
try:
    from utils.language_detector import detect_language
except ImportError:
    from fieldflow.utils.language_detector import detect_language

logger = logging.getLogger(__name__)

GENERAL_SYSTEM_PROMPT = """You are KisanVaani, a warm and helpful AI farming assistant for Indian farmers.
Rules:
- If this is a greeting: Say hello, introduce yourself briefly, list 5 things you can help with
- If a farming question: Give practical actionable advice for Indian conditions
- If unclear: Ask ONE clarifying question only
- Never say "I cannot help" — always give some useful guidance
- Refer to KVK helpline (1800-180-1551) for issues beyond your scope
- Keep to 3-4 sentences, warm and friendly tone

CRITICAL: Generate response ENTIRELY IN ENGLISH. No regional language, no markdown, no emojis. Translation will be handled by Gemini Translator after generation."""


class GeneralAdvisorAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(self, query: str, farmer: dict, memory: dict) -> str:
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))
        
        name = farmer.get("name", "")
        state = farmer.get("state", "")
        crop = farmer.get("crop_primary", "")

        context = f"Farmer name: {name or 'unknown'}. State: {state}. Main crop: {crop}."
        full_query = f"{context}\nFarmer says: {query}"

        response = await self.watsonx.generate(
            system_prompt=GENERAL_SYSTEM_PROMPT,
            user_message=full_query,
            max_tokens=200,
            temperature=0.5
        )
        
        if user_language != "en":
            response = self.translator.translate_and_clean(response, user_language)
        
        return response
