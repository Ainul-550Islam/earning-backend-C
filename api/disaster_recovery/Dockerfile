FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    tar \
    gzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create backup storage directory
RUN mkdir -p /var/backups/dr && chmod 777 /var/backups/dr

# Non-root user
RUN useradd -m -u 1000 druser && chown -R druser:druser /app /var/backups/dr
USER druser

EXPOSE 8000

CMD ["uvicorn", "disaster_recovery.main:app", "--host", "0.0.0.0", "--port", "8000"]
