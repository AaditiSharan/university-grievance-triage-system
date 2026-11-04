# Stage 1: Build the React + Vite frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + static file hosting
FROM python:3.11-slim

WORKDIR /app

# Configure glibc to prefer IPv4 over IPv6 (fixes Render unreachable IPv6 for cloud DBs)
RUN echo "precedence ::ffff:0:0/96  100" >> /etc/gai.conf

# Install curl for health checks if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies using production requirements
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy backend source code, configurations, and trained models
COPY config/ config/
COPY data/ data/
COPY src/ src/

# Copy built frontend production bundle from Stage 1
COPY --from=frontend-builder /app/frontend/dist frontend/dist

# Expose port (Render, Cloud Run, and Railway inject $PORT at runtime)
ENV PORT=8000
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["sh", "-c", "python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
