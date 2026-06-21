# ── Single-stage build (avoids --prefix copy issues) ─────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (build tools + runtime libs in one layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set HOME for EasyOCR model cache
ENV HOME=/app

# 1. Create the sheetagent system group and user first
RUN groupadd -r sheetagent && useradd -r -g sheetagent -d /home/sheetagent -m sheetagent

# 2. Create the directory (if it doesn't already exist) and grant ownership safely
RUN mkdir -p /home/sheetagent && chown -R sheetagent:sheetagent /home/sheetagent
# Increase timeouts and retries for slow connections
RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.timeout 5000 && \
    pip config set global.retries 100

COPY requirements.txt .

# Install numpy first with extended timeout, then everything else
RUN pip install --no-cache-dir --default-timeout=1000 "numpy>=1.26.0,<2.0.0" && \
    pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy application code
COPY . .

# Auto-create all missing __init__.py files (prevents import errors)
RUN find /app/app -type d -exec touch {}/__init__.py \; 2>/dev/null || true

# Create workspace directories
RUN mkdir -p /app/workspace/{incoming,processing,extracted,cleaned,excels,charts,reports,logs,memory,temp} \
    && chown -R sheetagent:sheetagent /app

USER sheetagent

# Skip EasyOCR pre-download to speed up builds
# Model will download on first use instead
# RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)" || true

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
