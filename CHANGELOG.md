# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2025-11-25

### Added
- Shared Playwright browser instance in `ScraperService` for better resource management.
- Minimum check duration enforcement for item checks.

### Changed
- Refactored scheduler for thread-safe database sessions.
- Centralized database session management for item retrieval.
- Enhanced AI service API base configuration.
- Made item check interval nullable and updated interval determination logic.

### Fixed
- Improved scraper input validation.
- Enhanced Playwright browser connection robustness.

## [0.1.4] - 2025-11-23

### Added
- AI reasoning effort setting for controlling model reasoning depth.
- OpenRouter provider support for additional AI model access.
- Empty LLM response validation to catch and handle empty AI responses.

### Changed
- Refactored AI service configuration for better maintainability.
- Improved `ai_api_base` default handling in settings.
- Increased AI service's default max tokens for better output quality.
- Suppressed verbose litellm logging to reduce noise.
- Updated dependencies and reordered Alembic imports.

## [0.1.3] - 2025-11-23

### Fixed
- AI provider switching issues (specifically Ollama to OpenAI).
- Handling of unsupported parameters (e.g., `temperature`) for certain models.
- Improved error messages for provider/model configuration mismatches.

## [0.1.2] - 2025-11-22

### Fixed
- CI/CD configuration issues (Docker tagging, isort, Codecov).

## [0.1.1] - 2025-11-22

### Changed
- Version bump.

## [0.1.0] - 2025-11-22

### Added
- Initial release of Pricecious.
- Basic API structure with FastAPI.
- Database integration with SQLAlchemy and PostgreSQL.
- Docker support for containerized deployment.
- CI/CD pipeline with GitHub Actions.
