"""
KisanVaani — Scheme Advisor Agent
Matches farmer to eligible government schemes
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
try:
    from utils.db import match_schemes
except ImportError:
    from fieldflow.utils.db import match_schemes

logger = logging.getLogger(__name__)

SCHEME_SYSTEM_PROMPT = """You are a government scheme expert for Indian farmers.
Present matching schemes clearly. Rules:
- List max 3 most relevant schemes
- For each: Name, Benefit amount, How to apply (one line)
- Start with: "Here are eligible schemes for you:" (in English)
- Always mention PM-KISAN if farmer has less than 5 acres
- End with helpline: 1800-180-1551 (free call)
- Keep to 5-6 sentences MAX

CRITICAL: Generate response ENTIRELY IN ENGLISH. No regional language, no markdown, no emojis. Translation will be handled by Gemini Translator after generation."""


class SchemeAdvisorAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(self, query: str, farmer: dict, memory: dict) -> str:
        # ── Detect user language ─────────────────────────────────────────
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))
        
        schemes = await match_schemes(farmer)

        scheme_list = "\n".join([
            f"- {s['scheme_name']}: {s['benefit_amount']} | Apply: {s.get('apply_url','')}"
            for s in schemes
        ]) if schemes else "PM-KISAN, PMFBY, KCC"

        context = f"""
Farmer profile: State={farmer.get('state','')}, Land={farmer.get('land_holding_acres','')} acres,
Crop={farmer.get('crop_primary','')}, Annual income=₹{farmer.get('income_annual_inr','')}
Matching schemes found:
{scheme_list}
Farmer's question: {query}
"""
        response = await self.watsonx.generate(
            system_prompt=SCHEME_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=250
        )
        
        # ── Translate & clean for voice output ───────────────────────────
        if user_language != "en":
            response = self.translator.translate_and_clean(response, user_language)
        
        return response
