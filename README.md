# Pricecious 💍

**Pricecious** is a self-hosted, AI-powered price tracking application. It uses **GenAI Vision Models** (OpenAI, Anthropic, Gemini, Ollama, etc.) to visually analyze product pages, detect prices, and monitor stock status.

<img width="1577" height="1188" alt="main_page" src="https://github.com/user-attachments/assets/8453838d-b1c0-45af-a3fc-4a13843bb3f8" />

## Features

*   **AI-Powered Analysis**: Uses GenAI Vision Models to "see" the price and stock status on any webpage, bypassing complex HTML structures.
*   **Confidence Scoring**: AI provides confidence scores (0-1) for each extraction, enabling smart business rules and quality monitoring.
*   **Robust JSON Parsing**: Hardened parsing pipeline with automatic JSON repair fallback when primary extraction fails.
*   **Provider-Specific Optimization**: Leverages native JSON modes and structured output features for OpenAI, Ollama, and other providers.
*   **Visual History**: Keeps a screenshot history of every check with full AI metadata (model, provider, confidence, etc.).
*   **Smart Scrolling**: Automatically scrolls pages to load lazy-loaded content before capturing.
*   **Text Context**: Optionally extracts page text to improve AI accuracy.
*   **Notifications**: Supports multi-channel notifications (Discord, Telegram, Email, etc.) via [Apprise](https://github.com/caronc/apprise).
*   **Dark Mode**: Beautiful UI with full dark/light mode support.
*   **Dockerized**: Easy to deploy with Docker Compose.

## Prerequisites

*   **Docker** and **Docker Compose**
*   **AI Provider**: An API key for OpenAI, Anthropic, Gemini, OR a local Ollama instance.
*   **PostgreSQL**: A database for storing items and history (handled via Docker Compose).
*   **Browserless**: A headless browser service for scraping (handled via Docker Compose).

## Quick Start

1.  **Create a `docker-compose.yml` file:**
    Save the following content to a file named `docker-compose.yml`:

    ```yaml
    services:
      app:
        image: ghcr.io/ds-sebastian/pricecious:latest
        container_name: pricecious-app
        ports:
          - "8000:8000"
        environment:
          - DATABASE_URL=postgresql://user:password@db:5432/pricewatch
          - OLLAMA_BASE_URL=http://host.docker.internal:11434 # Optional default
          - OLLAMA_MODEL=moondream # Optional default
          - BROWSERLESS_URL=ws://browserless:3000
        depends_on:
          - db
          - browserless
        extra_hosts:
          - "host.docker.internal:host-gateway"
        volumes:
          - screenshots_data:/app/screenshots

      db:
        image: postgres:15-alpine
        environment:
          POSTGRES_USER: user
          POSTGRES_PASSWORD: password
          POSTGRES_DB: pricewatch
        volumes:
          - postgres_data:/var/lib/postgresql/data

      browserless:
        image: browserless/chrome:latest
        ports:
          - "3000:3000"
        environment:
          - MAX_CONCURRENT_SESSIONS=10

    volumes:
      postgres_data:
      screenshots_data:
    ```

2.  **Start the Application:**
    Run the following command in the same directory:
    ```bash
    docker compose up -d
    ```

3.  **Access the Dashboard:**
    Open your browser and navigate to `http://localhost:8000`.

## Configuration

### Environment Variables
The following environment variables can be configured in your `docker-compose.yml`:

| Variable | Description | Default | Example |
| :--- | :--- | :--- | :--- |
| `OLLAMA_BASE_URL` | Default URL for Ollama (can be changed in UI) | `http://ollama:11434` | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | Default model name (can be changed in UI) | `moondream` | `gemma3:4b` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@db:5432/pricewatch` | `postgresql://u:p@localhost:5432/db` |
| `BROWSERLESS_URL` | WebSocket URL for Browserless | `ws://browserless:3000` | `ws://browserless:3000` |
| `LOG_LEVEL` | Application logging level | `INFO` | `DEBUG` |

### Scraper Settings
Navigate to the **Settings** page in the UI to configure:
*   **Smart Scroll**: Enable to handle infinite scroll pages.
*   **Text Context**: Enable to send page text to the AI for better accuracy.

### AI Configuration
Navigate to the **Settings** page to configure your AI provider:
*   **Provider**: Choose between OpenAI, Anthropic, Gemini, Ollama, or Custom.
*   **Model**: Specify the model name (e.g., `gpt-4o`, `claude-3-5-sonnet`, `gemma3:4b`).
*   **API Key**: Enter your API key (not required for Ollama).
*   **Base URL**: Required for Ollama or custom OpenAI-compatible endpoints.

**Advanced AI Settings**:
*   **Temperature** (`ai_temperature`): Controls output randomness (0.0-1.0). Lower values (e.g., 0.1) produce more deterministic results. Default: `0.1`
*   **Max Tokens** (`ai_max_tokens`): Maximum tokens for AI responses. Default: `300`
*   **Price Confidence Threshold** (`confidence_threshold_price`): Minimum confidence (0.0-1.0) required to update price. Default: `0.5`
*   **Stock Confidence Threshold** (`confidence_threshold_stock`): Minimum confidence required to update stock status. Default: `0.5`
*   **Enable JSON Repair** (`enable_json_repair`): Automatically attempt to repair malformed JSON responses. Default: `true`

**How Confidence Works**:
- The AI provides a confidence score (0.0 to 1.0) for each extracted value
- Scores represent the AI's subjective probability that the extraction is correct
- If confidence is below the threshold, the value is logged but doesn't overwrite the current value
- Large price changes (>20%) with low confidence (<0.7) are flagged for manual review
- All extractions are saved in history with their confidence scores for analysis

### Notifications
Create **Notification Profiles** in the Settings page using Apprise URLs.
*   Example Discord: `discord://webhook_id/webhook_token`
*   Example Telegram: `tgram://bot_token/chat_id`

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
