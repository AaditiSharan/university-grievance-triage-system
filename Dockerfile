# Backend image for Google Cloud Run (FastAPI + triage pipeline).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_BACKEND=firestore

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY config ./config
COPY data ./data
COPY src ./src

# Rebuild the classifier so the model files match the pinned scikit-learn.
RUN python -m src.classifier.train

CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
