"""
KisanVaani — Mandi Oracle Agent
Real-time mandi prices + sell/hold recommendation (Optimized for Gemini Translation)
"""
import httpx
import logging
import asyncio

# Corrected Imports
try:
    from utils.watsonx_client import WatsonxClient
except ImportError:
    from fieldflow.utils.watsonx_client import WatsonxClient

try:
    from utils.language_detector import detect_language
except ImportError:
    from fieldflow.utils.language_detector import detect_language

try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

from utils.gemini_translator import GeminiTranslator

logger = logging.getLogger(__name__)

# UPDATED: We now tell Watsonx to respond in ENGLISH only to avoid hallucinations.
# Gemini will handle the final translation.
MANDI_SYSTEM_PROMPT = """You are a concise farm assistant. Provide only the current market price, the MSP comparison, and one clear "Sell" or "Wait" recommendation. Maximum 3 short sentences. No greetings, no formatting, no links."""

COMMODITY_EXTRACTION_PROMPT = """You are a crop name normalizer for the Agmarknet API.
Extract the crop/commodity from the farmer's query and return ONLY the commodity name in English Title Case (e.g., "Rice", "Tomato").
Rules:
- If farmer says "அரிசி", respond: Rice
- If farmer says "गेहूँ", respond: Wheat
- Return ONLY the commodity name, nothing else."""

class MandiOracleAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(self, query: str, farmer: dict, memory: dict) -> str:
        # 1. Detect user's language
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))

        # 2. Extract commodity (English Title Case)
        commodity = await self._extract_commodity_for_api(query)
        if commodity == "Unknown" or not commodity:
            commodity = farmer.get("crop_primary", "Rice")

        state = farmer.get("state", "Tamil Nadu")
        district = farmer.get("district", "Madurai")

        # 3. Fetch live prices
        price_data = await self._fetch_mandi_prices(commodity, state, district)

        # 4. Generate the advice in ENGLISH (Pure Logic)
        context = f"Farmer asking about {commodity} prices in {district}, {state}.\nLive mandi data: {price_data}"
        
        response_en = await self.watsonx.generate(
            system_prompt=MANDI_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=150
        )

        # 5. Final Polishing Layer (Gemini)
        # We translate the clean English advice into perfect, conversational Tamil/Hindi
        if user_language != "en":
            logger.info(f"Polishing output for {user_language} using Gemini...")
            final_response = self.translator.translate_and_clean(response_en, user_language)
            return final_response

        return response_en

    async def _extract_commodity_for_api(self, query: str) -> str:
        try:
            commodity = await self.watsonx.generate(
                system_prompt=COMMODITY_EXTRACTION_PROMPT,
                user_message=query,
                max_tokens=10
            )
            return commodity.strip()
        except Exception as e:
            logger.error(f"Commodity extraction error: {e}")
            return ""

    async def _fetch_mandi_prices(self, crop: str, state: str, district: str) -> str:
        try:
            url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
            params = {
                "api-key": settings.AGMARKNET_API_KEY,
                "format": "json",
                "filters[state]": state,
                "filters[district]": district,
                "filters[commodity]": crop.lower(),
                "limit": 5
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10)
                data = resp.json()
                records = data.get("records", [])
                if records:
                    prices = [f"{r.get('market','')}: ₹{r.get('modal_price','N/A')}/quintal" for r in records[:3]]
                    return " | ".join(prices)
        except Exception as e:
            logger.error(f"Mandi API error: {e}")
        
        return f"Live price unavailable. Call 1800-270-0224 (eNAM helpline) for {crop} prices."