ARG PYTHON=3.13
FROM python:${PYTHON}-alpine AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# The operation fails if the readme is missing
RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    uv sync --frozen --no-dev --no-editable

FROM python:${PYTHON}-alpine

EXPOSE 8300

ENV VIRTUAL_ENV=/app/.venv \
     PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY src/tvb/*.py ./src/

CMD ["python", "-m", "src", "--host", "0.0.0.0"]
