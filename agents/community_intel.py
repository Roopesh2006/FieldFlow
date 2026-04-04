"""
KisanVaani — Community Intelligence Agent
Shows disease spread from nearby farmers
"""

import logging
try:
    from utils.watsonx_client import WatsonxClient
except ImportError:
    from fieldflow.utils.watsonx_client import WatsonxClient
try:
    from utils.language_detector import detect_language
except ImportError:
    from fieldflow.utils.language_detector import detect_language
try:
    from utils.gemini_translator import GeminiTranslator
except ImportError:
    from fieldflow.utils.gemini_translator import GeminiTranslator
try:
    from utils.db import get_community_alerts
except ImportError:
    from fieldflow.utils.db import get_community_alerts

logger = logging.getLogger(__name__)

COMMUNITY_SYSTEM_PROMPT = """You are a crop disease surveillance expert.
Present community disease alerts clearly. Rules:
- Start with: "Alert: X farmers in your area reported Y"
- Give severity: Low/Medium/High/CRITICAL
- For CRITICAL/High: say "Take precaution NOW"
- Recommend ONE preventive spray as precaution
- Keep to 3-4 sentences MAX
- RESPONSE MUST BE IN ENGLISH."""


class CommunityIntelAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(self, query: str, farmer: dict, memory: dict) -> str:
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))
        
        district = farmer.get("district", "")
        state = farmer.get("state", "")
        crop = farmer.get("crop_primary", "")

        alerts = await get_community_alerts(district, state)

        if not alerts:
            no_alert_msg = f"No disease outbreaks reported in {district} area in the last 7 days. Your crops seem safe! Continue regular monitoring."
            if user_language != "en":
                no_alert_msg = self.translator.translate_and_clean(no_alert_msg, user_language)
            return no_alert_msg

        alert_summary = "\n".join([
            f"- {a['disease_name']} on {a['crop']}: {a['report_count']} farmers, severity: {a['severity']}"
            for a in alerts[:3]
        ])

        context = f"""
Farmer in {district}, {state} grows {crop}.
Community disease reports from nearby farmers:
{alert_summary}
Farmer's question: {query}
"""
        response = await self.watsonx.generate(
            system_prompt=COMMUNITY_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=180
        )
        
        if user_language != "en":
            response = self.translator.translate_and_clean(response, user_language)
        
        return response
