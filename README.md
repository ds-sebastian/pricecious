# Pricecious 💍

**Pricecious** is a self-hosted, AI-powered price tracking application. It uses [Ollama](https://ollama.com/) and the [Moondream](https://github.com/vikhyat/moondream) vision model to visually analyze product pages, detect prices, and monitor stock status.

## Features

*   **AI-Powered Analysis**: Uses Moondream to "see" the price and stock status on any webpage, bypassing complex HTML structures.
*   **Visual History**: Keeps a screenshot history of every check.
*   **Smart Scrolling**: Automatically scrolls pages to load lazy-loaded content before capturing.
*   **Text Context**: Optionally extracts page text to improve AI accuracy.
*   **Notifications**: Supports multi-channel notifications (Discord, Telegram, Email, etc.) via [Apprise](https://github.com/caronc/apprise).
*   **Dark Mode**: Beautiful "Apple-esque" UI with full dark/light mode support.
*   **Dockerized**: Easy to deploy with Docker Compose.

## Prerequisites

*   **Docker** and **Docker Compose**
*   **Ollama**: You must have an Ollama instance running and accessible.
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
          - OLLAMA_BASE_URL=http://host.docker.internal:11434
          - OLLAMA_MODEL=moondream
          - BROWSERLESS_URL=ws://browserless:3000
        depends_on:
          - db
          - browserless
        extra_hosts:
          - "host.docker.internal:host-gateway"

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
| `OLLAMA_BASE_URL` | URL of the Ollama API | `http://ollama:11434` | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | Name of the Ollama model to use | `moondream` | `moondream:latest` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@db:5432/pricewatch` | `postgresql://u:p@localhost:5432/db` |
| `BROWSERLESS_URL` | WebSocket URL for Browserless | `ws://browserless:3000` | `ws://browserless:3000` |
| `LOG_LEVEL` | Application logging level | `INFO` | `DEBUG` |

### Scraper Settings
Navigate to the **Settings** page in the UI to configure:
*   **Smart Scroll**: Enable to handle infinite scroll pages.
*   **Text Context**: Enable to send page text to the AI for better accuracy.

### Notifications
Create **Notification Profiles** in the Settings page using Apprise URLs.
*   Example Discord: `discord://webhook_id/webhook_token`
*   Example Telegram: `tgram://bot_token/chat_id`

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
