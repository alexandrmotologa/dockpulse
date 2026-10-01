FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv for fast dependency installation (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.5.26 /uv /bin/uv

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

ENTRYPOINT ["dockpulse"]
CMD ["hud"]
