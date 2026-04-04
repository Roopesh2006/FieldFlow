"""
FieldFlow — Crop Doctor Agent
FIX: extract_crop_from_query now gracefully returns 'Unknown' instead of None
FIX: All DB calls pass safe non-null crop value
FIX: classify_image updated for PyTorch
"""

import httpx
import logging
from typing import Optional, Tuple
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
    from utils.db import save_disease_report
except ImportError:
    from fieldflow.utils.db import save_disease_report

logger = logging.getLogger(__name__)

CROP_DOCTOR_PROMPT = """You are an expert plant pathologist for Indian agriculture.
Diagnose the crop problem from the farmer's description and give treatment advice.

RULES:
- First line MUST be: DISEASE: [exact disease name or 'Unknown']
- Second line MUST be: CROP: [crop name mentioned, or 'Unknown' if not mentioned]
- Third line: CAUSE: [brief one-line cause]
- Fourth line: REMEDY: [organic option first, then chemical with exact product name and dosage]
- Fifth line: WARNING: [one safety tip]
- Keep total response under 100 words
- Always end with: "Spray early morning or evening only."

If farmer just says "my plant" without naming the crop, use CROP: Unknown.
If you cannot diagnose, say DISEASE: Possible fungal infection and give general fungicide advice.

CRITICAL: Generate response ENTIRELY IN ENGLISH. No regional language, no markdown, no emojis, no # headers. Translation will be handled by Gemini Translator after generation."""


# Common Indian crops for extraction
CROP_KEYWORDS = [
    "tomato", "tamatar", "टमाटर",
    "onion", "pyaaz", "प्याज",
    "potato", "aloo", "आलू",
    "rice", "paddy", "dhan", "धान", "चावल",
    "wheat", "gehun", "गेहूं",
    "cotton", "kapas", "कपास",
    "sugarcane", "ganna", "गन्ना",
    "maize", "corn", "makka", "मक्का",
    "chilli", "mirch", "मिर्च",
    "groundnut", "moongfali", "मूंगफली",
    "soybean", "soyabean",
    "banana", "kela", "केला",
    "mango", "aam", "आम",
    "brinjal", "baingan", "बैंगन",
    "cauliflower", "gobhi", "गोभी",
    "cabbage",
    "cucumber", "kheera", "खीरा",
    "spinach", "palak", "पालक",
    "garlic", "lahsun", "लहसुन",
    "ginger", "adrak", "अदरक",
    "turmeric", "haldi", "हल्दी",
    "mustard", "sarson", "सरसों",
    "lentil", "dal", "masoor",
]


def extract_crop_from_query(query: str, farmer_crop: Optional[str] = None) -> str:
    """
    FIX (Bug 3): Extract crop from query text.
    Returns farmer's registered crop, or crop found in query, or 'Unknown'.
    NEVER returns None or empty string — prevents 23502 DB constraint error.
    """
    if not query:
        return farmer_crop or "Unknown"

    query_lower = query.lower()

    # Check query text for crop keywords
    for keyword in CROP_KEYWORDS:
        if keyword.lower() in query_lower:
            # Normalize to English name
            crop_map = {
                "tamatar": "tomato", "टमाटर": "tomato",
                "pyaaz": "onion", "प्याज": "onion",
                "aloo": "potato", "आलू": "potato",
                "dhan": "rice", "धान": "rice", "paddy": "rice", "चावल": "rice",
                "gehun": "wheat", "गेहूं": "wheat",
                "kapas": "cotton", "कपास": "cotton",
                "ganna": "sugarcane", "गन्ना": "sugarcane",
                "makka": "maize", "मक्का": "maize", "corn": "maize",
                "mirch": "chilli", "मिर्च": "chilli",
                "moongfali": "groundnut", "मूंगफली": "groundnut",
                "kela": "banana", "केला": "banana",
                "aam": "mango", "आम": "mango",
                "baingan": "brinjal", "बैंगन": "brinjal",
                "gobhi": "cauliflower", "गोभी": "cauliflower",
                "kheera": "cucumber", "खीरा": "cucumber",
                "palak": "spinach", "पालक": "spinach",
                "lahsun": "garlic", "लहसुन": "garlic",
                "adrak": "ginger", "अदरक": "ginger",
                "haldi": "turmeric", "हल्दी": "turmeric",
                "sarson": "mustard", "सरसों": "mustard",
                "masoor": "lentil",
            }
            return crop_map.get(keyword.lower(), keyword)

    # Fall back to farmer's registered crop
    if farmer_crop and farmer_crop.strip():
        return farmer_crop.strip()

    # Last resort — never return None
    return "Unknown"


def extract_crop_from_response(response: str) -> str:
    """Extract crop name from AI response CROP: line"""
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("CROP:"):
            crop = line[5:].strip()
            return crop if crop and crop.lower() != "unknown" else "Unknown"
    return "Unknown"


def extract_disease_from_response(response: str) -> str:
    """Extract disease name from AI response DISEASE: line"""
    for line in response.split("\n"):
        line = line.strip()
        if line.upper().startswith("DISEASE:"):
            disease = line[8:].strip()
            return disease if disease else "Unknown"
    return "Unknown"


# PlantVillage disease classes
PLANT_VILLAGE_CLASSES = [
    "Apple scab", "Apple black rot", "Apple cedar rust", "Apple healthy",
    "Blueberry healthy", "Cherry powdery mildew", "Cherry healthy",
    "Corn gray leaf spot", "Corn common rust", "Corn northern blight", "Corn healthy",
    "Grape black rot", "Grape esca", "Grape leaf blight", "Grape healthy",
    "Orange citrus greening", "Peach bacterial spot", "Peach healthy",
    "Pepper bacterial spot", "Pepper healthy",
    "Potato early blight", "Potato late blight", "Potato healthy",
    "Raspberry healthy", "Soybean healthy", "Squash powdery mildew",
    "Strawberry leaf scorch", "Strawberry healthy",
    "Tomato bacterial spot", "Tomato early blight", "Tomato late blight",
    "Tomato leaf mold", "Tomato septoria leaf spot",
    "Tomato spider mites", "Tomato target spot",
    "Tomato yellow leaf curl", "Tomato mosaic virus", "Tomato healthy"
]

_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        import torch, torchvision.models as models, os
        model_path = "models/plantvillage_resnet50.pt"
        if os.path.exists(model_path):
            model = models.resnet50(weights=None)
            model.fc = torch.nn.Linear(model.fc.in_features, len(PLANT_VILLAGE_CLASSES))
            model.load_state_dict(torch.load(model_path, map_location="cpu"))
            model.eval()
            _model = model
            logger.info("PlantVillage model loaded")
            return model
    except Exception as e:
        logger.warning(f"Model not loaded (text-only mode): {e}")
    return None


async def classify_image(image_url: str) -> Tuple[str, float]:
    """Classify disease from image using PyTorch ResNet50"""
    try:
        import torch
        from torchvision import transforms
        from PIL import Image
        import io

        model = _load_model()
        if model is None:
            return "Unknown", 0.5

        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                image_url,
                timeout=15
            )
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")

        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        img_tensor: torch.Tensor = transform(img)  # type: ignore  # PIL Image -> Tensor
        tensor = img_tensor.unsqueeze(0)  # Add batch dimension
        with torch.no_grad():
            outputs = model(tensor)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            confidence, predicted = torch.max(probs, 1)
            class_idx = int(predicted[0].item())
            conf_score = float(confidence[0].item())

        disease = PLANT_VILLAGE_CLASSES[class_idx]
        conf = round(conf_score, 2)
        return disease, conf

    except Exception as e:
        logger.error(f"Image classification error: {e}")
        return "Unknown", 0.5


class CropDoctorAgent:
    def __init__(self):
        self.watsonx = WatsonxClient()
        self.translator = GeminiTranslator()

    async def run(
        self,
        query: str,
        farmer: dict,
        memory: dict,
        image_url: Optional[str] = None
    ) -> str:
        # ── Detect user language ─────────────────────────────────────────
        user_language = await detect_language(query, fallback=farmer.get("language", "hi"))
        
        # ── Extract crop safely ──────────────────────────────────────────
        # FIX: use extract_crop_from_query which NEVER returns None
        crop = extract_crop_from_query(query, farmer.get("crop_primary"))
        # crop is now always a non-empty string

        past_diseases = memory.get("past_diseases", [])
        past_context = ""
        if past_diseases:
            names = [d["disease_name"] for d in past_diseases if d.get("disease_name")]
            if names:
                past_context = f"This farmer previously had: {', '.join(names)}. "

        image_context = ""
        if image_url:
            detected_disease, confidence = await classify_image(image_url)
            if detected_disease != "Unknown":
                image_context = f"\nImage analysis detected: {detected_disease} (confidence: {confidence:.0%})."

        full_query = (
            f"Farmer grows {crop} in {farmer.get('district', 'India')}, "
            f"{farmer.get('state', '')}.\n"
            f"{past_context}"
            f"Farmer's complaint: {query}\n"
            f"{image_context}"
        )

        response = await self.watsonx.generate(
            system_prompt=CROP_DOCTOR_PROMPT,
            user_message=full_query,
            max_tokens=250,
            temperature=0.2
        )

        # ── Save to DB — all values null-safe ───────────────────────────
        if farmer.get("phone_number"):
            # Try to get crop from AI response first, fall back to extracted crop
            ai_crop = extract_crop_from_response(response)
            final_crop = ai_crop if ai_crop != "Unknown" else crop
            disease_name = extract_disease_from_response(response)

            await save_disease_report(  # type: ignore
                phone_number=farmer["phone_number"],
                farmer_id=farmer.get("id"),
                crop=final_crop,         # always a string, never None
                disease_name=disease_name,
                confidence=0.75,
                symptoms=query or None,
                remedy=response,
                district=farmer.get("district", "") or "",
                state=farmer.get("state", "") or ""
            )

        # ── Translate & clean for voice output ───────────────────────────
        if user_language != "en":
            response = self.translator.translate_and_clean(response, user_language)
        
        return response
