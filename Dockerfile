FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=system

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

# Dependencies first, so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

# Run as a non-root user
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

CMD ["uv", "run", "python", "main.py", "--help"]
