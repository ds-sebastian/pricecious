# Stage 1: Build Frontend
FROM node:22-alpine as frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

# Stage 2: Build Backend and Serve
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy build files
COPY pyproject.toml .
COPY README.md .

# Use uv for faster installation (fixed syntax)
RUN uv pip install --system --no-cache .

# Copy backend code
COPY app/ ./app
COPY alembic.ini ./
COPY docker-entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Copy built frontend static files
COPY --from=frontend-build /app/frontend/dist /app/static

# Create screenshots directory
RUN mkdir -p screenshots

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/')" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
