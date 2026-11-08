# SupplySense Nexus - Backend Runtime Container
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Create non-privileged user for security
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Install application dependencies via pyproject.toml
COPY pyproject.toml ./
COPY backend ./backend
COPY scripts ./scripts
COPY alembic.ini ./

RUN pip install --no-cache-dir .

# Fix ownership
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check using standard Python urllib
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')" || exit 1

# Production ASGI server startup
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
