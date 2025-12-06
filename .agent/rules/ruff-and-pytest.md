---
trigger: always_on
description: When large changes have been made apply these checks and formatting fixes
---

- Apply `uv run ruff check . --fix --unsafe-fixes` and `uv run ruff format .` to always make sure we're following Ruff formatting.
- use `uv run python -m pytest` to check for any breaking changes and address them