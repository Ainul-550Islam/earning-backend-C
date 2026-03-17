FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
RUN pip install --no-cache-dir -r requirements.txt
RUN echo "cache-bust-$(date +%s)"

COPY . .

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
