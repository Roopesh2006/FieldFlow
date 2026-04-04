# 🌾 KisanVaani — Setup Guide

## What You Need to Do (35 minutes total)

---

## Step 1 — Clone & Install (5 min)

```bash
git clone https://github.com/YOUR_USERNAME/kisanvaani.git
cd kisanvaani
pip install -r requirements.txt
cp .env.example .env
```

---

## Step 2 — IBM Cloud Setup (10 min)

1. Go to **cloud.ibm.com** → Sign up (free)
2. Click **"Create resource"** → search each service below:

### Speech to Text
- Create → Lite plan → Click the service → **Credentials** tab
- Copy `apikey` and `url` → paste into `.env` as `IBM_STT_API_KEY` and `IBM_STT_URL`

### Text to Speech
- Same steps → paste as `IBM_TTS_API_KEY` and `IBM_TTS_URL`

### Language Translator
- Same steps → paste as `IBM_TRANSLATOR_API_KEY` and `IBM_TRANSLATOR_URL`

---

## Step 3 — watsonx.ai Setup (5 min)

1. Go to **dataplatform.cloud.ibm.com** → Create account
2. Click **"New project"** → name it "KisanVaani" → Create
3. Go to **Settings** tab → copy **Project ID** → paste as `WATSONX_PROJECT_ID`
4. Go to **cloud.ibm.com → Manage → Access (IAM) → API keys** → Create → copy
5. Paste as `WATSONX_API_KEY`

---

## Step 4 — Twilio WhatsApp Sandbox (5 min)

1. Go to **twilio.com** → Sign up → verify your number
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Follow instructions to join sandbox (send a WhatsApp to +1 415 523 8886)
4. Copy **Account SID** and **Auth Token** from console home page
5. Paste into `.env`

---

## Step 5 — Supabase Keys (2 min)

1. Go to **supabase.com/dashboard/project/kffmgwndqlmenfawebrq/settings/api**
   *(Your DB is already set up — tables and data already exist!)*
2. Copy **Project URL** → paste as `SUPABASE_URL`
3. Copy **anon public key** → paste as `SUPABASE_KEY`

---

## Step 6 — OpenWeatherMap (2 min)

1. Go to **openweathermap.org/api** → Sign up
2. Go to **API Keys** tab → copy the default key
3. Paste as `OPENWEATHER_API_KEY`

---

## Step 7 — Neo4j Aura Free (3 min)

1. Go to **neo4j.com/cloud/aura-free** → Sign up
2. Create a free database → wait ~1 min
3. Copy the **Connection URI** (starts with `neo4j+s://`)
4. Copy the **Password** shown once (save it!)
5. Paste into `.env` as `NEO4J_URI` and `NEO4J_PASSWORD`

---

## Step 8 — Run the App (1 min)

```bash
# Seed Neo4j with demo data (run once)
python utils/neo4j_graph.py

# Start the server
uvicorn main:app --reload --port 8000
```

Open browser: **http://localhost:8000** — you should see KisanVaani running!

---

## Step 9 — Connect Twilio Webhook

1. Install ngrok: **ngrok.com/download**
2. Run: `ngrok http 8000`
3. Copy the `https://xxxx.ngrok.io` URL
4. Go to Twilio console → **Messaging → Sandbox Settings**
5. Set "When a message comes in" to: `https://xxxx.ngrok.io/webhook/whatsapp`
6. Save

**Send a WhatsApp message to your Twilio sandbox number — KisanVaani will reply!** 🎉

---

## Step 10 — Deploy to IBM Cloud (for submission)

```bash
# Follow instructions in deploy_ibm_cloud.sh
# Takes ~10 minutes
bash deploy_ibm_cloud.sh
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Demo Scenarios (For Jury)

### Demo 1 — Crop Disease (Hindi voice)
Send voice note: *"Mere tamatar ke patte peele pad rahe hain aur uspe kale dhabbey hain"*
Expected: Disease diagnosis + spray advice in Hindi voice

### Demo 2 — Community Alert (Tamil text)
Send: *"என் பகுதியில் என்ன நோய் பரவுகிறது?"*
Expected: Community disease alerts for that area in Tamil

### Demo 3 — Government Schemes (Telugu)
Send: *"నాకు ఏ ప్రభుత్వ పథకాలు వర్తిస్తాయి?"*
Expected: Matched schemes for Telangana farmer

### Demo 4 — Price Advisory (Marathi)
Send: *"आज कांद्याचा भाव काय आहे नाशिकला?"*
Expected: Live mandi price + sell/hold recommendation

---

## Architecture Quick Reference

```
WhatsApp → Twilio Webhook → FastAPI
→ Watson STT (voice→text)
→ Watson Translator (regional→English)
→ watsonx.ai Intent Detection
→ Agent Router → [Crop Doctor | Mandi | Weather | Scheme | Community | General]
→ Supabase (farmer memory, disease logs)
→ Neo4j (community spread patterns)
→ Watson Translator (English→regional)
→ Watson TTS (text→voice)
→ WhatsApp Reply to Farmer
```

## Support
KVK Helpline: 1800-180-1551 (free)
IBM Support: cloud.ibm.com/unifiedsupport
