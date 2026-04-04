# IBM Cloud Code Engine Deployment
# Run these commands in order after installing IBM Cloud CLI
#
# INSTALL CLI: curl -fsSL https://clis.cloud.ibm.com/install/linux | sh
# LOGIN:       ibmcloud login --apikey YOUR_IBM_APIKEY -r us-south
# INSTALL CE:  ibmcloud plugin install code-engine

# ── Step 1: Create Code Engine project ──────────────────────
# ibmcloud ce project create --name kisanvaani

# ── Step 2: Select project ───────────────────────────────────
# ibmcloud ce project select --name kisanvaani

# ── Step 3: Create container registry secret ─────────────────
# (Skip if using public Docker Hub)
# ibmcloud ce registry create --name dockerhub --server docker.io \
#   --username YOUR_DOCKERHUB_USER --password YOUR_DOCKERHUB_TOKEN

# ── Step 4: Build and push Docker image ──────────────────────
# docker build -t YOUR_DOCKERHUB_USER/kisanvaani:latest .
# docker push YOUR_DOCKERHUB_USER/kisanvaani:latest

# ── Step 5: Create secrets from .env ─────────────────────────
# ibmcloud ce secret create --name kisanvaani-secrets \
#   --from-env-file .env

# ── Step 6: Deploy application ───────────────────────────────
# ibmcloud ce application create \
#   --name kisanvaani \
#   --image docker.io/YOUR_DOCKERHUB_USER/kisanvaani:latest \
#   --env-from-secret kisanvaani-secrets \
#   --port 8000 \
#   --min-scale 1 \
#   --max-scale 5 \
#   --cpu 0.5 \
#   --memory 2G

# ── Step 7: Get public URL ───────────────────────────────────
# ibmcloud ce application get --name kisanvaani
# Copy the URL — paste it as your Twilio webhook URL

# ── Step 8: Update Twilio webhook ────────────────────────────
# Go to console.twilio.com → Messaging → Sandbox Settings
# Set "When a message comes in" to:
# https://YOUR_CE_URL/webhook/whatsapp

# ── Redeploy after code changes ──────────────────────────────
# docker build -t YOUR_DOCKERHUB_USER/kisanvaani:latest . && \
# docker push YOUR_DOCKERHUB_USER/kisanvaani:latest && \
# ibmcloud ce application update --name kisanvaani \
#   --image docker.io/YOUR_DOCKERHUB_USER/kisanvaani:latest
