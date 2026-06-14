FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEVASSIST_EXECUTION_ENABLED=false

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages

RUN python -m pip install --upgrade pip && \
    python -m pip install -e .

EXPOSE 8000

CMD ["uvicorn", "devassist_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
