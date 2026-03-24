# Contributing Guide

Thank you for your interest in contributing to Earning Platform!

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `python manage.py test`
5. Commit: `git commit -m "feat: your feature description"`
6. Push: `git push origin feature/your-feature`
7. Open a Pull Request

## Code Style

- Python: follow PEP 8
- JavaScript/React: ESLint rules
- Commit messages: use conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)

## Running Tests

```bash
# Backend
python manage.py test
coverage run manage.py test && coverage report

# Frontend
cd frontend && npm run test
```

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python/Node version
- Error logs
