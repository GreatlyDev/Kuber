FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEVASSIST_EXECUTION_ENABLED=false

WORKDIR /app

RUN adduser --system --group --home /app --no-create-home devassist

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages

RUN python -m pip install --upgrade pip && \
    python -m pip install -e . && \
    chown -R devassist:devassist /app

EXPOSE 8000

USER devassist

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"

CMD ["uvicorn", "devassist_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
