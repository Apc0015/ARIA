.PHONY: install run api web web-build web-test test clean format lint check

install:
	pip install -e ".[dev]"
	playwright install chromium

run:
	python -m aria.cli --mission missions/examples/default.yaml

api:
	python -m aria.cli --serve-api

web:
	cd aria-report && npm run dev

web-build:
	cd aria-report && npm run build

web-test:
	cd aria-report && npm run test

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf data/raw/* data/clean/* data/exports/* logs/*

format:
	black aria/ tests/
	isort aria/ tests/

lint:
	flake8 aria/ tests/ --max-line-length=88
	mypy aria/ --ignore-missing-imports

# Run tests + lint in one shot — use before commits
check: lint test
