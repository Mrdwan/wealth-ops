#!/bin/bash
# scripts/run-tests-docker.sh
# Runs pytest in a Docker container - used by pre-commit hook

set -e

# Build and run tests
docker compose --profile test run --rm test pytest -v --tb=short "$@"
