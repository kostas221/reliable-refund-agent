# The demo application in one image: the screens built with Node and served by the Python server on the API's own
# origin (docs/screens.md). Mock mode by default: the scripted agent of one development scenario, no API key, no cost.
# Started with the database by `docker compose --profile app up --build`; base images pinned by digest, like the
# database's (plan section 5).

FROM node:22-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS screens
WORKDIR /screens
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv

FROM python:3.12-slim@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/venv \
    PYTHONUNBUFFERED=1
WORKDIR /app
# Dependencies first, exactly as locked, so a change of code does not reinstall them.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY policies ./policies
COPY prompts ./prompts
COPY scenarios ./scenarios
COPY data/olist ./data/olist
COPY refund_agent ./refund_agent
COPY --from=screens /screens/dist ./screens
RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
EXPOSE 8000
# 0.0.0.0 inside the container only; docker-compose.yml publishes the port to this computer alone.
ENTRYPOINT ["/venv/bin/python", "-m", "refund_agent.api", "--host", "0.0.0.0", "--screens", "/app/screens"]
CMD ["--scenario", "D01"]
