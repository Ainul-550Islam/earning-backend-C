FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user
RUN useradd -m -u 1000 celeryuser && chown -R celeryuser:celeryuser /app
USER celeryuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD celery -A tasks.celery inspect ping -d celery@${HOSTNAME} || exit 1

EXPOSE 5555

CMD ["celery", "-A", "tasks.celery", "worker", "--loglevel=info"]