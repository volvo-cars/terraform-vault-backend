ARG PYTHON=3.11
FROM python:${PYTHON}-alpine3.19

ARG INCLUDE_DEV=false

RUN apk add --no-cache --virtual .pynacl_deps build-base python3-dev libffi-dev

RUN pip install poetry  

RUN mkdir -p /app  
COPY . /app

WORKDIR /app

EXPOSE 8000


# Example usage of the boolean argument
RUN if [ "$INCLUDE_DEV" = "true" ] ; then \
      poetry install; \
  else \
      poetry install --without dev; \
  fi

CMD ["poetry", "run", "python", "-m", "src"]
