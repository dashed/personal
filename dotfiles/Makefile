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
	@echo "  make lint         Run linters (ruff, mypy)"
	@echo "  make format       Format code with ruff"
	@echo "  make typecheck    Run mypy type checking"
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
	@echo "Docker Testing (Phase 4):"
	@echo "  make docker-test  Run Docker integration tests"
	@echo "  make test-ubuntu  Test on Ubuntu container"
	@echo "  make test-alpine  Test on Alpine container"

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
	uv run mypy src/

# Format code
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Type checking only
typecheck:
	uv run mypy src/ --strict

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

# Run all checks
check: lint typecheck test
	@echo "✅ All checks passed!"

# Clean build artifacts and cache
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
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

# Run all Phase 1 Docker tests
docker-test-all:
	mkdir -p test-results
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
	docker-compose -f docker-compose.test.yml down

# Run single Phase 1 test (default variant)
docker-test:
	mkdir -p test-results
	docker-compose -f docker-compose.test.yml up --build phase1-ubuntu-default
	docker-compose -f docker-compose.test.yml down

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