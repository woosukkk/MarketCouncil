FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 HF_HOME=/app/hf_cache
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl git && rm -rf /var/lib/apt/lists/*
COPY requirements.server.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && pip install --no-cache-dir -r requirements.server.txt
RUN python -m playwright install --with-deps chromium
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl --fail http://localhost:8501/_stcore/health || exit 1
CMD ["python", "-m", "streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", "--browser.gatherUsageStats=false"]
