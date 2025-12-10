# Release 0.2.1

## Added
- **Scheduler:** Implemented scheduled data refresh job with configurable interval.
- **Robustness:** Added retry logic in `AIService` to handle empty LLM responses gracefully.
- **Tests:** Added integration tests for scheduler startup and job registration.

## Fixed
- **Scraper:** Enhanced scraper to exit early on navigation failures and reset browser state.
- **Hyperscaling:** Fixed heartbeat mechanism for `scheduled_refresh`.
- **AI:** Automatically infer Ollama provider from API base URL.
- **AI:** Enforced `json_repair` usage for more reliable JSON parsing.

## Refactor
- **Lifecycle:** Enhanced application lifespan management with robust error handling and graceful shutdown.
