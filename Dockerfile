# Stage 1: Builder
FROM python:3.11-slim AS builder

# Set build arguments and labels
ARG BUILD_DATE
ARG VCS_REF
LABEL maintainer="Development Team" \
      version="1.0.0" \
      description="Contract Processing System Backend" \
      build-date="${BUILD_DATE}" \
      vcs-ref="${VCS_REF}"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.4.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies and security updates
RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        curl \
        build-essential \
        libpq-dev \
        git \
        poppler-utils \
        # WeasyPrint dependencies
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install poetry - version locked to ensure compatibility
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=${POETRY_VERSION} python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Set working directory
WORKDIR /app

# Copy only requirements files first
COPY pyproject.toml poetry.lock README.md ./

# Install dependencies with retry mechanism
RUN poetry config virtualenvs.create true \
    && poetry config virtualenvs.in-project true \
    && poetry install --only main --no-interaction --no-ansi --no-root || \
       (poetry lock --no-update && poetry install --only main --no-interaction --no-ansi --no-root) \
    && poetry run pip install --no-cache-dir "gunicorn==21.2.0"

# Copy application code
COPY app ./app/

# Install the application
RUN poetry install --only-root --no-interaction --no-ansi

# Stage 2: Final
FROM python:3.11-slim

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WORKERS_PER_CORE=1 \
    MAX_WORKERS=4 \
    TIMEOUT=300 \
    GRACEFUL_TIMEOUT=300 \
    KEEP_ALIVE=5

# Install system dependencies and security updates
RUN apt-get update && apt-get upgrade -y \
    && apt-get install --no-install-recommends -y \
        curl \
        libpq-dev \
        poppler-utils \
        # WeasyPrint dependencies
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Create non-root user
    && groupadd -r appuser -g 1000 \
    && useradd -r -g appuser -u 1000 -d /app appuser \
    # Create necessary directories
    && mkdir -p /app/logs \
    && mkdir -p /app/celery_data/{in,out,processed} \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app/celery_data

# Copy built application from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# Set working directory
WORKDIR /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:8000/health || exit 1

# Command to run the application
CMD ["/app/.venv/bin/python", "-m", "gunicorn", \
    "app.main:app", \
    "--workers=4", \
    "--worker-class=uvicorn.workers.UvicornWorker", \
    "--bind=0.0.0.0:8000", \
    "--access-logfile=-", \
    "--error-logfile=-", \
    "--worker-tmp-dir=/dev/shm", \
    "--graceful-timeout=300", \
    "--timeout=300", \
    "--keep-alive=5", \
    "--max-requests=1000", \
    "--max-requests-jitter=50", \
    "--log-level=info"]