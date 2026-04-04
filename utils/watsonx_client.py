"""
IBM watsonx.ai Client
Model: ibm/granite-3-8b-instruct (Granite 3.0 — active in us-south)
IMPORTANT: granite-13b-chat-v2 is DEPRECATED. Always use granite-3-8b-instruct.
Uses /ml/v1/text/chat endpoint with messages[] format (not /text/generation).
"""

import httpx
import logging
import time
try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

logger = logging.getLogger(__name__)

REGIONAL_TRANSLATION_PROMPT = """You are an expert translator for Indian regional languages.
Translate the English text to {language} maintaining professional and natural grammar.

CRITICAL RULES for translation:
1. NEVER create mixed-language hybrid words (e.g., do NOT write 'நன்ked' or 'helloவை')
2. For technical terms, acronyms (eNAM, KVK, SMS, PM-KISAN, Rs, KVK helpline), or brand names that don't translate naturally, RETAIN them EXACTLY as English words
3. For currency (Rs) and standard abbreviations, keep them unchanged
4. Ensure the translation reads naturally in {language} script
5. Maintain the original meaning and tone

Example: "Check eNAM (enam.gov.in) for more mandis near you" should be translated to:
- Tamil: "மேலும் மாண்டிகளுக்கு eNAM (enam.gov.in) ஐ சரிபார்க்கவும்"
- NOT: "eNAMஐ சரிபார்க்கவும்"

Translate now:"""

FARMING_SYSTEM_PROMPT = """You are FieldFlow, India's trusted AI agricultural advisor for farmers.
RULES — follow every single time:
1. Give SHORT, ACTIONABLE advice — max 4 sentences
2. Use product names available in Indian markets (Mancozeb, Ridomil, Confidor, DAP, Urea)
3. Cheapest solution FIRST, then better options
4. If recommending chemicals, add ONE safety tip
5. Prices in Indian Rupees
6. Indian seasons: Kharif (June-Nov), Rabi (Nov-April), Zaid (March-June)
7. Be empathetic — farmers are often in distress
8. Never say "I don't know" — give best available guidance
9. Max 120 words (will be translated to regional language)
10. End with one practical step the farmer can do TODAY
11. CRITICAL RULE: You must detect the language of the user's input and always respond in that exact same language. If the user writes in Tamil, you must reply in Tamil. If Hindi, reply in Hindi. Do not default to English unless the user writes in English.
12. LANGUAGE PURITY: Never create mixed-language hybrid words. Keep technical terms (Rs, SMS, KVK, PM-KISAN, eNAM) in English when they don't translate naturally."""


class WatsonxClient:
    def __init__(self):
        self._token_cache = {"token": None, "expires_at": 0}

    async def _get_token(self) -> str:
        if self._token_cache["token"] and time.time() < self._token_cache["expires_at"] - 60:
            return self._token_cache["token"]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://iam.cloud.ibm.com/identity/token",
                data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": settings.WATSONX_API_KEY},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20
            )
            data = response.json()
            token = data.get("access_token", "")
            expires = int(data.get("expiration", time.time() + 3600))
            self._token_cache = {"token": token, "expires_at": expires}
            return token

    async def generate(self, user_message: str, system_prompt: str = FARMING_SYSTEM_PROMPT,
                       max_tokens: int = 300, temperature: float = 0.3, context: str = "") -> str:
        try:
            token = await self._get_token()
            messages = [{"role": "system", "content": system_prompt}]
            if context:
                messages.append({"role": "system", "content": f"Farmer context:\n{context}"})
            messages.append({"role": "user", "content": user_message})

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.WATSONX_URL}/ml/v1/text/chat",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    params={"version": "2024-05-31"},
                    json={
                        "model_id": "ibm/granite-3-8b-instruct",
                        "messages": messages,
                        "parameters": {
                            "max_new_tokens": max_tokens,
                            "temperature": temperature,
                            "repetition_penalty": 1.1,
                            "decoding_method": "greedy"
                        },
                        "project_id": settings.WATSONX_PROJECT_ID
                    },
                    timeout=25
                )

                if response.status_code != 200:
                    logger.error(f"watsonx {response.status_code}: {response.text[:300]}")
                    return self._fallback(user_message)

                result = response.json()
                choices = result.get("choices", [])
                if choices:
                    generated = choices[0].get("message", {}).get("content", "").strip()
                    if generated:
                        logger.info(f"watsonx OK — {len(generated)} chars")
                        return generated
                logger.error(f"watsonx empty: {result}")
                return self._fallback(user_message)

        except httpx.TimeoutException:
            logger.error("watsonx timeout")
            return self._fallback(user_message)
        except Exception as e:
            logger.error(f"watsonx error: {e}", exc_info=True)
            return self._fallback(user_message)

    async def translate_fallback_message(self, english_text: str, target_language: str) -> str:
        """
        Translate fallback messages to regional languages with strict language purity.
        Prevents mixed-language hybrid words and retains technical terms in English.
        """
        if target_language == "en" or not english_text:
            return english_text
        
        # Language name map for the prompt
        lang_names = {
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "mr": "Marathi",
            "kn": "Kannada",
            "bn": "Bengali",
            "gu": "Gujarati",
            "pa": "Punjabi"
        }
        lang_name = lang_names.get(target_language, "regional language")
        
        translation_prompt = REGIONAL_TRANSLATION_PROMPT.format(language=lang_name)
        return await self.generate(
            user_message=english_text,
            system_prompt=translation_prompt,
            max_tokens=200,
            temperature=0.3
        )

    def _fallback(self, query: str) -> str:
        """Smart keyword fallback when watsonx unavailable"""
        q = query.lower()
        if any(w in q for w in ["disease","blight","spot","yellow","rot","pest","insect","fungus","पत्ते","रोग","पीले","spots","leaves"]):
            return ("Your crop may have a fungal disease. Spray Mancozeb 75WP at 2g per litre of water. "
                    "For organic option, use neem oil 5ml per litre. "
                    "Spray early morning and repeat after 7 days if symptoms persist.")
        if any(w in q for w in ["price","rate","bhav","mandi","sell","market","भाव"]):
            return ("Check today's mandi prices at enam.gov.in or call 1800-270-0224 (free). "
                    "Try to sell in groups with other farmers for better bargaining power.")
        if any(w in q for w in ["rain","weather","irrigat","water","spray","बारिश","सिंचाई"]):
            return ("Check weather at imd.gov.in before spraying. "
                    "Do not spray if rain is expected within 24 hours. "
                    "Irrigate early morning or evening to reduce evaporation.")
        if any(w in q for w in ["scheme","subsidy","loan","pm-kisan","yojana","सरकार","योजना","benefit","government"]):
            return ("You may be eligible for PM-KISAN (Rs.6,000/year) and PMFBY crop insurance. "
                    "Visit pmkisan.gov.in to check your status. "
                    "Call 1800-180-1551 (free) for complete scheme list for your state.")
        if any(w in q for w in ["hello","hi","namaste","help","नमस्ते","मदद","organic","tomato","farming"]):
            return ("Hello! I am FieldFlow, your AI farming assistant. "
                    "I can help with crop diseases, mandi prices, weather advice, and government schemes. "
                    "Send me a photo of your crop or describe your problem in any language!")
        return ("For immediate farming help, call the Kisan Call Centre: 1800-180-1551 (free, 24/7). "
                "You can also send me a photo of your crop and I will help diagnose the problem.")
