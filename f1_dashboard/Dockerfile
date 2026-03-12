FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/

# Copy pre-built frontend
COPY frontend/dist/ ./frontend/dist/

# Copy backtest CSVs
COPY backtest_data/ ./backtest/

# Data directory for SQLite (will be mounted as persistent volume on Fly.io)
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV DRY_RUN=true
ENV DB_PATH=/app/data/f1trading.db
ENV PYTHONPATH=/app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
