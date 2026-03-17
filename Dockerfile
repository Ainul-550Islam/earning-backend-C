FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
RUN find . -name "*.pyc" -delete 2>/dev/null; true
CMD python manage.py shell -c "from django.db import connection; connection.cursor().execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')" && python manage.py migrate --no-input && python manage.py collectstatic --no-input && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
