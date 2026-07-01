FROM python:3.10-slim

# ============ System Dependencies ============
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    aria2 \
    libopus0 \
    curl \
    git \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    wget \
    unzip \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# ============ Set Work Directory ============
WORKDIR /app

# ============ Environment Variables ============
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    TEMP_DIR=/app/temp \
    TZ=Africa/Cairo

# ============ Copy & Install Requirements ============
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============ Install Extra Tools ============
RUN pip install --no-cache-dir \
    telethon>=1.36.0 \
    aiohttp>=3.9.0 \
    pillow>=10.0.0 \
    phonenumbers>=8.13.0 \
    fake-useragent>=1.5.0 \
    cryptography>=41.0.0

# ============ Copy Project Files ============
COPY . .

# ============ Create Required Directories ============
RUN mkdir -p /app/data && \
    mkdir -p /app/data/sessions && \
    mkdir -p /app/data/temp && \
    mkdir -p /app/logs && \
    mkdir -p /app/downloads

# ============ Set Permissions ============
RUN chmod +x /app/*.py 2>/dev/null || true && \
    chown -R nobody:nogroup /app

# ============ Switch to Non-Root User ============
USER nobody

# ============ Expose Port (If Web Interface) ============
EXPOSE 5000

# ============ Health Check ============
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# ============ Run Bot ============
CMD ["python", "run.py"]
