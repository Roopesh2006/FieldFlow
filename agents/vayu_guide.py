"""
KisanVaani — Vayu Guide Agent
Weather-based irrigation, spraying and sowing advice
"""

import httpx
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
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings

logger = logging.getLogger(__name__)

WEATHER_SYSTEM_PROMPT = """You are a farm meteorologist for Indian agriculture.
Given weather data, give specific agricultural advice.
Rules:
- Mention today and next 2 days weather briefly
- Give ONE specific action: irrigate/don't irrigate, spray/don't spray, sow/wait
- Give EXACT timing if needed (e.g., "irrigate tomorrow morning 6am, 30 minutes per row")
- For spraying: warn if rain expected within 24 hours (spray will wash off)
- For sowing: mention soil moisture requirement
- Keep to 3-4 sentences MAX
- RESPONSE MUST BE IN ENGLISH."""

LOCATION_EXTRACTION_PROMPT = """Extract the city or location name from this farmer's query about weather.
If a city name is mentioned (e.g., Bengaluru, Chennai, Delhi), return ONLY that city name.
If no city is found, return the farmer's state/region if mentioned.
If neither, return 'default'.
Examples:
- 'What is the weather in Bengaluru?' → Bengaluru
- 'Is it raining in Bangalore?' → Bangalore
- 'Rain forecast for Tamil Nadu' → Tamil Nadu
- 'What weather today?' → default

Respond with ONLY the location name, nothing else."""


class VayuGuideAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(self, query: str, farmer: dict, memory: dict) -> str:
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))
        
        district = farmer.get("district", "")
        state = farmer.get("state", "")
        crop = farmer.get("crop_primary", "crops")

        # If district/state are empty, extract location from query
        if not district or not state:
            location = await self._extract_location_from_query(query)
            logger.info(f"[Weather] Extracted location from query: {location}")
            weather_data = await self._fetch_weather_by_city(location)
        else:
            logger.info(f"[Weather] Using farmer profile location: {district}, {state}")
            weather_data = await self._fetch_weather(district, state)

        context = f"""
Farmer in {district or 'unknown'}, {state or 'unknown'} growing {crop}.
Query: {query}
Current weather data: {weather_data}
"""
        response = await self.watsonx.generate(
            system_prompt=WEATHER_SYSTEM_PROMPT,
            user_message=context,
            max_tokens=180
        )
        
        if user_language != "en":
            response = self.translator.translate_and_clean(response, user_language)
        
        return response

    async def _extract_location_from_query(self, query: str) -> str:
        """Use LLM to extract city/location name from query"""
        try:
            location = await self.watsonx.generate(
                system_prompt=LOCATION_EXTRACTION_PROMPT,
                user_message=query,
                max_tokens=20
            )
            return location.strip() or "default"
        except Exception as e:
            logger.error(f"Location extraction failed: {e}")
            return "default"

    async def _fetch_weather_by_city(self, city: str) -> str:
        """Fetch current weather by city name from OpenWeatherMap"""
        if not city or city.lower() == "default":
            return "Location not specified. Please mention a city (e.g., 'Bengaluru', 'Chennai') in your query."
        
        try:
            logger.info(f"[Weather] Fetching weather for city: {city}")
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"},
                    timeout=10
                )
                if resp.status_code != 200:
                    logger.error(f"OpenWeatherMap error: {resp.status_code}")
                    return "Weather data unavailable for this location."
                
                data = resp.json()
                desc = data["weather"][0]["description"]
                temp = data["main"]["temp"]
                rain = data.get("rain", {}).get("1h", 0)
                humidity = data["main"]["humidity"]
                
                summary = f"Current weather in {city}: {desc}, {temp}°C, rain:{rain}mm, humidity:{humidity}%"
                logger.info(f"[Weather] Successfully fetched: {summary}")
                return summary
        except Exception as e:
            logger.error(f"Weather API error for city {city}: {e}")
            return "Weather data unavailable. Check IMD website (imd.gov.in) for exact forecast."

    async def _fetch_weather(self, district: str, state: str) -> str:
        """Fetch 3-day forecast from OpenWeatherMap"""
        try:
            logger.info(f"[Weather] Fetching weather for district: {district}, state: {state}")
            geo_url = "https://api.openweathermap.org/geo/1.0/direct"
            async with httpx.AsyncClient() as client:
                geo_resp = await client.get(
                    geo_url,
                    params={"q": f"{district},{state},IN", "limit": 1, "appid": settings.OPENWEATHER_API_KEY},
                    timeout=10
                )
                geo = geo_resp.json()
                if not geo:
                    logger.warning(f"[Weather] No geolocation found for {district}, {state}")
                    return "Weather data unavailable"

                lat, lon = geo[0]["lat"], geo[0]["lon"]
                logger.info(f"[Weather] Resolved to coordinates: lat={lat}, lon={lon}")

                forecast_resp = await client.get(
                    "https://api.openweathermap.org/data/2.5/forecast",
                    params={"lat": lat, "lon": lon, "appid": settings.OPENWEATHER_API_KEY,
                            "units": "metric", "cnt": 8},
                    timeout=10
                )
                forecast = forecast_resp.json()
                items = forecast.get("list", [])[:3]
                summaries = []
                for item in items:
                    dt = item["dt_txt"].split(" ")
                    desc = item["weather"][0]["description"]
                    temp = item["main"]["temp"]
                    rain = item.get("rain", {}).get("3h", 0)
                    humidity = item["main"]["humidity"]
                    summaries.append(f"{dt[0]} {dt[1]}: {desc}, {temp}°C, rain:{rain}mm, humidity:{humidity}%")
                return " | ".join(summaries)
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return "Moderate weather expected. Check IMD website (imd.gov.in) for exact forecast."
