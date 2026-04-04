"""
KisanVaani / FieldFlow Database Utilities
Supabase (PostgreSQL) interface

FIX: save_disease_report now sanitizes crop — never passes None/empty to DB
FIX: All inserts have null-safe defaults
"""

import logging
from typing import Optional, Dict, List
from supabase import create_client, Client
try:
    from config.settings import settings
except ImportError:
    from fieldflow.config.settings import settings
from datetime import datetime

logger = logging.getLogger(__name__)

_supabase: Optional[Client] = None


def get_db() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase


def _clean_phone(phone_number: str) -> str:
    """Normalize phone number — strip whatsapp: prefix"""
    return phone_number.replace("whatsapp:", "").strip()


async def get_or_create_farmer(phone_number: str) -> Dict:
    """Get existing farmer or create new profile"""
    db = get_db()
    clean_phone = _clean_phone(phone_number)

    try:
        result = db.table("farmers").select("*").eq("phone_number", clean_phone).single().execute()
        if result.data:
            return result.data
    except Exception:
        pass  # Not found — create below

    try:
        result = db.table("farmers").insert({
            "phone_number": clean_phone,
            "language": "hi",
        }).execute()
        return result.data[0] if result.data else {"phone_number": clean_phone}
    except Exception as e:
        logger.error(f"DB error creating farmer: {e}")
        return {"phone_number": clean_phone}


async def update_farmer_language(phone_number: str, language: str):
    db = get_db()
    clean_phone = _clean_phone(phone_number)
    try:
        db.table("farmers").update({
            "language": language,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("phone_number", clean_phone).execute()
    except Exception as e:
        logger.error(f"Error updating language: {e}")


async def log_message(
    phone_number: str,
    farmer_id: Optional[str],
    direction: str,
    message_type: str,
    content: str = "",
    media_url: str = "",
    intent: str = "",
    language_detected: str = "",
    response_time_ms: int = 0
):
    """Log every message interaction"""
    db = get_db()
    clean_phone = _clean_phone(phone_number)
    try:
        db.table("message_logs").insert({
            "phone_number": clean_phone,
            "farmer_id": farmer_id,
            "direction": direction,
            "message_type": message_type,
            "content": (content or "")[:2000],
            "media_url": media_url or "",
            "intent": intent or "",
            "language_detected": language_detected or "",
            "response_time_ms": response_time_ms
        }).execute()
    except Exception as e:
        logger.error(f"Error logging message: {e}")


async def save_disease_report(
    phone_number: str,
    farmer_id: Optional[str],
    crop: Optional[str],
    disease_name: Optional[str],
    confidence: float,
    symptoms: Optional[str],
    remedy: str,
    district: str = "",
    state: str = ""
) -> None:
    """
    Save crop disease detection to DB + update community alerts.

    FIX (Bug 2): crop is sanitized — None/empty → 'Unknown'
    This prevents: null value in column "crop" violates not-null constraint
    """
    db = get_db()
    clean_phone = _clean_phone(phone_number)

    # ── CRITICAL NULL SAFETY ─────────────────────────────────────────────
    # Never let None/empty reach the NOT NULL column
    safe_crop = (crop or "").strip() or "Unknown"
    safe_disease = (disease_name or "").strip() or "Unknown"
    safe_symptoms = (symptoms or "").strip() or None  # symptoms IS nullable

    try:
        db.table("disease_reports").insert({
            "phone_number": clean_phone,
            "farmer_id": farmer_id,
            "crop": safe_crop,                    # always a string now
            "disease_name": safe_disease,
            "disease_confidence": round(confidence, 2),
            "symptoms_described": safe_symptoms,
            "remedy_given": remedy[:2000] if remedy else "",
            "district": district or "",
            "state": state or ""
        }).execute()
        logger.info(f"Disease report saved: {safe_crop} / {safe_disease}")
    except Exception as e:
        logger.error(f"Error saving disease report: {e}")

    # Update community alerts aggregation
    if district and safe_disease and safe_disease != "Unknown":
        try:
            existing = db.table("community_alerts")\
                .select("*")\
                .eq("district", district)\
                .eq("crop", safe_crop)\
                .eq("disease_name", safe_disease)\
                .eq("is_active", True)\
                .execute()

            if existing.data:
                alert = existing.data[0]
                new_count = alert["report_count"] + 1
                severity = "low"
                if new_count >= 20: severity = "critical"
                elif new_count >= 10: severity = "high"
                elif new_count >= 5: severity = "medium"

                db.table("community_alerts").update({
                    "report_count": new_count,
                    "severity": severity,
                    "last_reported_at": datetime.utcnow().isoformat()
                }).eq("id", alert["id"]).execute()
            else:
                db.table("community_alerts").insert({
                    "district": district,
                    "state": state or "",
                    "crop": safe_crop,
                    "disease_name": safe_disease,
                    "report_count": 1,
                    "severity": "low"
                }).execute()
        except Exception as e:
            logger.error(f"Error updating community alert: {e}")


async def get_community_alerts(district: str, state: str) -> List:
    """Get active disease alerts for a district/state"""
    db = get_db()
    try:
        result = db.table("community_alerts")\
            .select("*")\
            .eq("is_active", True)\
            .or_(f"district.eq.{district},state.eq.{state}")\
            .order("report_count", desc=True)\
            .limit(5)\
            .execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Error fetching community alerts: {e}")
        return []


async def get_farmer_context(phone_number: str) -> Dict:
    """Get farmer's history for AI context injection"""
    db = get_db()
    clean_phone = _clean_phone(phone_number)
    context: Dict = {}

    try:
        diseases = db.table("disease_reports")\
            .select("crop, disease_name, created_at")\
            .eq("phone_number", clean_phone)\
            .order("created_at", desc=True)\
            .limit(3)\
            .execute()
        context["past_diseases"] = diseases.data or []

        mandi = db.table("mandi_queries")\
            .select("crop, price_modal, created_at")\
            .eq("phone_number", clean_phone)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        context["last_mandi_query"] = mandi.data[0] if mandi.data else None
    except Exception as e:
        logger.error(f"Error fetching farmer context: {e}")

    return context


async def match_schemes(farmer: Dict) -> List:
    """Match farmer profile to eligible government schemes"""
    db = get_db()
    try:
        state = farmer.get("state", "") or ""
        land = float(farmer.get("land_holding_acres") or 5.0)
        income = int(farmer.get("income_annual_inr") or 200000)

        result = db.table("govt_schemes")\
            .select("*")\
            .eq("is_active", True)\
            .or_(f"state_applicable.eq.ALL,state_applicable.eq.{state}")\
            .execute()

        schemes = result.data or []
        matched = []
        for s in schemes:
            if s.get("eligibility_land_max_acres") and land > float(s["eligibility_land_max_acres"]):
                continue
            if s.get("eligibility_income_max_inr") and income > int(s["eligibility_income_max_inr"]):
                continue
            matched.append(s)

        return matched[:5]
    except Exception as e:
        logger.error(f"Error matching schemes: {e}")
        return []
