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

# Increase timeouts and retries for slow connections
RUN pip install --no-cache-dir --upgrade pip && \
    pip config set global.timeout 5000 && \
    pip config set global.retries 100

COPY requirements.txt .

# Install numpy first, then everything else
RUN pip install --no-cache-dir "numpy>=1.26.0,<2.0.0" && \
    pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN groupadd -r sheetagent && useradd -r -g sheetagent sheetagent

# Copy application code
COPY . .

# Auto-create all missing __init__.py files (prevents import errors)
RUN find /app/app -type d -exec touch {}/__init__.py \; 2>/dev/null || true

# Create workspace directories
RUN mkdir -p /app/workspace/{incoming,processing,extracted,cleaned,excels,charts,reports,logs,memory,temp} \
    && chown -R sheetagent:sheetagent /app

USER sheetagent

# Pre-download EasyOCR English model (~100MB) to avoid cold start delay
# The || true means build won't fail if this times out
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)" || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
