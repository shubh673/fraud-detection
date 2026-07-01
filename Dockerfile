# =============================================================================
# Multi-stage build for the Card & Payment Fraud Detection POC.
#
#   Stage 1 (pipeline) : run the Python pipeline -> generates dashboard JSON
#   Stage 2 (frontend) : build the React dashboard (bundles the JSON)
#   Stage 3 (nginx)    : serve the static site under /fraud-detection/ on :8080
#
# The final image is small (nginx + built static files). The heavy model
# (~330 MB) and datasets stay in the build stages only.
#
# Deployed behind the host nginx on ai.arttechgroup.com:7777, which proxies
# /fraud-detection/ to this container. See NGINX-DEPLOY-GUIDE.md.
# =============================================================================

# ---- Stage 1: Python pipeline ----------------------------------------------
FROM python:3.12-slim AS pipeline
WORKDIR /app

# scikit-learn / pandas ship manylinux wheels, so no build tools are needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Code + inputs the pipeline reads
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY fraud_detection_enriched_dataset_pack/ ./fraud_detection_enriched_dataset_pack/

# Run the three stages in order (train -> detectors -> dashboard data).
RUN python src/train_step1_model.py \
 && python src/client_requirement_pipeline.py \
 && python scripts/prepare_dashboard_data.py

# ---- Stage 2: build the React dashboard ------------------------------------
FROM node:20-slim AS frontend
WORKDIR /app/frontend

# Install deps first (better layer caching). Use `npm install` rather than
# `npm ci` so a package-lock.json generated on another platform (e.g. Windows)
# still builds here — Tailwind v4 pulls in platform-specific optional deps that
# a cross-platform lock file may not fully capture.
COPY frontend/package*.json ./
RUN npm install

# App source, then overlay the pipeline-generated data before building.
# Vite base (/fraud-detection/) is set in frontend/vite.config.ts.
COPY frontend/ ./
COPY --from=pipeline /app/frontend/public/data ./public/data
RUN npm run build

# ---- Stage 3: serve with nginx ---------------------------------------------
FROM nginx:alpine AS serve
# Serve the SPA under the /fraud-detection/ base path (matches Vite base + the
# host nginx prefix). try_files in nginx.conf resolves paths from this subdir.
COPY --from=frontend /app/frontend/dist /usr/share/nginx/html/fraud-detection
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
