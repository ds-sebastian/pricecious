# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-09-25

### Fixed
- Deleting an item or notification profile failed with "Request failed (403)" behind reverse proxies whose firewall
  only allows GET and POST (the OWASP Core Rule Set default, used by CrowdSec AppSec and ModSecurity setups). The web
  UI now sends edits and deletes as POST; the REST API is unchanged.
- A reading's stock can be set back to unknown.
- Editing or deleting readings now also updates the item's price and stock confidence.
- "Select all matching" readings no longer shrinks to one page when a row or page is unticked.
- Alerts show a price of 0 instead of leaving it out.
- Version bumps also update `uv.lock`, so the next release doesn't fail `uv sync --locked`.

### Changed
- Dependencies upgraded to their latest compatible versions (SQLAlchemy 2.1, Starlette 1.7, LiteLLM 1.102, ...).

## [0.3.0] - 2026-09-25

### Added
- **Change detection:** checks skip the AI while a page's prices and stock wording match the last AI check (at least
  one real AI check a day; "Check now" always uses it). On by default; Settings shows how many checks it saved.
- **Currencies:** each item keeps its currency, detected from the page on the first check (or the site's domain) and
  editable. Prices, charts and notifications use it instead of always showing `$`.
- **Test AI settings:** run the settings form, saved or not, on one of your items and see the model's answer.
- **Faster adding:** a bookmarklet adds the page you're on, and items added without a name take the page title.
- **Deals:** "Lowest price seen" and "Lowest in 90 days" badges, and an optional "new lowest price" notification
  that replaces the price-drop message when both apply. Misreads never count as a record.
- **Filters:** "Needs attention" and "Deals" views on the Items page.
- **History filters:** filter an item's readings by price range, stock (including unknown) and confidence, including
  "low", meaning below your minimum confidence, so those readings never changed the price.
- **Bulk history fixes:** tick readings, or every reading matching the filters across pages, then delete them or set
  the right price and stock in one go.
- **Check all cooldown:** "Check all" skips items checked in the last 5 minutes and says how many it skipped.
- **Price ranges and sales:** pages that list a range across options ("$1,799 – $2,048") record the cheapest option
  as the price and show the top of the range. The crossed-out "was" price and the store's promotion label ("Limited
  Time Offer") are recorded too, shown as a sale badge with the discount, and mentioned in alerts. Site-wide banners
  don't count as a promotion.
- **README screenshots** of the current UI in light and dark.

### Changed
- **Thinking:** "Reasoning effort" (OpenAI only) became **Thinking (if available)** for every provider, off by
  default, with a **Reasoning level** (low by default) used when it's on. Off uses the least thinking each model
  allows; on adds a thinking allowance on top of Max output tokens so the answer still fits. OpenAI users who had
  chosen a reasoning level keep thinking on at that level.
- **Popups:** signup and cookie popups are closed with their own close or "no thanks" buttons (never a sign-up
  button), and any overlay still covering the page is hidden before the screenshot. The AI is also told to read the
  product behind anything left over.
- **Change detection** also watches sale wording ("limited time", "% off", "clearance"), so a sale starting or
  ending on an unchanged price is still read.
- **Charts:** thinning long histories keeps each period's real first, last, lowest and highest readings instead of
  averaging them, which drew prices that never existed.
- **Rewrite:** Backend reorganized into a few flat modules and the frontend rebuilt with fewer dependencies (no Radix,
  axios, date-fns or APScheduler, slowapi, tenacity, cachetools).
- **UI:** Analytics and History merged into a page per item. Tag comparison moved to Compare. Settings are saved with
  one explicit Save instead of on every keystroke.
- **AI:** An item's custom prompt now adds instructions to the built-in prompt instead of replacing it.
- **Docker:** Images install the exact locked dependency versions.

### Fixed
- Temperature and confidence sliders in Settings did nothing.
- Editing the masked API key saved the mask plus whatever was typed.
- Choosing a non-Ollama provider kept sending requests to the Ollama base URL.
- The target-price alert repeated on every check while the price stayed below target.
- Manual and "check all" runs ignored the concurrency limit, and the scheduler skipped beats during long runs.
- Items stayed stuck "refreshing" for an hour after a restart.
- The price history index was dropped by an earlier migration, slowing charts and history.
- Paused items could not be resumed from the UI.
- Unknown stock was shown as "Out of stock" in history.
- `SCREENSHOT_DIR` was not the directory the UI served screenshots from.
- The app failed to start when Browserless was not reachable yet.
- Failed test notifications were reported as sent.
- Check failures now say why (bot check, load error, AI error) instead of a generic message.
- European prices such as `1.234,56` are parsed correctly.
- Thinking models (Qwen 3 in Ollama, Gemini 2.5 and others) could spend the whole token budget reasoning and return
  nothing, failing with "returned an empty response". Thinking is now off by default, and a reply that runs out of
  tokens before answering says so instead of being retried.
- Pages showing "unable to display the requested page" are reported as blocked instead of being sent to the AI.
- Correcting a low-confidence reading by hand left it ignored by deals and new-low alerts; corrected readings now
  count as confirmed.
- Trackers blocked by a DNS blocklist were logged as blocked requests on every check, and LiteLLM logged each AI call
  twice at INFO. Both are now quiet (set `LITELLM_LOG` to see LiteLLM's logs).

## [0.2.3] - 2026-03-01

### Added
- **Browserless:** Replaced `BROWSERLESS_LAUNCH_OPTS_BASE64` with individual, human-readable environment variables for easier configuration.
- **CI:** Added frontend Biome lint/format checks and Dependabot support for GitHub Actions dependencies.

### Changed
- **Dependencies:** Updated frontend dependencies — React 18 → 19, react-router-dom 6 → 7, @vitejs/plugin-react 4 → 5.

### Fixed
- **CI:** Simplified CI workflow, fixed linting issues, and added automated dependency update configuration.
- **Browserless:** Improved startup timeout handling for more reliable browser connections.

## [0.2.2] - 2025-12-16

### Added
- **Browserless:** Added standard Chromium support and improved connection error handling/URL discovery to support more browserless configurations.
- **Forecast:** Added "beta" label to forecast feature.

### Fixed
- **UI:** Removed redundant "next check" and "interval" display from ItemCard.
- **Tests:** Fixed ScraperService mocking and database engine disposal in tests.

## [0.2.1] - 2025-12-10

### Added
- **Scheduler:** Implemented scheduled data refresh job with configurable interval.
- **Robustness:** Added retry logic in `AIService` to handle empty LLM responses gracefully.
- **Tests:** Added integration tests for scheduler startup and job registration.

### Fixed
- **Scraper:** Enhanced scraper to exit early on navigation failures and reset browser state.
- **Hyperscaling:** Fixed heartbeat mechanism for `scheduled_refresh`.
- **AI:** Automatically infer Ollama provider from API base URL.
- **AI:** Enforced `json_repair` usage for more reliable JSON parsing.

### Refactor
- **Lifecycle:** Enhanced application lifespan management with robust error handling and graceful shutdown.

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
