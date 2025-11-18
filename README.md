# Pricecious 💍

**Pricecious** is a self-hosted, AI-powered price tracking application. It uses an [Ollama](https://ollama.com/) vision model to visually analyze product pages, detect prices, and monitor stock status.

## Features

*   **AI-Powered Analysis**: Uses an LLM to "see" the price and stock status on any webpage, bypassing complex HTML structures.
*   **Visual History**: Keeps a screenshot history of every check.
*   **Smart Scrolling**: Automatically scrolls pages to load lazy-loaded content before capturing.
*   **Text Context**: Optionally extracts page text to improve AI accuracy.
*   **Notifications**: Supports multi-channel notifications (Discord, Telegram, Email, etc.) via [Apprise](https://github.com/caronc/apprise).
*   **Dark Mode**: Beautiful "Apple-esque" UI with full dark/light mode support.
*   **Dockerized**: Easy to deploy with Docker Compose.

## Prerequisites

*   **Docker** and **Docker Compose**
*   **Ollama**: You must have an Ollama instance running and accessible.
    *   *Note: The default configuration assumes Ollama is running on the host machine.*

## Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ds-sebastian/pricecious.git
    cd pricecious
    ```

2.  **Configure Environment:**
    The `docker-compose.yml` is set up to connect to Ollama on the host machine via `host.docker.internal`.
    *   **Linux Users**: You may need to ensure your Ollama service is listening on `0.0.0.0` or allow docker connections.
    *   **OLLAMA_BASE_URL**: If your Ollama instance is elsewhere, update this environment variable in `docker-compose.yml`.

3.  **Start the Application:**
    ```bash
    docker compose up -d --build
    ```

4.  **Access the Dashboard:**
    Open your browser and navigate to `http://localhost:8000`.

## Configuration

### Scraper Settings
Navigate to the **Settings** page in the UI to configure:
*   **Smart Scroll**: Enable to handle infinite scroll pages.
*   **Text Context**: Enable to send page text to the AI for better accuracy.

### Notifications
Create **Notification Profiles** in the Settings page using Apprise URLs.
*   Example Discord: `discord://webhook_id/webhook_token`
*   Example Telegram: `tgram://bot_token/chat_id`

## Development

### Project Structure
*   `frontend/`: React + Vite application.
*   `backend/`: FastAPI Python application.
*   `docker-compose.yml`: Orchestration.

### Running Locally (Dev Mode)
1.  **Backend**:
    ```bash
    cd backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    ```
2.  **Frontend**:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
