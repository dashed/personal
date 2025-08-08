# Dotfiles Management System - Makefile
# Common development workflows and commands

.PHONY: help install dev test lint format clean build run validate status sync ty ty-check quick-check

# Default target - show help
help:
	@echo "Dotfiles Management System - Development Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test         Run unit tests with coverage"
	@echo "  make test-v       Run tests with verbose output"
	@echo "  make lint         Run linters (ruff)"
	@echo "  make format       Format code with ruff"
	@echo "  make typecheck    Run ty type checking (strict)"
	@echo "  make ty           Run ty type checking (fast)"
	@echo "  make quick-check  Run ty + ruff (fast checks)"
	@echo ""
	@echo "CLI Operations:"
	@echo "  make run          Run CLI with default config"
	@echo "  make validate     Validate dotfiles.toml"
	@echo "  make status       Show system status"
	@echo "  make sync         Sync dotfiles (dry-run)"
	@echo "  make sync-apply   Sync dotfiles (apply changes)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        Remove build artifacts and cache"
	@echo "  make clean-db     Remove state database"
	@echo "  make build        Build distribution packages"
	@echo "  make check        Run all checks (lint, typecheck, test)"
	@echo ""
	@echo "Docker Integration Testing:"
	@echo "  make docker-test                  Run all integration tests"
	@echo "  make docker-test-pattern PATTERN Run tests matching pattern (* wildcards)"
	@echo "  make docker-test-specific TEST=   Run a specific test by name"
	@echo "  make docker-test-list             List all available integration tests"
	@echo "  make docker-test-dry-run PATTERN  Show which tests would run (dry-run)"
	@echo "  make docker-test-verbose PATTERN  Run tests with verbose output"
	@echo "  make docker-test-quick            Run tests with summary only"
	@echo "  make docker-test-all              Run tests on all platforms"
	@echo "  make docker-clean                 Clean up Docker resources"
	@echo ""
	@echo "Pattern examples:"
	@echo "  make docker-test-pattern PATTERN='*safety*'     # Safety tests"
	@echo "  make docker-test-pattern PATTERN='*core* *cli*' # Core and CLI tests"
	@echo "  make docker-test-specific TEST=docker_test_core_operations"
	@echo ""
	@echo "Quick shortcuts:"
	@echo "  make docker-test-safety    # All safety-related tests"
	@echo "  make docker-test-core      # Core operations tests"
	@echo "  make docker-test-cli       # CLI command tests"
	@echo "  make docker-test-database  # Database integration tests"
	@echo "  make docker-test-phase3    # Phase 3: Enhanced user journeys"

# Install production dependencies
install:
	uv sync --no-dev

# Install all dependencies including dev
dev:
	uv sync

# Run unit tests with coverage
test:
	uv run pytest tests/ --cov=dotfiles_sync --cov-report=term-missing

# Run tests with verbose output
test-v:
	uv run pytest tests/ -v --tb=short --cov=dotfiles_sync --cov-report=term-missing

# Run specific test file
test-file:
	@read -p "Test file (e.g., test_config): " file; \
	uv run pytest tests/unit/$$file.py -v

# Run linters
lint:
	uv run ruff check src/ tests/

# Format code
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Type checking only
typecheck:
	uv run ty check src/

# Fast type checking with ty
ty:
	uv run ty check src/

# Alias for ty
ty-check: ty

# Quick checks with ty and ruff (fast feedback)
quick-check:
	@echo "Running quick checks with ty and ruff..."
	uv run ty check src/
	uv run ruff check src/ tests/
	@echo "✅ Quick checks passed!"

# Fast check without Docker (for rapid development)
check-fast: lint typecheck test
	@echo "✅ Fast checks passed (unit tests only)!"

# Run all checks (including Docker integration tests)
check: lint typecheck test docker-integration-tests
	@echo "✅ All checks passed (including Docker integration tests)!"

# Alias for CI/CD - run everything
check-all: check
	@echo "🎆 Complete validation successful!"

# Clean build artifacts and cache
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf __pycache__/
	rm -rf src/**/__pycache__/
	rm -rf tests/**/__pycache__/
	rm -rf .coverage
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Clean state database
clean-db:
	rm -rf ~/.local/state/dotfiles/

# Build distribution packages
build: clean
	uv build

# Run CLI with help
run:
	uv run dotfiles-sync --help

# Validate configuration
validate:
	uv run dotfiles-sync validate

# Show system status
status:
	uv run dotfiles-sync status

# Sync dotfiles (dry-run by default)
sync:
	uv run dotfiles-sync sync

# Sync dotfiles with apply
sync-apply:
	uv run dotfiles-sync --apply sync

# Run with custom config
sync-custom:
	@read -p "Config file path: " config; \
	uv run dotfiles-sync --config $$config sync

# Run with specific variant
sync-variant:
	@read -p "Variant name (default/personal/work): " variant; \
	uv run dotfiles-sync --variant $$variant sync

# Show version
version:
	uv run dotfiles-sync --version

# Interactive shell with project environment
shell:
	uv run python

# Watch for changes and run tests (requires entr)
watch:
	@command -v entr >/dev/null 2>&1 || { echo "entr is required: brew install entr"; exit 1; }
	find src tests -name "*.py" | entr -c make test

# Generate coverage HTML report
coverage-html:
	uv run pytest tests/ --cov=dotfiles_sync --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"
	@command -v open >/dev/null 2>&1 && open htmlcov/index.html || echo "Open htmlcov/index.html in your browser"

# Update dependencies
update-deps:
	uv lock --upgrade

# Show outdated packages
outdated:
	uv pip list --outdated

# Security audit (if safety is installed)
audit:
	@command -v safety >/dev/null 2>&1 || uv pip install safety
	uv run safety check

# Create source distribution
sdist:
	uv build --sdist

# Create wheel distribution
wheel:
	uv build --wheel

# Install locally in editable mode
install-editable:
	uv pip install -e .

# Uninstall
uninstall:
	uv pip uninstall dotfiles-sync

# === Docker Testing (Phase 1 MVP) ===

# Build Docker test image
docker-build:
	docker build -t dotfiles-phase1-test -f Dockerfile.test .

# Run all Phase 1 Docker tests with statistics
docker-test-all:
	@echo "Starting All Docker Integration Tests..."
	@mkdir -p test-results
	@docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit 2>&1 | tee test-results/docker-test-all.log | grep -E "TEST|PASSED|FAILED|SKIPPED|━━━|✓|✗|⊘|✅|❌|Pass Rate|suite" || true
	@docker-compose -f docker-compose.test.yml down
	@echo ""
	@echo "=== OVERALL TEST SUMMARY ==="
	@for service in phase1-ubuntu-default phase1-ubuntu-personal phase1-ubuntu-work phase1-debian-default; do \
		echo -n "$$service: "; \
		docker-compose -f docker-compose.test.yml run --rm $$service cat /tmp/test-results.json 2>/dev/null | grep -o '"status":[^,}]*' | sed 's/"status"://g' | sed 's/"//g' || echo "NO RESULTS"; \
	done
	@echo ""
	@echo "Full test logs saved to test-results/"

# Run single Phase 1 test (default variant) with statistics
docker-test:
	@echo "Starting Docker Integration Tests..."
	@mkdir -p test-results
	@docker-compose -f docker-compose.test.yml up --build phase1-ubuntu-default 2>&1 | tee test-results/docker-test.log | grep -E "TEST|PASSED|FAILED|SKIPPED|━━━|✓|✗|⊘|✅|❌|Pass Rate" || true
	@docker-compose -f docker-compose.test.yml down

# Test new verb implementations in Docker
docker-test-new-verbs:
	@echo "Testing new verb implementations in Docker..."
	@docker build -t dotfiles-new-verbs-test -f Dockerfile.test .
	@docker run --rm -v $(PWD):/app dotfiles-new-verbs-test python /app/tests/integration/docker_test_new_verbs.py
	@echo ""
	@if docker-compose -f docker-compose.test.yml run --rm phase1-ubuntu-default cat /tmp/test-results.json 2>/dev/null; then \
		echo ""; \
		echo "Test results saved to test-results/"; \
	fi

# Run E2E User Journey tests in Docker
docker-test-e2e:
	@echo "🎯 Running End-to-End User Journey Tests in Docker..."
	@docker build -t dotfiles-e2e-test -f Dockerfile.test .
	@docker run --rm -v $(PWD):/app -e DOTFILES_TEST_MODE=true dotfiles-e2e-test python /app/tests/integration/docker_test_e2e_user_journeys.py

# Run E2E tests with verbose output
docker-test-e2e-verbose:
	@echo "🎯 Running E2E Tests (Verbose)..."
	@docker build -t dotfiles-e2e-test -f Dockerfile.test .
	@docker run --rm -it -v $(PWD):/app -e DOTFILES_TEST_MODE=true dotfiles-e2e-test python /app/tests/integration/docker_test_e2e_user_journeys.py

# Run ALL integration tests in Docker (safe) - main command
docker-integration-tests:
	@echo "🐳 Running ALL integration tests in Docker (safe environment)..."
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@echo "Running unit tests in Docker..."
	@docker run --rm -v $(PWD):/app --entrypoint sh dotfiles-test -c "cd /app && uv run pytest tests/unit -q"
	@echo "Running ALL integration tests in Docker..."
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 -e DOTFILES_TEST_MODE=true --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py || (echo "❌ Integration tests failed" && exit 1)
	@echo "✅ All tests passed in Docker!"

# Alias for backward compatibility
docker-integration: docker-integration-tests

# === Pattern-Based Test Execution ===

# Run tests matching a glob pattern
docker-test-pattern:
	@if [ -z "$(PATTERN)" ]; then echo "Usage: make docker-test-pattern PATTERN='*safety*'"; exit 1; fi
	@echo "🔍 Running integration tests matching pattern: $(PATTERN)"
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 -e DOTFILES_TEST_MODE=true --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py $(PATTERN)

# Run a specific test by name
docker-test-specific:
	@if [ -z "$(TEST)" ]; then echo "Usage: make docker-test-specific TEST=docker_test_core_operations"; exit 1; fi
	@echo "🎯 Running specific integration test: $(TEST)"
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 -e DOTFILES_TEST_MODE=true --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py '$(TEST)'

# List all available integration tests
docker-test-list:
	@echo "📋 Listing all available integration tests..."
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py --list

# Show which tests would run without executing them
docker-test-dry-run:
	@if [ -z "$(PATTERN)" ]; then echo "Usage: make docker-test-dry-run PATTERN='*safety*'"; exit 1; fi
	@echo "🏃‍♂️ Dry run - showing tests that would match pattern: $(PATTERN)"
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py --dry-run $(PATTERN)

# Run tests with verbose output
docker-test-verbose:
	@if [ -z "$(PATTERN)" ]; then PATTERN_ARG=""; else PATTERN_ARG="'$(PATTERN)'"; fi; \
	echo "🔊 Running integration tests with verbose output"; \
	if [ -n "$(PATTERN)" ]; then echo "Pattern: $(PATTERN)"; fi; \
	docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1); \
	docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 -e DOTFILES_TEST_MODE=true --entrypoint python dotfiles-test /app/tests/integration/run_integration_tests.py --verbose $$PATTERN_ARG

# Quick shortcuts for common test patterns
docker-test-safety:
	@$(MAKE) docker-test-pattern PATTERN='*safety*'

docker-test-core:
	@$(MAKE) docker-test-pattern PATTERN='*core*'

docker-test-cli:
	@$(MAKE) docker-test-pattern PATTERN='*cli*'

docker-test-database:
	@$(MAKE) docker-test-pattern PATTERN='*database*'

docker-test-e2e-pattern:
	@$(MAKE) docker-test-pattern PATTERN='*e2e*'

docker-test-phase3:
	@echo "🚀 Running Phase 3: Enhanced User Journey Tests in Docker..."
	@docker build -q -t dotfiles-test -f Dockerfile.test . || (echo "❌ Failed to build Docker image" && exit 1)
	@docker run --rm -v $(PWD):/app -e RUNNING_IN_DOCKER=1 -e DOTFILES_TEST_MODE=true --entrypoint python dotfiles-test /app/tests/integration/docker_test_phase3_user_journeys.py

# Verify integration tests are Docker-only (will fail if not in Docker)
verify-docker-guard:
	@echo "Verifying integration tests have Docker guards..."
	@python3 -c "import sys; sys.path.insert(0, 'tests/integration'); from docker_only_guard import require_docker; require_docker()" 2>&1 | grep -q "SAFETY ERROR" && echo "✅ Docker guard prevents host execution" || echo "❌ Docker guard failed - integration tests might run on host!"

# Test specific variant
docker-test-variant:
	@read -p "Variant (default/personal/work): " variant; \
	mkdir -p test-results; \
	docker-compose -f docker-compose.test.yml up --build phase1-ubuntu-$$variant; \
	docker-compose -f docker-compose.test.yml down

# Test on Ubuntu (Phase 1)
test-ubuntu:
	docker-compose -f docker-compose.test.yml up --build phase1-ubuntu-default

# Clean Docker test artifacts
docker-clean:
	docker-compose -f docker-compose.test.yml down -v
	rm -rf test-results/
	docker system prune -f

# Quick Docker test with summary only
docker-test-quick:
	@echo "Running Quick Docker Test..."
	@mkdir -p test-results
	@docker-compose -f docker-compose.test.yml up --build phase1-ubuntu-default > test-results/docker-quick.log 2>&1
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "TEST RESULTS"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@grep -E "(Total Tests|Passed|Failed|Skipped|Pass Rate|✅|❌)" test-results/docker-quick.log | tail -6 | sed 's/^[^T|P|F|S]*//' || echo "Unable to parse test results. Check test-results/docker-quick.log"
	@docker-compose -f docker-compose.test.yml down > /dev/null 2>&1
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


# Test on Fedora
test-fedora:
	@echo "Fedora testing will be implemented in Phase 4"
	# docker run --rm -v $(PWD):/app dotfiles-test:fedora

# === Development Helpers ===

# Start new feature branch
feature:
	@read -p "Feature name: " feature; \
	git checkout -b feature/$$feature

# Create new verb module (Phase 1)
new-verb:
	@read -p "Verb name (e.g., link, copy): " verb; \
	cp src/verbs/__init__.py src/verbs/$$verb.py; \
	echo "Created src/verbs/$$verb.py"

# Run specific CLI command with debug logging
debug:
	uv run dotfiles-sync --log-level DEBUG $(ARGS)

# Quick validate and test
quick: validate test
	@echo "✅ Quick check passed!"

# Full CI simulation
ci: clean check build
	@echo "✅ CI simulation passed!"

# Show project stats
stats:
	@echo "=== Project Statistics ==="
	@echo "Lines of code:"
	@find src -name "*.py" -exec wc -l {} + | tail -1
	@echo ""
	@echo "Test files:"
	@find tests -name "*.py" | wc -l
	@echo ""
	@echo "Test cases:"
	@grep -r "def test_" tests/ | wc -l
	@echo ""
	@echo "TODO items:"
	@grep -r "TODO" src/ tests/ | wc -l || echo "0"

# Show recent git commits
log:
	@git log --oneline -10

# Show git status
git-status:
	@git status -s

# Commit with conventional commit message
commit:
	@read -p "Commit type (feat/fix/docs/style/refactor/test/chore): " type; \
	read -p "Commit message: " msg; \
	git add -A && git commit -m "$$type: $$msg"

# Push to remote
push:
	git push origin $(shell git branch --show-current)

# Create a new release tag
release:
	@read -p "Version (e.g., 1.0.1): " version; \
	git tag -a v$$version -m "Release v$$version"; \
	echo "Tagged v$$version - use 'make push-tags' to push"

# Push tags to remote
push-tags:
	git push --tags

# Show current configuration
show-config:
	@echo "=== Current Configuration ==="
	@cat dotfiles.toml

# Backup current dotfiles before testing
backup:
	@mkdir -p backups/$(shell date +%Y%m%d_%H%M%S)
	@echo "Backup directory created: backups/$(shell date +%Y%m%d_%H%M%S)"

# === Phase-specific targets ===

# Phase 1: Test link operation (when implemented)
test-link:
	@echo "Link operation will be implemented in Phase 1"

# Phase 1: Test copy operation (when implemented)
test-copy:
	@echo "Copy operation will be implemented in Phase 1"

# Phase 1: Test rollback (when implemented)
test-rollback:
	@echo "Rollback will be implemented in Phase 1"

# Phase 2: Test backup system (when implemented)
test-backup:
	@echo "Backup system will be implemented in Phase 2"

# Phase 3: Test package managers (when implemented)
test-packages:
	@echo "Package managers will be implemented in Phase 3"

.DEFAULT_GOAL := help