"""
KisanVaani Orchestrator
Detects intent and routes to the right agent(s) in parallel
"""

import asyncio
import logging
from typing import Optional, Tuple
try:
    from utils.watsonx_client import WatsonxClient
except ImportError:
    from fieldflow.utils.watsonx_client import WatsonxClient

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for KisanVaani, an AI farm assistant.
Classify the farmer's query into EXACTLY ONE of these intents:
- crop_doctor     : disease, pest, yellowing, spots, rot, insect damage, leaf problem
- mandi           : price, bhav, rate, sell, market, mandi
- weather         : rain, irrigation, spraying, sowing, harvest timing, baarish
- scheme          : government scheme, subsidy, loan, PM-KISAN, benefit, yojana, sarkar madad
- community       : nearby farmers, area problem, others facing, spread
- general         : greeting, thanks, other farm advice

CRITICAL: You must accurately classify intents even if the user speaks in regional languages like Tamil, Hindi, Telugu, Marathi, Kannada, Bengali, Gujarati, or Punjabi. Translate the meaning internally before selecting the route. For example, if someone asks about prices in Tamil or Hindi, classify as 'mandi' regardless of language.

Respond with ONLY the intent word. Nothing else."""


class KisanOrchestrator:
    def __init__(self):
        self.watsonx = WatsonxClient()

    async def detect_intent(self, query: str) -> str:
        """Classify the farmer's query intent using watsonx.ai"""
        try:
            intent = await self.watsonx.generate(
                system_prompt=INTENT_SYSTEM_PROMPT,
                user_message=query,
                max_tokens=10
            )
            intent = intent.strip().lower()
            valid_intents = {"crop_doctor", "mandi", "weather", "scheme", "community", "general"}
            return intent if intent in valid_intents else "general"
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return "general"

    async def process(
        self,
        english_query: str,
        farmer: dict,
        original_query: str,
        language: str,
        image_url: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Main orchestration method.
        Returns (english_response, intent)
        """
        # Detect intent
        intent = await self.detect_intent(english_query)

        # Always fetch farmer memory in parallel (lightweight)
        memory_task = asyncio.create_task(self._get_farmer_context(farmer))

        # Route to the right agent
        if intent == "crop_doctor" or image_url:
            try:
                from agents.crop_doctor import CropDoctorAgent
            except ImportError:
                from fieldflow.agents.crop_doctor import CropDoctorAgent
            agent = CropDoctorAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory, image_url)

        elif intent == "mandi":
            try:
                from agents.mandi_oracle import MandiOracleAgent
            except ImportError:
                from fieldflow.agents.mandi_oracle import MandiOracleAgent
            agent = MandiOracleAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory)

        elif intent == "weather":
            try:
                from agents.vayu_guide import VayuGuideAgent
            except ImportError:
                from fieldflow.agents.vayu_guide import VayuGuideAgent
            agent = VayuGuideAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory)

        elif intent == "scheme":
            try:
                from agents.scheme_advisor import SchemeAdvisorAgent
            except ImportError:
                from fieldflow.agents.scheme_advisor import SchemeAdvisorAgent
            agent = SchemeAdvisorAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory)

        elif intent == "community":
            try:
                from agents.community_intel import CommunityIntelAgent
            except ImportError:
                from fieldflow.agents.community_intel import CommunityIntelAgent
            agent = CommunityIntelAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory)

        else:
            try:
                from agents.general_advisor import GeneralAdvisorAgent
            except ImportError:
                from fieldflow.agents.general_advisor import GeneralAdvisorAgent
            agent = GeneralAdvisorAgent()
            memory = await memory_task
            response = await agent.run(english_query, farmer, memory)

        return response, intent

    async def _get_farmer_context(self, farmer: dict) -> dict:
        """Get farmer memory context — recent disease history, last queries"""
        try:
            try:
                from utils.db import get_farmer_context
            except ImportError:
                from fieldflow.utils.db import get_farmer_context
            return await get_farmer_context(farmer.get("phone_number", ""))
        except Exception:
            return {}
