#!/usr/bin/env bash
# =============================================================
# run_tests.sh  -  Setup PostgreSQL and run all fraud detection tests
# =============================================================
set -e

DB_NAME="fraud_detection_test"
DB_USER="postgres"
DB_PASS="postgres"   # Change if your local postgres password differs
DB_HOST="localhost"
DB_PORT="5432"

echo "=========================================="
echo " Fraud Detection Test Runner"
echo "=========================================="

# 1. Check Python & pip
echo "[1/6] Checking Python..."
python3 --version

# 2. Install dependencies
echo "[2/6] Installing dependencies..."
pip install \
    django \
    djangorestframework \
    django-filter \
    channels \
    celery \
    redis \
    psycopg2-binary \
    pytest \
    pytest-django \
    pytest-cov \
    factory-boy \
    Faker \
    PyJWT \
    scipy \
    numpy \
    -q

# 3. Check PostgreSQL is running
echo "[3/6] Checking PostgreSQL..."
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
    echo "ERROR: PostgreSQL is not running on $DB_HOST:$DB_PORT"
    echo "Start it with: sudo service postgresql start  (Linux)"
    echo "           or: brew services start postgresql  (macOS)"
    exit 1
fi
echo "PostgreSQL is running."

# 4. Create test database if not exists
echo "[4/6] Setting up database..."
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -tc \
    "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
    || PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        -c "CREATE DATABASE $DB_NAME;"
echo "Database '$DB_NAME' ready."

# 5. Run migrations
echo "[5/6] Running migrations..."
DJANGO_SETTINGS_MODULE=test_settings python3 -m django migrate --run-syncdb

# 6. Run tests with coverage
echo "[6/6] Running tests..."
DJANGO_SETTINGS_MODULE=test_settings python3 -m pytest \
    fraud_detection/tests/ \
    --tb=short \
    -v \
    --cov=fraud_detection \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    -x \
    "$@"

echo ""
echo "=========================================="
echo " Tests complete! Coverage report: htmlcov/index.html"
echo "=========================================="
