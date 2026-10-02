FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

RUN groupadd --system --gid 10001 docpipe \
    && useradd --system --uid 10001 --gid 10001 \
        --no-create-home --shell /usr/sbin/nologin docpipe

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

USER 10001:10001

CMD ["uvicorn", "docpipe_ingestion.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
