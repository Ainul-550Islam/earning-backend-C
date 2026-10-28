# CMS Makefile — shortcuts for common dev tasks
.PHONY: help install migrate run celery test lint security-check

help:
	@echo "CMS Development Commands"
	@echo "  make install          — Install all dependencies"
	@echo "  make migrate          — Run all DB migrations"
	@echo "  make run              — Start Django dev server"
	@echo "  make celery           — Start Celery worker"
	@echo "  make celery-beat      — Start Celery Beat scheduler"
	@echo "  make test             — Run all tests"
	@echo "  make test-cov         — Run tests with coverage"
	@echo "  make lint             — Run flake8"
	@echo "  make security-check   — Run bandit security scan"
	@echo "  make check-deploy     — Django deployment checks"
	@echo "  make superuser        — Create admin superuser"
	@echo "  make shell            — Django shell"

install:
	pip install -r requirements.txt

migrate:
	python manage.py makemigrations cms
	python manage.py migrate

run:
	python manage.py runserver 0.0.0.0:8000

celery:
	celery -A config worker --loglevel=info --concurrency=4

celery-beat:
	celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

test:
	pytest api/cms/tests/ -v --tb=short

test-cov:
	pytest api/cms/tests/ -v --cov=api/cms --cov-report=html --cov-report=term-missing

lint:
	flake8 api/cms/ --max-line-length=120 --exclude=migrations

security-check:
	bandit -r api/cms/ -x api/cms/tests/ -ll

check-deploy:
	python manage.py check --deploy

superuser:
	python manage.py createsuperuser

shell:
	python manage.py shell_plus

load-fixtures:
	python manage.py loaddata api/cms/fixtures/*.json

collect-static:
	python manage.py collectstatic --noinput

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
