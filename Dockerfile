# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps only for compilation, then strip
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "app:flask_app", "-b", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--access-logfile", "-"]