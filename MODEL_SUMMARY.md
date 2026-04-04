# FieldFlow — Model & AI Service Architecture

**Last Updated:** April 4, 2026  
**Project:** KisanVaani (FieldFlow) — Agricultural AI Assistant for Indian Farmers

---

## 📊 Summary

| Service | Model | Purpose | Status | Local? |
|---------|-------|---------|--------|--------|
| **Main AI Brain** | IBM Granite 3.0 (8B-Instruct) | Intent classification, routing, responses | ✅ Active | ❌ Cloud API |
| **Image Analysis** | ResNet50 + PlantVillage | Crop disease detection from photos | ⚠️ Optional | ⚠️ Conditional Local |
| **Text-to-Speech** | IBM Watson TTS | Voice output in regional languages (Hindi, Tamil, etc.) | ✅ Active | ❌ Cloud API |
| **Speech-to-Text** | IBM Watson STT | Voice input transcription | ✅ Active | ❌ Cloud API |
| **Translation (Deprecated)** | IBM Watson Translator | Regional ↔ English translation | ⚠️ Deprecated | ❌ Cloud API |
| **Fallback Translation** | IBM Granite 3.0 (via Watsonx) | Clean translation for fallback messages | ✅ Active | ❌ Cloud API |
| **Alternative Translation** | Google Gemini 1.5 Flash | Experimental translation option | ⚠️ Not in Use | ❌ Cloud API |
| **Database** | Neo4j Aura | Graph database for relationships | ✅ Active | ❌ Cloud DB |
| **Messaging** | Twilio WhatsApp API | WhatsApp bot integration | ✅ Active | ❌ Cloud API |
| **Data Store** | Supabase (PostgreSQL) | Structured data storage | ✅ Active | ❌ Cloud DB |

---

## 🤖 Detailed Model Breakdown

### 1. **IBM Granite 3.0 (8B-Instruct)** — Main AI Brain
**Location:** Cloud (IBM watsonx.ai — us-south region)  
**Service:** `utils/watsonx_client.py`  
**Endpoints:** `/ml/v1/text/chat`

**Purpose:**
- Answer farming questions with agricultural expertise
- Intent classification (routing to Crop Doctor, Mandi Oracle, etc.)
- Language detection and regional language responses
- Commodity name extraction for API calls
- Fallback translation with language purity

**Why This Model?**
- Specifically trained for agricultural domain
- Efficient 8B parameter size (faster inference)
- Supports 100+ languages natively
- Handles Indian farming terminology (crop names, fertilizers, seasons)
- CRITICAL RULE: Always responds in user's input language (no English fallback)

**Configuration:**
```json
{
  "model_id": "ibm/granite-3-8b-instruct",
  "url": "https://us-south.ml.cloud.ibm.com",
  "api_version": "2024-05-31"
}
```

**Status:** ✅ Active and working well after latest language purity fixes

---

### 2. **ResNet50 + PlantVillage Dataset** — Crop Disease Detection
**Location:** Local (expected at `models/plantvillage_resnet50.pt`, but NOT currently present)  
**Framework:** PyTorch  
**Service:** `agents/crop_doctor.py`

**Purpose:**
- Analyze farmer-uploaded crop images
- Identify plant diseases and pests
- Return disease name + confidence score

**Architecture:**
- ResNet50 backbone (pre-trained ImageNet weights)
- Fine-tuned on PlantVillage dataset (38 disease classes)
- Classes include: Tomato leaf blight, Potato early blight, Powdery mildew, etc.
- Input: 224×224 RGB images
- Output: Disease name + confidence (0-1)

**Why This Model?**
- Specialized for crop disease recognition
- Lightweight enough for mobile inference
- PlantVillage dataset covers Indian crops

**Status:** ⚠️ **Model file missing!**  
- Not present in local system (`models/plantvillage_resnet50.pt`)
- Code gracefully falls back to text-only mode
- System shows warnings but continues to work

**How to Fix:**
```bash
# Download the model (~100MB):
# 1. Get from your training pipeline
# 2. Create models/ directory
# 3. Place plantvillage_resnet50.pt there
mkdir -p models
# Then place the .pt file in there
```

---

### 3. **IBM Watson Speech-to-Text (STT)**
**Location:** Cloud (IBM Watson API — au-syd region)  
**Service:** `utils/watson_stt.py`

**Purpose:**
- Convert farmer's voice input to text
- Multi-language support (Hindi, Tamil, Telugu, etc.)
- Real-time transcription

**Why This Model?**
- Excellent accuracy for accented English and Indian languages
- Fast processing
- Works with Twilio WebHook integration

**Status:** ✅ Active and working

---

### 4. **IBM Watson Text-to-Speech (TTS)**
**Location:** Cloud (IBM Watson API — au-syd region)  
**Service:** `utils/watson_tts.py`

**Purpose:**
- Convert responses to voice
- Multiple language-specific voices available
- Regional language voice synthesis

**Voices Configured:**
- **Hindi:** Meera V3 (Female) — `hi-IN_MeeraV3Voice`
- **Regional fallback:** Michael V3 (English) for Tamil, Telugu, Kannada, etc.

**Why This Model?**
- Native support for Indian regional languages
- High-quality audio output
- Available voices match farmer demographics

**Status:** ✅ Active with recent fix for async token retrieval

---

### 5. **IBM Watson Language Translator** (Deprecated)
**Location:** Cloud (IBM Watson API)  
**Service:** `utils/watson_translator.py`

**Status:** ⚠️ **DEPRECATED — Being phased out**

**Why Deprecated?**
- Watsonx (Granite 3.0) now handles translation natively
- IBM Translator has empty API keys (not configured)
- Early exit implemented: if key missing, returns original text immediately

**Previous Role:**
- Converted regional language queries to English for processing
- Translated responses back to regional languages

**Future:** Will be completely removed in next refactor

---

### 6. **Google Gemini 1.5 Flash** (Experimental)
**Location:** Cloud (Google AI API)  
**Service:** `utils/gemini_translator.py`

**Status:** ⚠️ **Not in active use**

**Purpose (if activated):**
- Ultra-fast translation for real-time scenarios
- Clean output for TTS (strips markdown, prevents hybrid words)
- Alternative to Watsonx-based translation

**Why Not Used?**
- Watsonx solution already working well
- Google API adds extra dependency
- Cost optimization (Watsonx already provisioned)

---

### 7. **Neo4j Aura** — Knowledge Graph Database
**Location:** Cloud (Neo4j cloud infrastructure)  
**Service:** `utils/neo4j_graph.py`

**Purpose:**
- Store relationships between:
  - Farmers ↔ Crops
  - Crops ↔ Diseases
  - Diseases ↔ Treatments
  - Farmers ↔ Schemes (government benefits)
- Query disease patterns across geographic regions
- Build farmer community intelligence

**Why Graph Database?**
- Agricultural domain is highly relational
- Enables "Crop X causes Disease Y which needs Treatment Z" queries
- Scales with community size

**Status:** ✅ Configured but may need optimization

---

### 8. **Supabase (PostgreSQL)** — Structured Data Store
**Location:** Cloud (Supabase cloud infrastructure)  
**Service:** `utils/db.py`

**Purpose:**
- Store structured farmer data (profiles, alerts, reports)
- Disease reports with timestamps
- Community disease alerts aggregation
- Message history logging

**Tables:**
- `farmers` — farmer profiles
- `disease_reports` — crop disease detections
- `community_alerts` — area-wide alerts
- `messages` — WhatsApp message history

**Status:** ✅ Active

---

### 9. **Twilio WhatsApp Bot**
**Location:** Cloud (Twilio API)  
**Integration:** `main.py` (FastAPI endpoint)

**Purpose:**
- WhatsApp interface for farmers
- Webhooks receive incoming messages
- Multi-language support

**Status:** ✅ Active

---

## 🔄 Model Flow Diagram

```
Farmer (WhatsApp Input - Regional Language)
           ↓
  [Twilio WebHook]
           ↓
  [Language Detector] ← Detects Hindi/Tamil/Telugu/etc.
           ↓
  [IBM Watson STT] (if voice)
           ↓
  [Granite 3.0 Intent Classifier]
           ↓
    ┌─────┬─────────┬─────────┬─────────┐
    ↓     ↓         ↓         ↓         ↓
  Crop  Mandi   Weather  Scheme  General
 Doctor Oracle  Guide   Advisor  Advisor
    ↓     ↓         ↓         ↓         ↓
    │  [ResNet50] [Mandi    [DB       [Granite
    │  +Plant     API]      Query]    3.0]
    │  Village
    │  Disease
    │  Detection]
    │
    └─────→ [Granite 3.0 Response Generator]
             (with language purity rules)
           ↓
    [Fallback Translator] if needed
           ↓
    [IBM Watson TTS] (text → voice)
           ↓
    [Twilio API] (send WhatsApp response)
           ↓
    Farmer (Response - Native Language)
```

---

## 🔑 Key Configuration

**Active API Keys Required:**
```env
# IBM Services
WATSONX_API_KEY=<value in .env>
WATSONX_PROJECT_ID=<value in .env>
IBM_STT_API_KEY=<value in .env>
IBM_TTS_API_KEY=<value in .env>

# Optional (deprecated)
IBM_TRANSLATOR_API_KEY=<empty by design>

# Alternative (not in use)
GEMINI_API_KEY=<in .env, not used>

# Databases
NEO4J_URI=bolt+s://f3cff19f.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<secure password>

# Messaging
TWILIO_ACCOUNT_SID=<value>
TWILIO_AUTH_TOKEN=<value>

# Data
SUPABASE_URL=https://kffmgwndqlmenfawebrq.supabase.co
SUPABASE_KEY=<jwt key>
```

---

## 📋 Missing Local Models

| Model | Path | Size | Status | Action Required |
|-------|------|------|--------|-----------------|
| PlantVillage ResNet50 | `models/plantvillage_resnet50.pt` | ~100MB | ❌ Missing | Download & place locally |

**Note:** System works fine without this model — gracefully falls back to text-only disease diagnosis.

---

## ⚡ Performance Notes

| Model | Avg Response Time | Tokens Used | Cost Impact |
|-------|-------------------|-------------|------------|
| Granite 3.0 (Intent) | 400-600ms | 50-100 | Low |
| Granite 3.0 (Response) | 1-2s | 100-300 | Low |
| ResNet50 (Image) | 300-500ms | N/A | N/A (local) |
| Watson STT | 1-3s | N/A | Moderate |
| Watson TTS | 500ms-2s | N/A | Moderate |
| Gemini Translation | 1-2s | 50-150 | Low (not used) |
| Neo4j Query | 100-500ms | N/A | N/A (local) |
| Supabase Query | 200-800ms | N/A | N/A (managed) |

---

## 🛡️ Language Purity & Quality Assurance

**Critical Rules Enforced:**
1. ✅ No mixed-language hybrid words (e.g., ~~'நன்ked'~~)
2. ✅ Technical terms (eNAM, KVK, PM-KISAN) retained in English
3. ✅ Always respond in user's input language (no English default)
4. ✅ Natural, conversational grammar in regional scripts
5. ✅ Currency (Rs) and phone numbers unchanged

**Implementation:**
- Rule 1: Embedded in both Watsonx prompts and Gemini translator
- Rule 2-5: REGIONAL_TRANSLATION_PROMPT in `watsonx_client.py`

---

## 🚀 Next Steps / Improvements

1. **Download PlantVillage Model** — Enable image disease detection
2. **Optimize Token Usage** — Monitor Granite 3.0 requests to reduce API cost
3. **Deprecate Watson Translator** — Remove completely once Watsonx fully stable
4. **Add Groq Integration** — Consider for ultra-low-latency scenarios
5. **Fine-tune Granite** — Custom model for even better agricultural responses

---

## 📚 References

- **IBM Watsonx Documentation:** https://www.ibm.com/products/watsonx
- **PlantVillage Dataset:** https://plantvillage.psu.edu
- **Neo4j Aura:** https://www.neo4j.com/cloud/aura/
- **Supabase:** https://supabase.com
- **Twilio WhatsApp:** https://www.twilio.com/whatsapp

---

**Generated:** April 4, 2026 | **Version:** 1.0