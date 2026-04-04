# 🌾 FieldFlow / KisanVaani — Project Structure

Complete directory structure and file organization for the FieldFlow agricultural AI assistant.

```
fieldflow/
│
├── 📄 Root Files
│   ├── main.py                      # Application entry point
│   ├── requirements.txt             # Python dependencies
│   ├── .env                         # Environment variables (secrets)
│   ├── .env.example                 # Template for .env configuration
│   ├── .gitignore                   # Git ignore patterns
│   ├── README.md                    # Project documentation & setup guide
│   ├── STRUCTURE.md                 # This file - project structure
│   ├── GEMINI_HANDOFF.txt          # Handoff notes/documentation
│   │
│   └── 🐳 Container Files
│       ├── Dockerfile              # Docker image definition
│       ├── docker-compose.yml      # Multi-container orchestration
│       └── deploy_ibm_cloud.sh    # IBM Cloud deployment script
│
├── 📁 config/
│   ├── __init__.py                 # Package marker
│   └── settings.py                 # Pydantic BaseSettings - environment configuration
│                                    # Loads all API keys and connection strings from .env
│
├── 📁 agents/                      # Core agent modules - LLM-powered decision makers
│   ├── __init__.py
│   │
│   ├── orchestrator.py             # Intent classifier & routing
│   │                                # Routes farmer queries to appropriate agents
│   │                                # Intents: crop_doctor, mandi, weather, scheme, community, general
│   │
│   ├── crop_doctor.py              # Crop disease diagnosis agent
│   │                                # Uses: image classification, plant pathology knowledge
│   │                                # Output: Disease name, cause, organic/chemical remedies, safety tips
│   │
│   ├── mandi_oracle.py             # Market price advisor & eNAM API integration
│   │                                # Uses: Agmarknet/data.gov.in API for live mandi prices
│   │                                # Output: Current prices, sell/wait recommendations
│   │
│   ├── vayu_guide.py               # Weather forecasting & irrigation advisor
│   │                                # Uses: IMD weather data integration
│   │                                # Output: Weather-based farming actions (spray, irrigate, sow)
│   │
│   ├── scheme_advisor.py           # Government scheme matcher
│   │                                # Matches farmers to eligible schemes (PM-KISAN, PMFBY, etc.)
│   │                                # Output: Scheme names, benefits, application process
│   │
│   ├── general_advisor.py          # Fallback agent for general farming advice
│   │                                # Handles greetings, unclear queries, general guidance
│   │
│   └── community_intel.py          # Disease surveillance & community alerts
│                                    # Alerts about regional crop disease outbreaks
│
├── 📁 utils/                       # Utility modules & external integrations
│   ├── __init__.py
│   │
│   ├── watsonx_client.py           # IBM Watsonx.ai LLM client
│   │                                # Model: ibm/granite-3-8b-instruct
│   │                                # Methods: generate(), translate_fallback_message()
│   │                                # Handles token caching & fallback responses
│   │
│   ├── watson_stt.py               # IBM Watson Speech-to-Text
│   │                                # Converts farmer voice (WhatsApp/SMS) → text
│   │                                # Supports Indian language accents
│   │
│   ├── watson_tts.py               # IBM Watson Text-to-Speech
│   │                                # Converts advisor responses → audio in regional languages
│   │                                # Voices: Hindi (Meera), English (Michael), with fallbacks
│   │
│   ├── watson_translator.py        # IBM Watson Language Translator
│   │                                # Bidirectional: Regional ↔ English
│   │                                # [DEPRECATED] Functionality moved to Watsonx native translation
│   │
│   ├── language_detector.py        # Unicode script-based language detection
│   │                                # Detects: Hindi, Tamil, Telugu, Marathi, Kannada, Bengali, Gujarati, Punjabi
│   │                                # Uses: Devanagari, Tamil, Telugu scripts analysis
│   │
│   ├── twilio_handler.py           # Twilio WhatsApp integrations
│   │                                # Routes incoming WhatsApp messages
│   │
│   ├── neo4j_graph.py              # Neo4j knowledge graph
│   │                                # Stores: disease relationships, crop-scheme mappings, market data
│   │
│   ├── db.py                       # Supabase database operations
│   │                                # Tables: farmers, reports, disease_history, scheme_eligibility
│   │
│   └── prompts.py                  # [If exists] System prompt definitions
│                                    # Now integrated into individual agent files
│
├── 📁 tests/
│   ├── __init__.py
│   └── test_kisanvaani.py          # Unit tests for core functionality
│
└── 📁 __pycache__/                 # Python bytecode cache (auto-generated)
    └── *.pyc

```

## 🔑 Key Files Overview

### Configuration
- **config/settings.py**: Pydantic BaseSettings model - loads all credentials from .env
  - Neo4j, Supabase, IBM Watson services, Watsonx, Twilio, weather, market APIs

### LLM Agents
- **agents/orchestrator.py**: Intent classifier - routes to correct agent
- **agents/crop_doctor.py**: Plant disease diagnosis expert
- **agents/mandi_oracle.py**: Market price advisor with Agmarknet integration
- **agents/vayu_guide.py**: Weather-based farming guidance
- **agents/scheme_advisor.py**: Government scheme matcher
- **agents/general_advisor.py**: Fallback for general advice

### AI/ML Services
- **utils/watsonx_client.py**: Granite 3.0 LLM client (primary AI engine)
- **utils/watson_stt.py**: Speech recognition (Twitter → text)
- **utils/watson_tts.py**: Text-to-speech (response → audio)
- **utils/language_detector.py**: Language detection from Unicode scripts

### Integrations
- **utils/twilio_handler.py**: WhatsApp messaging interface
- **utils/db.py**: Supabase database operations
- **utils/neo4j_graph.py**: Knowledge graph storage

### Entry Point
- **main.py**: FastAPI/Async application startup

---

## 📊 Data Flow

```
Farmer Input (WhatsApp/Voice)
    ↓
Twilio (twilio_handler.py)
    ↓
Language Detection (language_detector.py)
    ↓
Speech-to-Text if voice (watson_stt.py)
    ↓
Intent Classification (orchestrator.py)
    ↓
Route to Agent → Generate response
    ├─ crop_doctor.py
    ├─ mandi_oracle.py
    ├─ vayu_guide.py
    ├─ scheme_advisor.py
    ├─ community_intel.py
    └─ general_advisor.py
    ↓
Response Generation (watsonx_client.py)
    ↓
Language Translation if needed
    ↓
Text-to-Speech if voice (watson_tts.py)
    ↓
Send via Twilio WhatsApp
```

---

## 🗄️ External Services

| Service | Type | Purpose | File |
|---------|------|---------|------|
| IBM Watsonx.ai | LLM | Response generation (Granite 3.0) | watsonx_client.py |
| IBM Watson STT | Speech Recognition | Voice → Text | watson_stt.py |
| IBM Watson TTS | Speech Synthesis | Text → Voice | watson_tts.py |
| IBM Watson Translator | Translation | [Deprecated] Regional ↔ English | watson_translator.py |
| Twilio | Messaging | WhatsApp integration | twilio_handler.py |
| Neo4j Aura | Graph DB | Knowledge graph | neo4j_graph.py |
| Supabase | SQL Database | Farmer profiles, reports | db.py |
| Agmarknet/data.gov.in | API | Mandi prices | mandi_oracle.py |
| IMD/Weather API | API | Weather forecast | vayu_guide.py |

---

## 🎯 Intent Classification

The orchestrator routes queries to agents based on intent:

| Intent | Agent | Trigger Keywords |
|--------|-------|-----------------|
| crop_doctor | crop_doctor.py | disease, pest, yellowing, spots, rot, insect, blight |
| mandi | mandi_oracle.py | price, bhav, rate, sell, market, மணி |
| weather | vayu_guide.py | rain, irrigation, spraying, baarish, आँधी |
| scheme | scheme_advisor.py | scheme, subsidy, loan, PM-KISAN, योजना |
| community | community_intel.py | nearby farmers, area, others facing, आसपास |
| general | general_advisor.py | greeting, thanks, other advice |

---

## 🌐 Supported Languages

- Hindi (हिंदी) - hi
- Tamil (தமிழ்) - ta  
- Telugu (తెలుగు) - te
- Marathi (मराठी) - mr
- Kannada (ಕನ್ನಡ) - kn
- Bengali (বাংলা) - bn
- Gujarati (ગુજરાતી) - gu
- Punjabi (ਪੰਜਾਬੀ) - pa
- English - en

---

## 📋 Environment Variables (.env)

```
# IBM Watson Services
IBM_STT_API_KEY=...
IBM_TTS_API_KEY=...

# IBM Watsonx.ai
WATSONX_API_KEY=...
WATSONX_TOKEN=...
WATSONX_PROJECT_ID=...

# Twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...

# Neo4j
NEO4J_URI=...
NEO4J_USERNAME=...
NEO4J_PASSWORD=...

# Supabase
SUPABASE_URL=...
SUPABASE_KEY=...

# APIs
OPENWEATHER_API_KEY=...
AGMARKNET_API_KEY=...

# App
APP_ENV=development
LOG_LEVEL=INFO
```

---

## 🚀 Deployment

- **Docker**: Dockerfile + docker-compose.yml for containerization
- **IBM Cloud**: deploy_ibm_cloud.sh for cloud deployment
- **Local**: `python main.py` to run locally

