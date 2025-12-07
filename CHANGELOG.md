# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-12-07

### Added
- **Analytics:** Comprehensive Item Analytics page with price history charts, statistics, outlier filtering, and time window selection.
- **Forecasting:** Implemented Prophet model for price forecasting with dynamic seasonality, regressor configuration, and horizon capping.
- **Stock Tracking:** Track and visualize in-stock status (depleted/restocked) in analytics charts.
- **UI:** New Table UI component and Min/Max price annotations on charts.
- **AI:** Custom AI prompt field for items.
- **Server:** Switched to **Granian** as the web server for better performance.
- **Settings:** Comprehensive settings management page.
- **Development:** Integrated Biome for frontend formatting and Ruff updates.

### Changed
- **Database:** Major migration to **SQLAlchemy 2.0** async/await syntax.
- **Performance:** Implemented analytics data caching and SQL-based aggregation.
- **Performance:** Price history downsampling for large datasets.
- **Refactor:** Standardized datetime handling to UTC across the application.
- **Refactor:** Externalized database session management and improved scheduler thread safety.

### Fixed
- Fixed JSX issues in History page.
- Addressed outlier prevention bugs.
- Fixed asynchronous Alembic migrations by implementing async engine.

## [0.1.6] - 2025-11-27

### Added
- Calculate and display dynamic item refresh intervals and next check times.
- Display item refresh interval on card.

### Changed
- Clarify interval terminology in settings from 'check' to 'refresh'.
- Remove job next run display from settings.
- Ruff updates (linting/formatting fixes).

### Fixed
- Standardize datetime handling to use naive local times for database consistency.
- Add `next_check` and `interval` fields to `Watch` schema.
- Extract scraper initialization logic, update dependencies, and add a reconnection deadlock test.
- Remove UTC import and usage from datetime comparisons.
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
