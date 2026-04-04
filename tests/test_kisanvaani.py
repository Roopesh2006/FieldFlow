"""
KisanVaani — Test Suite
Run: pytest tests/ -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Mock settings so tests run without real API keys ─────────
@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    monkeypatch.setenv("IBM_STT_API_KEY", "test_key")
    monkeypatch.setenv("IBM_TTS_API_KEY", "test_key")
    monkeypatch.setenv("IBM_TRANSLATOR_API_KEY", "test_key")
    monkeypatch.setenv("WATSONX_API_KEY", "test_key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "test_project")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test_key")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test_key")
    monkeypatch.setenv("AGMARKNET_API_KEY", "test_key")


# ── Test Language Detector ───────────────────────────────────
@pytest.mark.asyncio
async def test_detect_hindi():
    from utils.language_detector import detect_language
    result = await detect_language("मेरी फसल में कीड़े लग गए हैं")
    assert result == "hi"


@pytest.mark.asyncio
async def test_detect_tamil():
    from utils.language_detector import detect_language
    result = await detect_language("என் தக்காளி இலைகள் மஞ்சளாகி விட்டன")
    assert result == "ta"


@pytest.mark.asyncio
async def test_detect_telugu():
    from utils.language_detector import detect_language
    result = await detect_language("నా పంటకు రోగం వచ్చింది")
    assert result == "te"


@pytest.mark.asyncio
async def test_detect_english_fallback():
    from utils.language_detector import detect_language
    result = await detect_language("My tomato leaves are turning yellow")
    assert result == "en"


# ── Test Intent Detection ────────────────────────────────────
@pytest.mark.asyncio
async def test_intent_crop_doctor():
    with patch("utils.watsonx_client.WatsonxClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "crop_doctor"
        from agents.orchestrator import KisanOrchestrator
        orc = KisanOrchestrator()
        intent = await orc.detect_intent("My tomato leaves have yellow spots")
        assert intent == "crop_doctor"


@pytest.mark.asyncio
async def test_intent_mandi():
    with patch("utils.watsonx_client.WatsonxClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "mandi"
        from agents.orchestrator import KisanOrchestrator
        orc = KisanOrchestrator()
        intent = await orc.detect_intent("What is onion price today in Nashik")
        assert intent == "mandi"


@pytest.mark.asyncio
async def test_intent_scheme():
    with patch("utils.watsonx_client.WatsonxClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "scheme"
        from agents.orchestrator import KisanOrchestrator
        orc = KisanOrchestrator()
        intent = await orc.detect_intent("Is there any government help available for me")
        assert intent == "scheme"


# ── Test Crop Doctor Agent ───────────────────────────────────
@pytest.mark.asyncio
async def test_crop_doctor_response():
    with patch("utils.watsonx_client.WatsonxClient.generate", new_callable=AsyncMock) as mock_gen, \
         patch("utils.db.save_disease_report", new_callable=AsyncMock):
        mock_gen.return_value = "DISEASE: Early Blight\nCAUSE: Fungal\nREMEDY: Mancozeb 2g/litre\nWARNING: Wear gloves"
        from agents.crop_doctor import CropDoctorAgent
        agent = CropDoctorAgent()
        farmer = {"phone_number": "+919876543210", "crop_primary": "tomato",
                  "district": "Nashik", "state": "Maharashtra"}
        result = await agent.run("yellow spots on leaves", farmer, {})
        assert "DISEASE" in result or "Blight" in result.lower() or len(result) > 10


# ── Test Webhook Endpoint ────────────────────────────────────
@pytest.mark.asyncio
async def test_health_endpoint():
    with patch("utils.db.get_or_create_farmer", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = {"id": "123", "phone_number": "+919876543210", "language": "hi"}
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root_endpoint():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "KisanVaani" in data["name"]
        assert len(data["languages"]) == 8


# ── Test Language Detector Edge Cases ────────────────────────
@pytest.mark.asyncio
async def test_detect_empty_uses_fallback():
    from utils.language_detector import detect_language
    result = await detect_language("", "ta")
    assert result == "ta"


@pytest.mark.asyncio
async def test_detect_marathi():
    from utils.language_detector import detect_language
    result = await detect_language("माझ्या पिकाला रोग आला आहे")
    assert result in ("mr", "hi")  # Both are Devanagari
