.PHONY: install run api web web-build web-test test test-saas test-core test-collectors test-access migrate-saas clean format lint check

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

test: test-saas test-core test-collectors test-access

# Keep the suite in deterministic domains. Collector tests load optional heavy
# dependencies, while SaaS tests mutate isolated auth/storage state.
test-saas:
	pytest tests/test_api_auth.py tests/test_api_integration.py tests/test_api_e2e.py tests/test_tenant_authorization.py tests/test_tenant_route_isolation.py -q

test-core:
	pytest tests/test_config.py tests/test_exporter_full.py tests/test_mesh_aggregator.py tests/test_orchestrator_helpers.py tests/test_output tests/test_run_topics.py tests/test_shared_memory.py tests/test_storage.py tests/test_utils_aria.py -q

test-collectors:
	pytest tests/test_agents tests/test_collectors -q

test-access:
	pytest tests/test_access tests/test_cleaner_unit.py -q

migrate-saas:
	python3 scripts/migrate_saas.py

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
