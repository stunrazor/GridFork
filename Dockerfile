# GridFork FastAPI demo. Portable: runs on Render, Hugging Face Spaces
# (Docker), Railway, Fly, or any container host. The app binds 0.0.0.0 on
# $PORT (hosts set it; 8000 locally) and degrades gracefully without keys.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'))"
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
