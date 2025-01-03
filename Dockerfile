ARG PYTHON=3.13
FROM python:${PYTHON}-alpine AS builder

RUN pip install --no-cache poetry 

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_OPTIONS_NO_PIP=1 \
    POETRY_VIRTUALENVS_OPTIONS_NO_SETUPTOOLS=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --only=main --no-root && \
    rm -rf $POETRY_CACHE_DIR

FROM python:${PYTHON}-alpine

EXPOSE 8300

ENV VIRTUAL_ENV=/app/.venv \
     PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY src/*.py ./src/

CMD ["python", "-m", "src", "--host", "0.0.0.0"]
