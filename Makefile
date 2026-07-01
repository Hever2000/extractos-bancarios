.PHONY: install test lint typecheck clean docker-build docker-test docker-lint docker-typecheck docker-all

install:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

test-coverage:
	python -m pytest tests/ --cov=src --cov-report=term-missing

test-benchmark:
	python -m pytest tests/ --benchmark-only

lint:
	ruff check src/ tests/

typecheck:
	mypy src/

robustness:
	python -m pytest tests/laboratorio/ -v --tb=short -m robustez -x

robustness-full:
	python -m pytest tests/laboratorio/ -v --tb=long --maxfail=5

robustness-edge:
	python -m pytest tests/laboratorio/ -v --tb=short -m edge

robustness-report:
	python -m pytest tests/laboratorio/test_robustez.py::test_consolidated_report -v --tb=short

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache

docker-build:
	docker compose build lambda

docker-test:
	docker compose run --rm test

docker-lint:
	docker compose run --rm lint

docker-typecheck:
	docker compose run --rm typecheck

docker-all: docker-build docker-lint docker-typecheck docker-test

docker-shell:
	docker compose run --rm --entrypoint /bin/bash lambda

docker-local:
	docker compose up lambda

# Deploy: build and push to ECR
# Assumes AWS_ACCOUNT_ID and AWS_REGION are set
docker-deploy:
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	docker tag extractos-bancarios:latest $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/extractos-bancarios:latest
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/extractos-bancarios:latest
