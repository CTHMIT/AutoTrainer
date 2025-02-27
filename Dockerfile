FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PDM_USE_VENV=0

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PDM
RUN pip install --no-cache-dir pdm==2.11.1

# Set working directory
WORKDIR /app

# Copy PDM files
COPY pyproject.toml pdm.lock* README.md /app/

# Install dependencies using PDM
RUN pdm install --no-self --prod --no-editable

# Copy application code
COPY src /app/src/

# Create log directory
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Create non-root user
RUN addgroup --system app && adduser --system --group app
RUN chown -R app:app /app
USER app

# Expose port for API
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["pdm", "run"]

# Default command (can be overridden)
CMD ["python", "-m", "src.api.app"]
