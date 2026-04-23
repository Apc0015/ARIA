.PHONY: install run api test clean format lint check

install:
	pip install -e ".[dev]"
	playwright install chromium

run:
	python -m aria.cli --mission missions/examples/default.yaml

api:
	python -m aria.cli --serve-api

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf data/raw/* data/clean/* data/exports/* logs/*

format:
	black aria/ infocollector/ tests/
	isort aria/ infocollector/ tests/

lint:
	flake8 aria/ infocollector/ tests/ --max-line-length=88
	mypy aria/ infocollector/ --ignore-missing-imports

# Run tests + lint in one shot — use before commits
check: lint test
