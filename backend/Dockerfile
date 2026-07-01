# Cloud Run backend image for the FastAPI service.
# Build with the repository root as context:
#   docker build -f backend/Dockerfile -t med-intel-backend .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install Python dependencies first so Docker can cache this layer when backend
# source changes but requirements.txt does not.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy only the backend package required by the Cloud Run service.
COPY backend ./backend

RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
